"""Gera a faixa fictícia usada nos prints da página Música (não vai para o repo).

    .venv\\Scripts\\python scripts\\make_demo_track.py <saida.mp3>

MP3 de silêncio (3:30) com tag ID3: título "Faixa de demonstração", artista "Aureum" e uma
capa original (logo da Aureum sobre fundo escuro com hexágonos). Sem lib extra: os quadros
MP3 vazios decodificam como silêncio, e a capa é desenhada pelo Qt. Toque o arquivo no Media
Player do Windows para o SMTC mostrar a faixa no notch.
"""

from __future__ import annotations

import math
import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TITLE = "Faixa de demonstração"
ARTIST = "Aureum"
ALBUM = "Aureum Island"
SECONDS = 210
COVER_SIZE = 600

# MPEG-1 Layer III, 128 kbps, 44,1 kHz, estéreo, sem CRC. Com o resto do quadro zerado,
# nenhum dado de áudio: o decodificador toca silêncio.
_FRAME_HEADER = bytes([0xFF, 0xFB, 0x90, 0x04])
_FRAME_SIZE = 144 * 128_000 // 44_100  # 417 bytes
_FRAMES_PER_SECOND = 44_100 / 1152


def render_cover() -> bytes:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT / "src"))
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
    from PySide6.QtGui import (
        QColor,
        QGuiApplication,
        QImage,
        QPainter,
        QPen,
        QPolygonF,
        QRadialGradient,
    )
    from PySide6.QtSvg import QSvgRenderer

    from aureum_island.theme.tokens import DARK, DEFAULT_ACCENT

    _app = QGuiApplication.instance() or QGuiApplication([])
    size = COVER_SIZE
    image = QImage(size, size, QImage.Format.Format_RGB32)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    glow = QRadialGradient(QPointF(size * 0.5, size * 0.42), size * 0.75)
    accent = QColor(DEFAULT_ACCENT)
    deep = QColor(DARK.bg_rail)
    glow.setColorAt(0, QColor.fromRgbF(accent.redF() * 0.28, accent.greenF() * 0.2, 0.03))
    glow.setColorAt(1, deep)
    p.fillRect(image.rect(), glow)

    # Hexágonos de fundo, bem fracos.
    line = QColor(accent)
    line.setAlphaF(0.09)
    p.setPen(QPen(line, 1.5))
    r = 34
    w, h = math.sqrt(3) * r, 1.5 * r
    for row in range(-1, int(size / h) + 2):
        for col in range(-1, int(size / w) + 2):
            cx = col * w + (w / 2 if row % 2 else 0)
            cy = row * h
            hexagon = QPolygonF(
                [
                    QPointF(
                        cx + r * math.cos(math.radians(60 * k - 30)),
                        cy + r * math.sin(math.radians(60 * k - 30)),
                    )
                    for k in range(6)
                ]
            )
            p.drawPolygon(hexagon)

    svg = (ROOT / "docs/design/brand/logo.svg").read_bytes()
    logo = QSvgRenderer(QByteArray(svg))
    side = size * 0.46
    p.setPen(Qt.PenStyle.NoPen)
    logo.render(p, QRectF((size - side) / 2, (size - side) / 2, side, side))
    p.end()

    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    return bytes(data)


def _syncsafe(n: int) -> bytes:
    return bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])


def _frame(frame_id: str, payload: bytes) -> bytes:
    # ID3v2.3: tamanho do quadro em inteiro normal (não syncsafe).
    return frame_id.encode("ascii") + struct.pack(">I", len(payload)) + b"\x00\x00" + payload


def _text(frame_id: str, value: str) -> bytes:
    return _frame(frame_id, b"\x01" + value.encode("utf-16"))  # UTF-16 com BOM


def id3_tag(cover_png: bytes) -> bytes:
    apic = b"\x00" + b"image/png\x00" + b"\x03" + b"\x00" + cover_png  # 3 = capa
    frames = (
        _text("TIT2", TITLE) + _text("TPE1", ARTIST) + _text("TALB", ALBUM) + _frame("APIC", apic)
    )
    return b"ID3\x03\x00\x00" + _syncsafe(len(frames)) + frames


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out = Path(sys.argv[1])
    frame = _FRAME_HEADER + bytes(_FRAME_SIZE - len(_FRAME_HEADER))
    count = round(SECONDS * _FRAMES_PER_SECOND)
    out.write_bytes(id3_tag(render_cover()) + frame * count)
    print(f"{out} ({out.stat().st_size // 1024} KB, {SECONDS} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
