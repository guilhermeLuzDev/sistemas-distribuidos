#!/usr/bin/env python3
"""
Gera arquivos de teste leves (Imagem PNG, Áudio WAV e Vídeo MP4)
para testar imediatamente a conversão sem precisar caçar arquivos no PC.
"""

import os
import math
import struct
import wave
from pathlib import Path
from PIL import Image, ImageDraw

OUTPUT_DIR = Path(__file__).parent
OUTPUT_DIR.mkdir(exist_ok=True)

def generate_image():
    img_path = OUTPUT_DIR / "teste_imagem.png"
    img = Image.new("RGBA", (300, 300), color=(37, 99, 235, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 250, 250], fill=(22, 163, 74, 255))
    draw.ellipse([80, 80, 220, 220], fill=(234, 88, 12, 255))
    img.save(img_path)
    print(f"[OK] Imagem gerada: {img_path.name}")

def generate_audio():
    wav_path = OUTPUT_DIR / "teste_audio.wav"
    sample_rate = 44100
    duration = 2.0  # 2 segundos
    frequency = 440.0  # Tom Lá (A4)
    num_samples = int(sample_rate * duration)

    with wave.open(str(wav_path), "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        for i in range(num_samples):
            value = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
            data = struct.pack("<h", value)
            wav_file.writeframesraw(data)

    print(f"[OK] Audio gerado:  {wav_path.name}")

if __name__ == "__main__":
    generate_image()
    generate_audio()
    print("Arquivos de demonstração prontos na pasta test_samples!")
