"""Gera os sons do Aureum Island com síntese aditiva, só com a stdlib (wave + math).

Uso: python scripts/generate_sounds.py
Saída: src/aureum_island/assets/sounds/chime.wav (© Aureum, ver LICENSES.md).
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RATE = 44_100
OUT = Path(__file__).resolve().parents[1] / "src" / "aureum_island" / "assets" / "sounds"

# Sino suave: fundamental + parciais levemente inarmônicos, cada um com seu decaimento.
# (razão da frequência, amplitude, tempo de decaimento em s)
PARTIALS = (
    (1.000, 1.00, 0.42),
    (2.010, 0.42, 0.26),
    (2.990, 0.20, 0.18),
    (4.170, 0.10, 0.11),
    (5.430, 0.05, 0.07),
)


def chime(base_hz: float = 880.0, seconds: float = 0.6, gain: float = 0.32) -> list[float]:
    total = int(RATE * seconds)
    attack = int(RATE * 0.006)  # 6 ms de ataque: sem clique
    release = int(RATE * 0.05)  # 50 ms finais até o silêncio
    samples = []
    for n in range(total):
        t = n / RATE
        value = sum(
            amp * math.exp(-t / decay) * math.sin(2 * math.pi * base_hz * ratio * t)
            for ratio, amp, decay in PARTIALS
        )
        env = min(1.0, n / attack) * min(1.0, (total - n) / release)
        samples.append(value * env)
    peak = max(abs(s) for s in samples)
    return [s / peak * gain for s in samples]


def write_wav(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(b"".join(struct.pack("<h", round(s * 32767)) for s in samples))


if __name__ == "__main__":
    target = OUT / "chime.wav"
    write_wav(target, chime())
    print(f"gerado: {target}")
