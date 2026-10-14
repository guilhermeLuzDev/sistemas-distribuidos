import os
import io
import json
import uuid
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from minio import Minio
import redis
import pika

app = Flask(__name__)

# Configurações do ambiente
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")

QUEUE_NAME = "conversion_queue"
NOTIFICATION_QUEUE = "notification_queue"
DLQ_QUEUE_NAME = "dead_letter_queue"

# Inicializa clientes de conexão
r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

def init_minio_buckets():
    """Garante a criação dos buckets e configura leitura pública no bucket 'converted' (RF04)."""
    for _ in range(10):
        try:
            if not minio_client.bucket_exists("uploads"):
                minio_client.make_bucket("uploads")
            if not minio_client.bucket_exists("converted"):
                minio_client.make_bucket("converted")
            
            public_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
                        "Resource": ["arn:aws:s3:::converted"]
                    },
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": ["arn:aws:s3:::converted/*"]
                    }
                ]
            }
            minio_client.set_bucket_policy("converted", json.dumps(public_policy))
            print("[MinIO] Buckets 'uploads' e 'converted' configurados com sucesso!")
            return
        except Exception as e:
            time.sleep(2)

def get_rabbitmq_channel():
    """Conecta ao RabbitMQ com retentativa até o broker estar pronto."""
    for _ in range(10):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600)
            )
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.queue_declare(queue=NOTIFICATION_QUEUE, durable=True)
            channel.queue_declare(queue=DLQ_QUEUE_NAME, durable=True)
            return connection, channel
        except Exception:
            time.sleep(2)
    raise RuntimeError("Não foi possível conectar ao RabbitMQ")

def detect_source_type(ext: str) -> str:
    ext = ext.lower().replace(".", "")
    if ext in ["mp4", "avi", "mov", "mkv", "webm", "flv"]:
        return "video"
    elif ext in ["mp3", "wav", "ogg", "aac", "flac", "m4a"]:
        return "audio"
    elif ext in ["png", "jpg", "jpeg", "webp", "bmp", "gif"]:
        return "image"
    return "unknown"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    """
    RF01 e RF02: Recebe o arquivo, grava no MinIO, publica mensagem na fila
    e responde IMEDIATAMENTE com HTTP 202 (Accepted) e o jobId, sem esperar a conversão.
    """
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    target_format = request.form.get("targetFormat", "").strip().lower()
    notify_email = request.form.get("email", "").strip()

    if not file.filename or not target_format:
        return jsonify({"error": "Arquivo e formato de destino são obrigatórios"}), 400

    filename = file.filename
    source_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    source_type = detect_source_type(source_ext)

    if source_type == "unknown":
        return jsonify({"error": f"Extensão de arquivo não suportada: .{source_ext}"}), 400

    job_id = str(uuid.uuid4())
    object_name = f"{job_id}_{filename}"

    # Lê o arquivo para buffer em memória e envia para o MinIO bucket 'uploads'
    file_bytes = file.read()
    file_stream = io.BytesIO(file_bytes)

    # Assegura que o bucket de uploads existe
    if not minio_client.bucket_exists("uploads"):
        minio_client.make_bucket("uploads")

    minio_client.put_object(
        bucket_name="uploads",
        object_name=object_name,
        data=file_stream,
        length=len(file_bytes),
        content_type=file.content_type or "application/octet-stream"
    )

    # Persiste o estado inicial do Job no Redis com status PENDENTE
    job_data = {
        "jobId": job_id,
        "filename": filename,
        "sourceType": source_type,
        "sourceFormat": source_ext,
        "targetFormat": target_format,
        "notifyEmail": notify_email,
        "status": "PENDENTE",
        "createdAt": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "downloadUrl": ""
    }
    r.set(f"job:{job_id}", json.dumps(job_data))
    r.lpush("jobs:recent", job_id)

    # Contrato da Mensagem conforme Seção 5 do PDF (apenas metadados e referência, sem binário!)
    message_payload = {
        "jobId": job_id,
        "sourceBucket": "uploads",
        "sourceObject": object_name,
        "sourceType": source_type,
        "sourceFormat": source_ext,
        "targetFormat": target_format,
        "notifyEmail": notify_email,
        "requestedAt": datetime.now().isoformat(),
        "attempt": 1
    }

    # Publica a mensagem de forma persistente no RabbitMQ
    connection, channel = get_rabbitmq_channel()
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(message_payload),
        properties=pika.BasicProperties(
            delivery_mode=pika.DeliveryMode.Persistent,
            content_type="application/json"
        )
    )
    connection.close()

    # Retorno imediato (RF02)
    return jsonify({
        "message": "Pedido de conversão aceito com sucesso!",
        "jobId": job_id,
        "status": "PENDENTE"
    }), 202

@app.route("/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """
    RF07: Consulta de status do pedido (PENDENTE, PROCESSANDO, CONCLUÍDO, ERRO).
    """
    raw = r.get(f"job:{job_id}")
    if not raw:
        return jsonify({"error": "Job não encontrado"}), 404
    return jsonify(json.loads(raw))

@app.route("/jobs", methods=["GET"])
def list_jobs():
    """Lista os últimos jobs para exibição no painel de acompanhamento."""
    job_ids = r.lrange("jobs:recent", 0, 9)
    jobs = []
    for jid in job_ids:
        raw = r.get(f"job:{jid}")
        if raw:
            jobs.append(json.loads(raw))
    return jsonify(jobs)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "UP"}), 200

if __name__ == "__main__":
    init_minio_buckets()
    app.run(host="0.0.0.0", port=5000, debug=False)
