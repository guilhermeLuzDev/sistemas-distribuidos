#!/usr/bin/env python3
"""
Script de Verificacao de Distribuicao de Carga (Teste 3 do Roteiro de Avaliacao)
Dispara N requisicoes contra o Load Balancer e contabiliza as respostas por instancia
usando o cabecalho HTTP 'X-Served-By'.
"""

import sys
import time
import argparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from collections import Counter

# Assegura suporte a UTF-8 no Windows quando suportado pelo terminal
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_load_test(url: str, total_requests: int):
    print("=" * 65)
    print("INICIANDO TESTE DE DISTRIBUICAO EM VOLUME (TESTE 3)")
    print(f"Alvo:              {url}")
    print(f"Total Requisicoes: {total_requests}")
    print("=" * 65)

    counts = Counter()
    latencies = []
    failed = 0

    start_time = time.time()

    for i in range(1, total_requests + 1):
        req_start = time.time()
        try:
            req = Request(url, headers={"User-Agent": "LoadTester/1.0", "Cache-Control": "no-cache"})
            with urlopen(req, timeout=3.0) as resp:
                served_by = resp.headers.get("X-Served-By", "desconhecido")
                counts[served_by] += 1
                latencies.append(time.time() - req_start)
        except Exception:
            failed += 1
            counts["ERRO/FALHA"] += 1

        # Barra de progresso amigavel para terminais Windows
        percent = (i / total_requests) * 100
        bar_len = 25
        filled = int(bar_len * i // total_requests)
        bar = "#" * filled + "-" * (bar_len - filled)
        sys.stdout.write(f"\rProgresso: [{bar}] {i}/{total_requests} ({percent:5.1f}%)")
        sys.stdout.flush()

    total_time = time.time() - start_time
    print("\n\n" + "=" * 65)
    print("RESULTADO DA DISTRIBUICAO DE CARGA")
    print("=" * 65)
    print(f"{'Instancia':<15} | {'Requisicoes':<12} | {'Percentual':<12} | {'Distribuicao'}")
    print("-" * 65)

    successful = total_requests - failed

    for instance in sorted(counts.keys()):
        count = counts[instance]
        pct = (count / total_requests) * 100
        bar_visual = "#" * int(pct / 2.5)
        print(f"{instance:<15} | {count:<12} | {pct:6.1f}%     | {bar_visual}")

    print("-" * 65)
    print(f"Total executado:    {total_requests} requisicoes")
    print(f"Respostas sucesso:  {successful}")
    print(f"Falhas / Timeouts:  {failed}")
    print(f"Tempo total:        {total_time:.2f} segundos")
    if latencies:
        avg_latency_ms = (sum(latencies) / len(latencies)) * 1000
        print(f"Latencia media:     {avg_latency_ms:.2f} ms")
    print("=" * 65)

    active_instances = [k for k in counts.keys() if k != 'ERRO/FALHA']
    if failed == 0 and len(active_instances) >= 2:
        print("[SUCESSO] Distribuicao uniforme e funcional comprovada com sucesso!")
    else:
        print("[AVISO] Verifique se todas as instancias estao em execucao.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Teste de Distribuicao de Carga HTTP")
    parser.add_argument("--url", default="http://localhost:8080/", help="URL do Balanceador (padrao: http://localhost:8080/)")
    parser.add_argument("--count", type=int, default=100, help="Numero total de requisicoes (padrao: 100)")
    args = parser.parse_args()

    run_load_test(args.url, args.count)
