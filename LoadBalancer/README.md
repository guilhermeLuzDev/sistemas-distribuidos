# Atividade Avaliativa: Escalabilidade de Aplicações Web com Load Balancer

Este repositório contém a implementação completa, didática e containerizada de uma arquitetura web escalável com balanceamento de carga, desenvolvida para a disciplina de **Sistemas Distribuídos**.

A solução utiliza **Python (Flask + Gunicorn)** para as instâncias da aplicação web e **NGINX** como proxy reverso e balanceador de carga em camada 7 (HTTP), orquestrados via **Docker Compose**.

---

##  Arquitetura da Solução

Todas as requisições externas chegam unicamente através do Load Balancer na porta `8080`. O balanceador distribui as requisições entre as instâncias internas do pool utilizando o algoritmo **Round-Robin**.

```
                        [ Cliente / Navegador ]
                                  │
                       Requisição HTTP (Porta 8080)
                                  ▼
                    ┌───────────────────────────┐
                    │  Load Balancer (NGINX)    │
                    │  Porta Externa: 8080      │
                    │  Política: Round-Robin    │
                    └─────────────┬─────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │ (Round-Robin)          │ (Round-Robin)          │ (Round-Robin)
         ▼                        ▼                        ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│     app-01      │      │     app-02      │      │     app-03      │
│  (Porta: 5000)  │      │  (Porta: 5000)  │      │  (Porta: 5000)  │
│  Cor: Azul      │      │  Cor: Verde     │      │  Cor: Laranja   │
│  X-Served-By:   │      │  X-Served-By:   │      │  X-Served-By:   │
│     app-01      │      │     app-02      │      │     app-03      │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

> **Prova Negativa:** Para fins de comprovação acadêmica (conforme item 4 da especificação), as instâncias também expõem portas diretas no host (`3001`, `3002`, `3003`). Ao acessar uma porta direta, o indicador nunca se altera, comprovando que a alternância observada na porta `8080` decorre exclusivamente do balanceador de carga.

---

##  Tecnologias Utilizadas

| Tecnologia | Função na Arquitetura |
| :--- | :--- |
| **Python 3.11** | Linguagem base da aplicação backend |
| **Flask** | Microframework web para rotas, templates e endpoints `/health` e `/api/info` |
| **Gunicorn** | Servidor WSGI de produção executando 1 worker independente por container |
| **NGINX (Alpine)** | Proxy reverso e Load Balancer (Round-Robin e failover automático) |
| **Docker & Docker Compose** | Isolamento de processos, redes virtuais e orquestração de containers |

---

##  Como o Balanceamento foi Configurado

A configuração reside em [`nginx/nginx.conf`](nginx/nginx.conf):

1. **Definição do Upstream:**
   ```nginx
   upstream backend_servers {
       server app-01:5000 max_fails=1 fail_timeout=5s;
       server app-02:5000 max_fails=1 fail_timeout=5s;
       server app-03:5000 max_fails=1 fail_timeout=5s;
   }
   ```
   * O NGINX aplica o algoritmo **Round-Robin** sequencialmente entre os servidores.
   * `max_fails=1` e `fail_timeout=5s` definem a detecção passiva de falhas: se uma instância não responder, ela é temporariamente suspensa por 5 segundos.

2. **Tolerância a Falhas e Failover Imediato (`proxy_next_upstream`):**
   ```nginx
   proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504;
   proxy_next_upstream_tries 3;
   proxy_next_upstream_timeout 5s;
   proxy_connect_timeout 1s;
   ```
   * Caso uma instância seja interrompida abruptamente, o NGINX **não** retorna erro ao cliente; ele redireciona a requisição instantaneamente para a próxima instância saudável do pool de forma transparente.

3. **Injeção de Identificador Dinâmico (Sem Código Fixo):**
   * A aplicação lê obrigatoriamente a variável `INSTANCE_ID` injetada via `docker-compose.yml`:
     ```python
     INSTANCE_ID = os.environ.get("INSTANCE_ID", socket.gethostname())
     ```
   * A cor visual e o cabeçalho HTTP de identificação (`X-Served-By`) são gerados com base nessa variável.

---

##  Como Executar o Projeto

### Pré-requisitos
* **Docker** e **Docker Compose** instalados e em execução.
* **Python 3.x** (para rodar os scripts de teste automatizados).

### Passo Único de Inicialização
No terminal, dentro da pasta do projeto, execute:
```bash
docker compose up -d --build
```

O ambiente estará pronto:
* **Load Balancer (Ponto de Entrada Único):** [http://localhost:8080](http://localhost:8080)
* **Instâncias Diretas (Prova Negativa):**
  * `app-01`: [http://localhost:3001](http://localhost:3001)
  * `app-02`: [http://localhost:3002](http://localhost:3002)
  * `app-03`: [http://localhost:3003](http://localhost:3003)

Para parar os containers ao final da apresentação:
```bash
docker compose down
```

---

##  Roteiro de Reprodução dos Testes (Seção 4)

Você pode executar todos os testes automaticamente com um único comando:
```powershell
powershell -ExecutionPolicy Bypass -File .\run_tests.ps1
```
Ou reproduzi-los manualmente passo a passo conforme exigido pelo professor:

### 1. Teste Visual de Alternância (Navegador)
1. Abra no navegador: [http://localhost:8080](http://localhost:8080).
2. Pressione `Ctrl + F5` (ou clique no botão **"Recarregar"** da página).
3. **Resultado Esperado:** A cada carregamento, a cor de fundo e o badge mudam ciclicamente:
   * `app-01` (Azul Safira)
   * `app-02` (Verde Esmeralda)
   * `app-03` (Laranja Âmbar)
4. *Dica para apresentação:* Ative a chave **"Alternância Automática (1s)"** para demonstrar o ciclo ao vivo sem precisar clicar.

### 2. Teste por Linha de Comando (curl e Cabeçalho `X-Served-By`)
Execute 6 requisições inspecionando o cabeçalho HTTP:
```powershell
for ($i = 1; $i -le 6; $i++) { (curl.exe -s -I http://localhost:8080/ | Select-String "X-Served-By").Line.Trim() }
```
**Resultado Esperado:**
```text
X-Served-By: app-01
X-Served-By: app-02
X-Served-By: app-03
X-Served-By: app-01
X-Served-By: app-02
X-Served-By: app-03
```

#### Prova Negativa Recomendada (Acesso Direto)
Acesse uma instância diretamente (sem passar pelo balanceador):
```powershell
for ($i = 1; $i -le 3; $i++) { (curl.exe -s -I http://localhost:3002/ | Select-String "X-Served-By").Line.Trim() }
```
**Resultado Esperado:** Retorna apenas `X-Served-By: app-02`, comprovando que a alternância é causada pelo NGINX.

### 3. Teste de Distribuição em Volume (100 Requisições)
Execute o script em Python que dispara 100 requisições e contabiliza o balanceamento:
```bash
python test_distribution.py --count 100
```
**Resultado Esperado:** Distribuição aproximadamente igualitária (~33% para cada instância), com 0 falhas:
```text
=================================================================
RESULTADO DA DISTRIBUICAO DE CARGA
=================================================================
Instancia       | Requisicoes  | Percentual   | Distribuicao
-----------------------------------------------------------------
app-01          | 33           |   33.0%     | #############
app-02          | 34           |   34.0%     | #############
app-03          | 33           |   33.0%     | #############
-----------------------------------------------------------------
Total executado:    100 requisicoes | Falhas: 0
```

### 4. Teste de Tolerância a Falhas
1. Derrube propositalmente o container `app-02`:
   ```bash
   docker stop app-02
   ```
2. Dispare um novo lote de requisições:
   ```bash
   python test_distribution.py --count 30
   ```
   **Resultado Esperado:** O serviço continua respondendo com **0 falhas** (100% de sucesso), dividindo a carga entre `app-01` e `app-03`.
3. Reative a instância:
   ```bash
   docker start app-02
   ```
4. Dispare mais requisições: `app-02` reingressa automaticamente no ciclo de balanceamento.

### 5. Teste de Escala Horizontal (Adicionando uma 4ª Instância)
1. Execute o script de escala:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scale_up.ps1
   ```
   *(Ele sobe o container `app-04`, atualiza o upstream do NGINX e faz `nginx -s reload` sem derrubar o balanceador).*
2. Verifique a nova distribuição entre 4 instâncias:
   ```bash
   python test_distribution.py --count 100
   ```
   **Resultado Esperado:** Cada uma das 4 instâncias atende exatamente ~25% das requisições (`app-01`, `app-02`, `app-03`, `app-04` na cor Roxo Ametista).
3. Para voltar ao cluster padrão de 3 instâncias:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scale_down.ps1
   ```

### 6. Evidência nos Logs
Exiba os logs de acesso do balanceador NGINX comprovando o repasse para cada IP upstream:
```bash
docker compose logs --tail=15 loadbalancer
```
**Resultado Esperado:** Linhas de log contendo `upstream=172.19.0.x:5000` demonstrando a alternância contínua entre as instâncias.

---

## 🔮 Como a Solução Poderia Evoluir

1. **Persistência de Sessão (Sticky Sessions vs. Sessões Stateless):**
   * *Problema:* Em aplicações tradicionais com login guardado em memória, a alternância do Round-Robin causa perda de sessão a cada requisição.
   * *Solução 1 (Sticky Sessions):* Configurar afinidade por cookie ou IP (`ip_hash` no NGINX). O cliente sempre é roteado para a mesma instância enquanto ela estiver saudável.
   * *Solução 2 (Arquitetura Stateless):* Armazenar as sessões em um repositório compartilhado externo (como **Redis** ou banco de dados) ou usar tokens **JWT** auto-contidos. Assim, qualquer instância pode atender qualquer requisição.

2. **Service Discovery e Adição Dinâmica de Nós:**
   * Em arquiteturas dinâmicas de microsserviços, novos nós surgem e morrem frequentemente. Em vez de editar arquivos de configuração estáticos, ferramentas como **Consul**, **Eureka** ou proxies nativos de nuvem (**Traefik**, **Kubernetes Ingress**) descobrem réplicas ativas via DNS/API sem necessidade de recarregar configurações manualmente.

3. **Auto Scaling Automático:**
   * Utilizar métricas de infraestrutura (CPU > 70%, uso de memória, latência p95 ou taxa de requisições por segundo via Prometheus) para disparar réplicas adicionais automaticamente (ex.: **HPA - Horizontal Pod Autoscaler** no Kubernetes ou AWS Auto Scaling Groups).

4. **Algoritmos Alternativos de Distribuição:**
   * `least_conn`: Encaminha a requisição para a instância com menor número de conexões ativas simultâneas (ideal para requisições de tempo de processamento heterogêneo).
   * `ip_hash`: Garante que requisições do mesmo IP cliente vão para o mesmo servidor.
   * `weighted`: Atribuição de pesos (`weight=3`), direcionando mais requisições para servidores com maior capacidade computacional.

5. **Terminação SSL/TLS e HTTP/2:**
   * Descarregar a criptografia HTTPS diretamente no NGINX, aliviando o processamento criptográfico das instâncias de aplicação e habilitando multiplexação de conexões com HTTP/2 ou HTTP/3 (QUIC).
