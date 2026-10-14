Set-Location -Path $PSScriptRoot

Write-Host ">>> Iniciando escala horizontal: Adicionando app-04 ao cluster..." -ForegroundColor Cyan

# 1. Copia a configuração com 4 instâncias para a ativa
Copy-Item -Path "nginx\nginx-4-instances.conf" -Destination "nginx\nginx.conf" -Force

# 2. Sobe a 4ª instância usando o profile 'scale'
docker compose --profile scale up -d app-04

# Aguarda 1 segundo para o container estabilizar
Start-Sleep -Seconds 1

# 3. Recarrega as configurações do NGINX sem derrubar o serviço (zero downtime)
docker compose exec loadbalancer nginx -s reload

Write-Host ">>> Escala concluída! A instância app-04 agora está recebendo requisições." -ForegroundColor Green
Write-Host ">>> Execute 'python test_distribution.py' para comprovar a distribuição entre 4 instâncias." -ForegroundColor Yellow
