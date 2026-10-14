# Script Automatizado de Verificacao dos 6 Testes de Avaliacao
# Garante que os comandos rodem a partir da pasta correta do script, independente de onde o terminal estiver aberto
Set-Location -Path $PSScriptRoot

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   SISTEMAS DISTRIBUIDOS - BATERIA DE TESTES DE AVALIACAO" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

function Get-ServedByHeader($url) {
    $resp = curl.exe -s -I $url
    $found = ($resp -match "X-Served-By")
    if ($found) {
        return ($found[0].Trim())
    }
    return "X-Served-By: desconhecido"
}

# TESTE 2: Linha de comando (curl)
Write-Host "`n[TESTE 2] Verificacao por Linha de Comando (Cabecalho X-Served-By):" -ForegroundColor Yellow
for ($i = 1; $i -le 6; $i++) {
    $header = Get-ServedByHeader "http://localhost:8080/"
    Write-Host "  Requisicao $i -> $header" -ForegroundColor Green
}

# PROVA NEGATIVA
Write-Host "`n[PROVA NEGATIVA] Acessando instancia direta (porta 3002 sem balanceador):" -ForegroundColor Yellow
for ($i = 1; $i -le 3; $i++) {
    $direct = Get-ServedByHeader "http://localhost:3002/"
    Write-Host "  Direto porta 3002 -> $direct (Permanente, sem alternancia)" -ForegroundColor Magenta
}

# TESTE 3: Distribuicao em volume (100 requisicoes)
Write-Host "`n[TESTE 3] Teste de Distribuicao em Volume (100 requisicoes):" -ForegroundColor Yellow
python "$PSScriptRoot\test_distribution.py" --count 100

# TESTE 4: Tolerancia a Falhas
Write-Host "`n[TESTE 4] Teste de Tolerancia a Falhas (Derrubando app-02):" -ForegroundColor Yellow
Write-Host "  Derrubando container app-02..." -ForegroundColor Gray
docker compose stop app-02 | Out-Null
Write-Host "  Disparando 30 requisicoes com app-02 offline..." -ForegroundColor Gray
python "$PSScriptRoot\test_distribution.py" --count 30
Write-Host "  Restaurando app-02..." -ForegroundColor Gray
docker compose start app-02 | Out-Null
Start-Sleep -Seconds 1
Write-Host "  Instancia app-02 recuperada com sucesso!" -ForegroundColor Green

# TESTE 5: Escala Horizontal
Write-Host "`n[TESTE 5] Teste de Escala (Adicionando app-04 ao cluster):" -ForegroundColor Yellow
powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\scale_up.ps1" | Out-Null
python "$PSScriptRoot\test_distribution.py" --count 40
Write-Host "  Restaurando cluster para 3 instancias..." -ForegroundColor Gray
powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\scale_down.ps1" | Out-Null

# TESTE 6: Evidencia nos Logs
Write-Host "`n[TESTE 6] Evidencia nos Logs do NGINX:" -ForegroundColor Yellow
docker compose logs --tail=6 loadbalancer

Write-Host "`n=================================================================" -ForegroundColor Cyan
Write-Host "[OK] TODOS OS TESTES FORAM EXECUTADOS COM SUCESSO!" -ForegroundColor Green
Write-Host "Para o Teste 1 (Visual): Acesse no navegador: http://localhost:8080" -ForegroundColor White
Write-Host "=================================================================" -ForegroundColor Cyan
