# Projeto Prático: Conversor Escalável de Vídeo, Áudio e Imagem com Processamento Assíncrono

Sistema distribuído de conversão de mídia assíncrono desenvolvido para a disciplina de **Sistemas Distribuídos**.

A arquitetura desacopla a ingestão HTTP do processamento pesado utilizando **RabbitMQ** como message broker (competing consumers), **MinIO** como Object Storage S3 compatível, **Redis** para persistência do estado dos jobs e **Mailpit** para simulação e visualização de notificações por e-mail via SMTP.

---

## 🏛️ Arquitetura Distribuída

```
 [ Usuário / Browser ]
          │
     Upload HTTP (Porta 8000)
          ▼
┌──────────────────────────────┐
│       API de Ingestão        │ ──(1) Grava Origem──► ┌───────────────────┐
│     (Flask Producer)         │                       │       MinIO       │
└──────────────┬───────────────┘                       │ (Object Storage)  │
               │                                       │   uploads/        │
    (2) Publica Job (JSON)                             │   converted/      │
               ▼                                       └─────────┬─────────┘
┌──────────────────────────────┐                                 ▲
│      Broker RabbitMQ         │                                 │ (3) GET Origem
│  Fila: conversion_queue      │                                 │ (4) PUT Convertido
└──────────────┬───────────────┘                                 │ (5) DELETE Origem
               │                                                 │
      (Competing Consumers)                                      │
               ▼                                                 │
┌──────────────────────────────┐                                 │
│      Worker 1 .. Worker N    │ ────────────────────────────────┘
│     (FFmpeg / Pillow)        │
└──────────────┬───────────────┘
               │
      (6) Publica Conclusão
               ▼
┌──────────────────────────────┐
│     Serviço Notificação      │ ──(7) Envia E-mail──► ┌───────────────────┐
│         (SMTP)               │                       │      Mailpit      │
└──────────────────────────────┘                       │  (Painel Web: 8025)│
                                                       └───────────────────┘
```

---

## 🛠️ Tecnologias Utilizadas

| Componente | Tecnologia | Papel no Sistema |
| :--- | :--- | :--- |
| **API de Ingestão** | Python (Flask) | Recebe uploads, grava no MinIO e enfileira jobs com resposta imediata HTTP 202. |
| **Message Broker** | RabbitMQ (Alpine) | Desacoplamento, filas duráveis, competing consumers e Dead Letter Queue (DLQ). |
| **Object Storage** | MinIO | Armazenamento de uploads temporários e arquivos convertidos com links públicos. |
| **Workers** | Python + FFmpeg + Pillow | Processamento paralelo de vídeo, áudio e imagem com confirmação manual (ACK). |
| **Notificação** | Python (smtplib) | Consumidor desacoplado que envia e-mails com o link de download. |
| **Servidor SMTP** | Mailpit | Servidor SMTP local com interface web para inspeção imediata dos e-mails. |
| **Estado dos Jobs** | Redis | Rastreamento em tempo real (PENDENTE, PROCESSANDO, CONCLUÍDO, ERRO). |
| **Orquestração** | Docker Compose | Subida de todo o cluster com um único comando. |

---

## 🚀 Como Executar o Projeto

### Passo Único
Na pasta do projeto, execute:
```bash
docker compose up -d --build
```

### Portas e Painéis Disponíveis
* **Interface Web Principal:** [http://localhost:8000](http://localhost:8000)
* **Painel RabbitMQ:** [http://localhost:15672](http://localhost:15672) *(Login: `guest` / Senha: `guest`)*
* **Console MinIO:** [http://localhost:9001](http://localhost:9001) *(Login: `minioadmin` / Senha: `minioadmin`)*
* **Caixa de Entrada Mailpit:** [http://localhost:8025](http://localhost:8025)

---

## 📈 Como Escalar os Workers Horizontalmente

Para demonstrar a escalabilidade horizontal e o ganho de throughput com múltiplos workers consumindo da mesma fila em paralelo (competing consumers):
```bash
docker compose up -d --scale worker=3
```
O RabbitMQ distribuirá automaticamente as mensagens entre os 3 workers (`conversor-worker-1`, `conversor-worker-2`, `conversor-worker-3`) utilizando `basic_qos(prefetch_count=1)`.

---

## 🧪 Como Executar a Bateria de Testes Automatizada

Você pode rodar todos os testes de ponta a ponta com o script:
```powershell
powershell -ExecutionPolicy Bypass -File .\run_tests.ps1
```

O script valida automaticamente:
1. **Aceite Imediato (RF02):** Envio do arquivo e retorno em < 150ms com status `PENDENTE`.
2. **Processamento Assíncrono (RF03):** Polling do status até a transição para `CONCLUÍDO`.
3. **Link Público (RF04):** Acesso HTTP 200 direto ao arquivo convertido no MinIO.
4. **Limpeza do Arquivo de Origem (RF05):** Remoção confirmada do bucket `uploads`.
5. **Notificação por E-mail (RF06):** Verificação da mensagem recebida na API do Mailpit.
