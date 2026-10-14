import os
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pika

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
SMTP_HOST = os.environ.get("SMTP_HOST", "mailpit")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 1025))
NOTIFICATION_QUEUE = "notification_queue"

def send_email(to_email: str, job_id: str, download_url: str, filename: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Conversão Concluída] Seu arquivo {filename} está pronto!"
    msg["From"] = "conversor@plataforma.com"
    msg["To"] = to_email

    text = f"""Olá,

Seu arquivo foi convertido com sucesso!
- Arquivo: {filename}
- Job ID: {job_id}

Você pode baixá-lo diretamente pelo link público:
{download_url}

Atenciosamente,
Sistema Distribuído de Conversão de Mídia
"""
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; border: 1px solid #e2e8f0;">
          <h2 style="color: #0284c7; margin-top: 0;">Conversão Concluída com Sucesso!</h2>
          <p>Olá, o seu pedido de conversão de mídia foi processado pelos nossos workers assíncronos.</p>
          <ul style="color: #475569;">
            <li><strong>Arquivo:</strong> {filename}</li>
            <li><strong>Job ID:</strong> <code>{job_id}</code></li>
          </ul>
          <div style="margin: 30px 0; text-align: center;">
            <a href="{download_url}" style="background-color: #0284c7; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
              Baixar Arquivo Convertido
            </a>
          </div>
          <p style="font-size: 0.85rem; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 15px;">
            Link direto: <a href="{download_url}">{download_url}</a>
          </p>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.sendmail("conversor@plataforma.com", [to_email], msg.as_string())
    print(f"[Notifier] E-mail de notificação enviado para {to_email} (Job: {job_id})")

def on_notification(ch, method, properties, body):
    try:
        data = json.loads(body.decode("utf-8"))
        job_id = data.get("jobId")
        notify_email = data.get("notifyEmail")
        download_url = data.get("downloadUrl")
        filename = data.get("filename", "arquivo")

        if notify_email:
            send_email(notify_email, job_id, download_url, filename)

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"[Notifier] Erro ao enviar e-mail: {e}")
        # Em caso de falha de conexão SMTP, dá nack com requeue
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        time.sleep(2)

def main():
    print("[Notifier] Inicializando serviço de notificação por e-mail...")
    while True:
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600))
            channel = conn.channel()
            channel.queue_declare(queue=NOTIFICATION_QUEUE, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=NOTIFICATION_QUEUE, on_message_callback=on_notification)
            print("[Notifier] Conectado ao RabbitMQ! Aguardando eventos de conclusão...")
            channel.start_consuming()
        except Exception as e:
            print(f"[Notifier] Aguardando RabbitMQ... ({e})")
            time.sleep(3)

if __name__ == "__main__":
    main()
