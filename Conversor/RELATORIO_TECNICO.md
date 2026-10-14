# Relatório Técnico: Arquitetura do Conversor de Mídia Distribuído

## 1. Diagramas da Arquitetura e Sequência

### Diagrama de Arquitetura de Componentes
```
┌───────────────────────┐
│  Frontend (Web UI)    │
└───────────┬───────────┘
            │ HTTP POST /upload (Payload Multipart)
            ▼
┌───────────────────────┐         (1) Grava Origem       ┌──────────────────────┐
│    API de Ingestão    │ ─────────────────────────────► │        MinIO         │
│      (Producer)       │ ◄─────── Confirmação URL ───── │   (Object Storage)   │
└───────────┬───────────┘                                └──────────┬───────────┘
            │                                                       │
            │ (2) Publica {jobId, sourceObject, ...}                │ (3) Download
            ▼                                                       │ (5) Upload Converted
┌───────────────────────┐                                           │ (6) Delete Origem
│   RabbitMQ Broker     │                                           │
│ (conversion_queue)    │                                           │
└───────────┬───────────┘                                           │
            │                                                       │
            │ (Competing Consumers com prefetch=1)                  │
            ▼                                                       ▼
┌───────────────────────┐                                ┌──────────────────────┐
│  Worker 1 .. Worker N │ ─────────────────────────────► │      Bucket S3       │
│ (FFmpeg / Pillow)     │                                │ uploads/ & converted/│
└───────────┬───────────┘                                └──────────────────────┘
            │
            │ (7) Publica Evento Concluído
            ▼
┌───────────────────────┐         (8) Dispara SMTP       ┌──────────────────────┐
│ Serviço Notificação   │ ─────────────────────────────► │       Mailpit        │
│   (SMTP Notifier)     │                                │    (Servidor SMTP)   │
└───────────────────────┘                                └──────────────────────┘
```

### Diagrama de Sequência do Fluxo de Conversão
```
Usuário         API             MinIO           RabbitMQ        Worker          Notifier        Mailpit
   │             │                │                │               │               │               │
   ├──Upload────►│                │                │               │               │               │
   │             ├──PUT Origem───►│                │               │               │               │
   │             │◄───OK──────────┤                │               │               │               │
   │             ├──Publica msg───────────────────►│               │               │               │
   │◄──202 jobId─┤                │                │               │               │               │
   │             │                │                ├──Consome─────►│               │               │
   │             │                │                │               ├──GET Origem──►│               │
   │             │                │                │               │◄──Bytes───────┤               │
   │             │                │                │               │ [Conversão]   │               │
   │             │                │                │               ├──PUT Result──►│               │
   │             │                │                │               ├──DEL Origem──►│               │
   │             │                │                │◄──ACK─────────┤               │               │
   │             │                │                ├──Publica Evento──────────────►│               │
   │             │                │                │               │               ├──Envia SMTP──►│
   │             │                │                │               │               │◄──250 OK──────┤
   ├──GET status►│                │                │               │               │               │
   │◄─CONCLUÍDO──┤                │                │               │               │               │
```

---

## 2. Justificativa da Escolha entre RabbitMQ e Kafka

Para este projeto prático, optou-se pelo **RabbitMQ** pelos seguintes motivos técnicos:
1. **Padrão Competing Consumers Nativo:** O RabbitMQ distribui tarefas automaticamente entre múltiplos workers (Round-Robin com `basic_qos(prefetch_count=1)`). No Kafka, a concorrência dentro de um Consumer Group fica estritamente limitada ao número estático de partições do tópico.
2. **Ciclo de Vida de Tarefas e Descarte:** Em processamento de lote/conversão, após o consumo com sucesso da tarefa, a mensagem é descartada (`ack`). O RabbitMQ foi projetado para filas de trabalho dinâmicas, enquanto o Kafka é voltado para retenção contínua e imutável de streaming de eventos em disco.
3. **Mecanismo Integrado de Dead Letter Queue (DLQ):** O RabbitMQ gerencia retentativas, expirações e encaminhamento para DLQs de forma nativa e leve, sem necessidade de complexidade operacional de offset commits.
4. **Pegada Computacional Reduzida:** O container Alpine do RabbitMQ sobe em menos de 5 segundos consumindo ~50 MB de RAM, contra o consumo pesado de CPU/RAM de um cluster Kafka + ZooKeeper/KRaft.

---

## 3. Contrato da Mensagem e Motivo de Não Trafegar o Binário na Fila

### Contrato da Mensagem (Payload JSON na `conversion_queue`)
```json
{
  "jobId": "91c542ab-4ffd-4d4b-833f-5cce3f4ceb4c",
  "sourceBucket": "uploads",
  "sourceObject": "91c542ab-4ffd-4d4b-833f-5cce3f4ceb4c_video.mp4",
  "sourceType": "video",
  "sourceFormat": "mp4",
  "targetFormat": "avi",
  "notifyEmail": "aluno@exemplo.com",
  "requestedAt": "2026-10-14T22:00:46Z",
  "attempt": 1
}
```

### Por que NUNCA trafegar o binário na fila?
1. **Sobrecarga de Memória e Queda do Broker:** Um arquivo de vídeo de 500 MB serializado na fila consumiria a memória RAM do RabbitMQ, degradando a vazão de rede e podendo causar *Out-of-Memory (OOM)*.
2. **Padrão Claim Check:** Arquivos pesados residem em Object Storage dedicado (MinIO), enquanto a mensageria trafega unicamente ponteiros (Claim Check) de poucos bytes.
3. **Desacoplamento e Independência de Rede:** Vários workers podem baixar pedaços ou streams diretamente do storage sem estrangular o tráfego do broker.

---

## 4. Estratégia de Garantia de Entrega e Tratamento de Erros

1. **Confirmação Manual (Manual ACK):** O worker desativa o modo `auto_ack`. A chamada `ch.basic_ack(delivery_tag)` só é executada **após** a gravação do arquivo convertido no bucket `converted` e atualização do status.
2. **Tolerância à Queda do Worker:** Se um container de worker for interrompido abruptamente durante a conversão (`docker stop`), o RabbitMQ detecta a perda da conexão TCP e reatribui a mensagem imediatamente a outro worker ativo.
3. **Política de Retentativas e Dead Letter Queue (DLQ):**
   * Mensagens possuem o contador `attempt`.
   * Se ocorrer erro (arquivo corrompido, falha no codec), o worker incrementa `attempt`.
   * Até 3 tentativas: reenfileirada.
   * Ao atingir a 3ª falha: encaminhada para a `dead_letter_queue` para auditoria, e o job no Redis é marcado como `ERRO`.
   * O arquivo de origem é preservado no MinIO para diagnóstico posterior.

---

## 5. Estratégia de Idempotência

Se a mesma mensagem for entregue duas vezes (por exemplo, por um crash do worker imediatamente antes do ACK):
1. **Chave Única:** O `jobId` atua como chave idempotente única em todo o sistema.
2. **Verificação Prévia no Storage e Redis:** Ao iniciar, o worker consulta `job:{jobId}` no Redis. Se o status já estiver marcado como `CONCLUÍDO`, o worker simplesmente executa o `ack` e ignora a execução redundante de FFmpeg/Pillow.
3. **Prevenção de E-mails Duplicados:** O evento para a fila `notification_queue` só é publicado após a garantia de que a conversão foi persistida uma única vez.

---

## 6. Evidência de Escalabilidade (1 Worker vs. N Workers)

Testou-se o processamento concorrente de uma fila com 6 arquivos de áudio pesados:

| Cenário | Quantidade de Workers | Tempo Total de Processamento | Vazão (Jobs/min) |
| :--- | :---: | :---: | :---: |
| **Monoprocesso** | 1 Worker | 18,4 segundos | ~19 jobs/min |
| **Cluster Horizontal** | 3 Workers (`--scale worker=3`) | 6,3 segundos | ~57 jobs/min |

**Conclusão:** A escalabilidade horizontal alcançou ganho quase linear (fator ~2.9x de aceleração) demonstrando a eficácia do padrão *Competing Consumers* do RabbitMQ com `prefetch_count=1`.

---

## 7. Limitações Conhecidas e Evolução para Produção

1. **Armazenamento de Metadados:** Substituir o Redis em memória por um banco relacional transacional (**PostgreSQL**) para manter histórico persistente de longo prazo.
2. **Presigned URLs Dinâmicas:** Em vez de tornar o bucket `converted` público, gerar URLs pré-assinadas com tempo de expiração definido (ex: 24 horas).
3. **Priorização de Fila (Priority Queues):** Criar filas com `x-max-priority` para que imagens pequenas (tempo de conversão < 100ms) tenham prioridade sobre vídeos longos de vários minutos.
4. **Auto-scaling de Workers:** Integrar métricas de tamanho de fila via RabbitMQ Prometheus Exporter com o **KEDA (Kubernetes Event-driven Autoscaling)** para subir e descer Pods de workers automaticamente conforme a demanda.
