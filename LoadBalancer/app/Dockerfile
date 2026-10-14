FROM python:3.11-slim

# Evita geração de bytecode .pyc e ativa saída imediata de logs no terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalação das dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cópia do código-fonte e templates
COPY app.py .
COPY templates ./templates

# Exposição da porta da aplicação
EXPOSE 5000

# Execução com Gunicorn com 1 worker por container
# Conforme exigido: múltiplos containers independentes representam as instâncias
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--access-logfile", "-", "app:app"]
