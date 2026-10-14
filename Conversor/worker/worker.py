import os
import time
import json
import socket
import subprocess
from pathlib import Path
from PIL import Image
import pika
from minio import Minio
import redis

# Configurações do ambiente
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")

QUEUE_NAME = "conversion_queue"
NOTIFICATION_QUEUE = "notification_queue"
DLQ_QUEUE_NAME = "dead_letter_queue"
MAX_ATTEMPTS = 3

WORKER_ID = socket.gethostname()

# Clientes
r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

def convert_image(input_path: str, output_path: str, target_fmt: str):
    """Conversão de imagem usando Pillow"""
    with Image.open(input_path) as img:
        target_fmt = target_fmt.lower()
        if target_fmt in ["jpg", "jpeg"]:
            # Converte modo RGBA para RGB se necessário
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output_path, "JPEG")
        elif target_fmt == "png":
            img.save(output_path, "PNG")
        elif target_fmt == "webp":
            img.save(output_path, "WEBP")
        elif target_fmt == "bmp":
            img.save(output_path, "BMP")
        else:
            img.save(output_path)

def convert_media_ffmpeg(input_path: str, output_path: str):
    """Conversão de vídeo e áudio utilizando FFmpeg"""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        output_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg falhou: {res.stderr.decode('utf-8', errors='ignore')}")

def process_conversion(payload: dict):
    job_id = payload["jobId"]
    source_bucket = payload["sourceBucket"]
    source_object = payload["sourceObject"]
    source_type = payload.get("sourceType", "video")
    source_format = payload.get("sourceFormat", "mp4")
    target_format = payload["targetFormat"].lower()
    notify_email = payload.get("notifyEmail", "")

    # IDEMPOTÊNCIA: Verifica se o job já foi concluído anteriormente
    raw_job = r.get(f"job:{job_id}")
    if raw_job:
        job_data = json.loads(raw_job)
        if job_data.get("status") == "CONCLUÍDO":
            print(f"[{WORKER_ID}] Job {job_id} já concluído anteriormente. Ignorando reprocessamento.")
            return True

    print(f"[{WORKER_ID}] Iniciando conversão do Job {job_id} ({source_format} -> {target_format})...")

    # Atualiza status para PROCESSANDO
    if raw_job:
        job_data = json.loads(raw_job)
        job_data["status"] = "PROCESSANDO"
        job_data["worker"] = WORKER_ID
        r.set(f"job:{job_id}", json.dumps(job_data))

    temp_dir = Path("/tmp")
    local_input = temp_dir / f"{job_id}_in.{source_format}"
    local_output = temp_dir / f"{job_id}_out.{target_format}"

    # 1. Download do arquivo de origem do MinIO
    minio_client.fget_object(source_bucket, source_object, str(local_input))

    # 2. Execução da conversão
    if source_type == "image" and target_format in ["jpg", "jpeg", "png", "webp", "bmp"]:
        convert_image(str(local_input), str(local_output), target_format)
    else:
        convert_media_ffmpeg(str(local_input), str(local_output))

    # 3. Envio do arquivo convertido para o bucket 'converted' no MinIO
    if not minio_client.bucket_exists("converted"):
        minio_client.make_bucket("converted")

    output_object_name = f"{job_id}.{target_format}"
    minio_client.fput_object("converted", output_object_name, str(local_output))

    # 4. Geração do link público de download (RF04)
    public_url = f"http://localhost:9000/converted/{output_object_name}"

    # 5. RF05: Limpeza do arquivo de origem no MinIO após sucesso na persistência
    minio_client.remove_object(source_bucket, source_object)
    print(f"[{WORKER_ID}] Arquivo temporário de origem {source_object} removido do MinIO com sucesso.")

    # 6. Atualiza o status do Job para CONCLUÍDO
    if raw_job:
        job_data = json.loads(raw_job)
        job_data["status"] = "CONCLUÍDO"
        job_data["downloadUrl"] = public_url
        r.set(f"job:{job_id}", json.dumps(job_data))

    # 7. Dispara evento de conclusão para a fila de notificações
    notification_payload = {
        "jobId": job_id,
        "notifyEmail": notify_email,
        "downloadUrl": public_url,
        "filename": output_object_name,
        "status": "CONCLUÍDO"
    }

    # Limpeza dos arquivos locais no container
    local_input.unlink(missing_ok=True)
    local_output.unlink(missing_ok=True)

    print(f"[{WORKER_ID}] Conversão concluída para Job {job_id}!")
    return notification_payload

def on_message(ch, method, properties, body):
    payload = json.loads(body.decode("utf-8"))
    job_id = payload.get("jobId")
    attempt = payload.get("attempt", 1)

    try:
        notification_payload = process_conversion(payload)
        if notification_payload and isinstance(notification_payload, dict):
            # Publica evento de conclusão para o serviço de notificação desacoplado
            ch.basic_publish(
                exchange="",
                routing_key=NOTIFICATION_QUEUE,
                body=json.dumps(notification_payload),
                properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
            )

        # Confirmação manual (ACK) somente após persistência e sucesso
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[{WORKER_ID}] Erro na tentativa {attempt} para o Job {job_id}: {e}")
        if attempt < MAX_ATTEMPTS:
            payload["attempt"] = attempt + 1
            # Reenfileira com incremento de tentativa
            ch.basic_publish(
                exchange="",
                routing_key=QUEUE_NAME,
                body=json.dumps(payload),
                properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            # Envia para a Dead Letter Queue após atingir o limite de tentativas
            print(f"[{WORKER_ID}] Job {job_id} atingiu limite de tentativas. Movendo para DLQ.")
            ch.basic_publish(
                exchange="",
                routing_key=DLQ_QUEUE_NAME,
                body=json.dumps({"error": str(e), "original": payload}),
                properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
            )
            # Atualiza status para ERRO no Redis (o arquivo de origem é preservado no MinIO)
            raw = r.get(f"job:{job_id}")
            if raw:
                job_data = json.loads(raw)
                job_data["status"] = "ERRO"
                job_data["error"] = str(e)
                r.set(f"job:{job_id}", json.dumps(job_data))

            ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    print(f"[{WORKER_ID}] Inicializando worker de conversão de mídia...")
    # Aguarda o RabbitMQ ficar pronto
    while True:
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600))
            channel = conn.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.queue_declare(queue=NOTIFICATION_QUEUE, durable=True)
            channel.queue_declare(queue=DLQ_QUEUE_NAME, durable=True)

            # Competing Consumers: prefetch=1 garante distribuição equilibrada entre múltiplos workers
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message)
            print(f"[{WORKER_ID}] Conectado ao RabbitMQ! Aguardando pedidos de conversão...")
            channel.start_consuming()
        except Exception as e:
            print(f"[{WORKER_ID}] Aguardando RabbitMQ estar disponível... ({e})")
            time.sleep(3)

if __name__ == "__main__":
    main()
