#!/usr/bin/env python3
"""Gerador procedural de assets de áudio para as 10 categorias canônicas do Atlas.

Gera arquivos WAV (PCM 16-bit, 44.1kHz) usando apenas a biblioteca padrão do Python.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


SAMPLE_RATE = 44100


def synthesize_tone(
    filename: Path,
    frequencies: list[tuple[float, float]],  # list of (freq_hz, duration_sec)
    amplitude: float = 0.5,
    attack_sec: float = 0.02,
    decay_sec: float = 0.05,
) -> None:
    filename.parent.mkdir(parents=True, exist_ok=True)
    total_frames = sum(int(SAMPLE_RATE * dur) for _, dur in frequencies)
    frames = bytearray()

    max_amplitude = 32767.0 * amplitude

    for freq, dur in frequencies:
        num_frames = int(SAMPLE_RATE * dur)
        for i in range(num_frames):
            t = float(i) / SAMPLE_RATE
            # Envelope linear simples de ataque e decaimento
            env = 1.0
            if t < attack_sec:
                env = t / attack_sec
            elif t > (dur - decay_sec):
                env = max(0.0, (dur - t) / decay_sec)

            val = math.sin(2.0 * math.pi * freq * t) * max_amplitude * env
            sample = int(max(-32768.0, min(32767.0, val)))
            frames.extend(struct.pack("<h", sample))

    with wave.open(str(filename), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(bytes(frames))


CATEGORIES = {
    "calm": [(440.0, 0.3), (554.37, 0.4)],
    "acknowledge": [(520.0, 0.08), (660.0, 0.12)],
    "working": [(330.0, 0.1), (330.0, 0.1)],
    "happy": [(523.25, 0.1), (659.25, 0.1), (783.99, 0.2)],
    "concerned": [(440.0, 0.2), (370.0, 0.3)],
    "annoyed": [(280.0, 0.1), (250.0, 0.15)],
    "critical": [(880.0, 0.15), (0.0, 0.05), (987.77, 0.25)],
    "relief": [(587.33, 0.25), (440.0, 0.35)],
    "confused": [(400.0, 0.1), (500.0, 0.1), (450.0, 0.15)],
    "victory": [(523.25, 0.1), (659.25, 0.1), (783.99, 0.1), (1046.50, 0.25)],
}


def generate_all(base_dir: Path | None = None) -> list[Path]:
    target_root = base_dir or Path(__file__).resolve().parent.parent / "assets" / "audio"
    generated: list[Path] = []
    for cat, freq_seq in CATEGORIES.items():
        out_file = target_root / cat / "tone_01.wav"
        synthesize_tone(out_file, freq_seq)
        generated.append(out_file)
    return generated


if __name__ == "__main__":
    files = generate_all()
    print(f"Gerados {len(files)} arquivos de áudio em {files[0].parent.parent}")
