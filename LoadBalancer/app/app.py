import os
import socket
from datetime import datetime
from flask import Flask, render_template, jsonify

from zoneinfo import ZoneInfo

app = Flask(__name__)

# Lê o identificador da variável de ambiente (conforme exigido pelo PDF)
INSTANCE_ID = os.environ.get("INSTANCE_ID", socket.gethostname())

# Cores simples sugeridas no enunciado (app-01 azul, app-02 verde, app-03 laranja, app-04 roxo)
COLORS = {
    "app-01": "#2563eb",  # Azul
    "app-02": "#16a34a",  # Verde
    "app-03": "#ea580c",  # Laranja
    "app-04": "#9333ea",  # Roxo
}

@app.after_request
def add_headers(response):
    # Injeta o cabeçalho X-Served-By e desativa cache
    response.headers["X-Served-By"] = INSTANCE_ID
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response

@app.route("/")
def index():
    color = COLORS.get(INSTANCE_ID, "#334155")
    hostname = socket.gethostname()
    server_time = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
    return render_template(
        "index.html",
        instance_id=INSTANCE_ID,
        color=color,
        hostname=hostname,
        server_time=server_time
    )

@app.route("/health")
def health():
    return jsonify({"status": "UP", "instance_id": INSTANCE_ID}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
