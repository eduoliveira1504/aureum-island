"""Ícones SVG próprios (assets/icons), coloridos pelo tema em runtime."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


@lru_cache(maxsize=16)
def _svg_source(name: str) -> str:
    return resources.files("aureum_island.assets.icons").joinpath(f"{name}.svg").read_text("utf-8")


@lru_cache(maxsize=128)
def pixmap(name: str, color: str, size: int, device_pixel_ratio: float = 1.0) -> QPixmap:
    """Ícone `name` em `color` ('#RRGGBB'), `size` em pixels lógicos."""
    data = _svg_source(name).replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))
    physical = max(1, round(size * device_pixel_ratio))
    pm = QPixmap(physical, physical)
    pm.fill(Qt.GlobalColor.transparent)
    pm.setDevicePixelRatio(device_pixel_ratio)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pm


def icon(name: str, color: str, size: int) -> QIcon:
    result = QIcon()
    for ratio in (1.0, 1.25, 1.5, 2.0):
        result.addPixmap(pixmap(name, color, size, ratio))
    return result
