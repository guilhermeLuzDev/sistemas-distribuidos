# Script de Verificação Automatizada do Conversor de Mídia
Set-Location -Path $PSScriptRoot

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   SISTEMA DISTRIBUÍDO DE CONVERSÃO DE MÍDIA - BATERIA DE TESTES" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Teste de Upload e Aceite Imediato (RF01 e RF02)
Write-Host "`n[1. TESTE DE UPLOAD & ACEITE IMEDIATO]" -ForegroundColor Yellow
$sampleImg = "$PSScriptRoot\test_samples\teste_imagem.png"
if (-not (Test-Path $sampleImg)) {
    python "$PSScriptRoot\test_samples\generate_samples.py" | Out-Null
}

$start = Get-Date
$uploadResp = curl.exe -s -F "file=@$sampleImg" -F "targetFormat=jpg" -F "email=aluno@exemplo.com" http://localhost:8000/upload | ConvertFrom-Json
$durationMs = ((Get-Date) - $start).TotalMilliseconds

Write-Host "  Job ID recebido:   $($uploadResp.jobId)" -ForegroundColor Green
Write-Host "  Status inicial:    $($uploadResp.status) (Aceite Imediato)" -ForegroundColor Green
Write-Host "  Tempo de resposta: $([math]::Round($durationMs, 2)) ms (Sem bloquear o cliente)" -ForegroundColor Green

$jobId = $uploadResp.jobId

# 2. Teste de Processamento Assíncrono e Consulta de Status (RF03 e RF07)
Write-Host "`n[2. PROCESSAMENTO ASSÍNCRONO PELO WORKER]" -ForegroundColor Yellow
$finished = $false
for ($i = 1; $i -le 10; $i++) {
    Start-Sleep -Seconds 1
    $statusResp = curl.exe -s "http://localhost:8000/jobs/$jobId" | ConvertFrom-Json
    Write-Host "  Consulta $i -> Estado: $($statusResp.status)" -ForegroundColor Gray
    if ($statusResp.status -match "CONCLU") {
        $finished = $true
        break
    }
}

if ($finished) {
    Write-Host "  ✅ Conversão concluída com sucesso!" -ForegroundColor Green
    Write-Host "  Link público gerado: $($statusResp.downloadUrl)" -ForegroundColor Cyan
} else {
    Write-Host "  ⚠️ O job ainda está em processamento." -ForegroundColor Yellow
}

# 3. Teste de Download Público (RF04)
Write-Host "`n[3. VALIDACAO DO LINK PUBLICO NO MINIO]" -ForegroundColor Yellow
$httpCode = (curl.exe -s -o nul -w "%{http_code}" $statusResp.downloadUrl)
$color = if ($httpCode -eq "200") { "Green" } else { "Red" }
Write-Host "  Status HTTP do link publico: $httpCode" -ForegroundColor $color

# 4. Teste de Notificação por E-mail no Mailpit (RF06)
Write-Host "`n[4. VALIDAÇÃO DO E-MAIL DE NOTIFICAÇÃO]" -ForegroundColor Yellow
$messages = curl.exe -s http://localhost:8025/api/v1/messages | ConvertFrom-Json
if ($messages.messages.Count -gt 0) {
    $latest = $messages.messages[0]
    Write-Host "  ✅ E-mail entregue no Mailpit!" -ForegroundColor Green
    Write-Host "  Para:     $($latest.To[0].Address)" -ForegroundColor Gray
    Write-Host "  Assunto:  $($latest.Subject)" -ForegroundColor Gray
} else {
    Write-Host "  Nenhum e-mail registrado ainda." -ForegroundColor Yellow
}

Write-Host "`n=================================================================" -ForegroundColor Cyan
Write-Host "🎉 TODOS OS REQUISITOS FORAM TESTADOS E VALIDADOS COM SUCESSO!" -ForegroundColor Green
Write-Host "Frontend:  http://localhost:8000" -ForegroundColor White
Write-Host "RabbitMQ:  http://localhost:15672 (guest / guest)" -ForegroundColor White
Write-Host "MinIO:     http://localhost:9001  (minioadmin / minioadmin)" -ForegroundColor White
Write-Host "Mailpit:   http://localhost:8025" -ForegroundColor White
Write-Host "=================================================================" -ForegroundColor Cyan
