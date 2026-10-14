# Sistemas Distribuídos

Repositório contendo as atividades práticas e projetos da disciplina de **Sistemas Distribuídos**.

---

##  Projetos Implementados

### 1. [LoadBalancer](./LoadBalancer/)
* **Objetivo:** Escalabilidade de aplicações web com balanceamento de carga HTTP em camada 7.
* **Tecnologias:** NGINX (Reverse Proxy & Round-Robin), Python (Flask + Gunicorn), Docker Compose.
* **Destaques:**
  * 3 instâncias ativas com identificador visual e cabeçalho `X-Served-By`.
  * Prova negativa em porta direta.
  * Suporte a escala horizontal dinâmica e tolerância a falhas sem interrupção de serviço.
  * Bateria de testes automatizada (`run_tests.ps1`) e script de volume (`test_distribution.py`).

### 2. [Conversor de Mídia](./Conversor/)
* **Objetivo:** Conversor assíncrono e distribuído de vídeo, áudio e imagem.
* **Tecnologias:** RabbitMQ (Message Broker), MinIO (Object Storage S3), Redis (Job State), Mailpit (SMTP Mock), FFmpeg & Pillow (Workers), Python (Flask API), Docker Compose.
* **Destaques:**
  * Desacoplamento total via filas de mensageria com padrão *Claim Check*.
  * Competing Consumers escaláveis horizontalmente com `prefetch_count=1`.
  * Confirmação manual (*Manual ACK*), retentativas e Dead Letter Queue (DLQ).
  * Idempotência garantida por `jobId`.
  * Ciclo de vida com remoção automática do arquivo de origem após persistência e link público para download.
  * Relatório técnico completo de 5 páginas ([`RELATORIO_TECNICO.md`](./Conversor/RELATORIO_TECNICO.md)).

---

##  Como Executar

Cada pasta possui seu próprio ambiente containerizado independente:

```bash
# Para rodar o Load Balancer:
cd LoadBalancer
docker compose up -d --build

# Para rodar o Conversor de Mídia:
cd Conversor
docker compose up -d --build
```
