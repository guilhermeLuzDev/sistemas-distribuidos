Set-Location -Path $PSScriptRoot

# Restaura o cluster para 3 instâncias
if (Test-Path "nginx\nginx-3-instances.conf") {
    Copy-Item -Path "nginx\nginx-3-instances.conf" -Destination "nginx\nginx.conf" -Force
} else {
    $min3 = @"
events {}

http {
    upstream backend_servers {
        server app-01:5000;
        server app-02:5000;
        server app-03:5000;
    }

    server {
        listen 80;

        location / {
            proxy_pass http://backend_servers;
            proxy_next_upstream error timeout http_502;
        }

        location /health {
            proxy_pass http://backend_servers/health;
        }
    }
}
"@
    Set-Content -Path "nginx\nginx.conf" -Value $min3 -Force
}

docker compose stop app-04 | Out-Null
docker compose exec loadbalancer nginx -s reload | Out-Null
Write-Host "Cluster restaurado para 3 instancias com sucesso!" -ForegroundColor Green
