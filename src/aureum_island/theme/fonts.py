"""Registro das fontes empacotadas (Sora e Figtree, variáveis, OFL), as mesmas do Aureum Voice."""

from __future__ import annotations

import logging
from importlib import resources

from PySide6.QtGui import QFont, QFontDatabase

log = logging.getLogger(__name__)

FONT_FILES = ("Figtree[wght].ttf", "Sora[wght].ttf")


def register_fonts() -> list[str]:
    """Registra as fontes no QFontDatabase. Precisa de um QGuiApplication criado.

    Devolve as famílias registradas. Falha em uma fonte é logada, sem quebrar o app.
    """
    families: list[str] = []
    base = resources.files("aureum_island.assets.fonts")
    for name in FONT_FILES:
        data = base.joinpath(name).read_bytes()
        font_id = QFontDatabase.addApplicationFontFromData(data)
        if font_id < 0:
            log.warning("não foi possível registrar a fonte %s", name)
            continue
        families.extend(QFontDatabase.applicationFontFamilies(font_id))
    # Fontes variáveis listam a família uma vez por instância nomeada.
    return list(dict.fromkeys(families))


def make_font(
    family: str,
    pixel_size: int,
    weight: int = 400,
    *,
    tabular: bool = False,
    letter_spacing_em: float = 0.0,
) -> QFont:
    """QFont em pixels lógicos. `tabular` liga tabular-nums; espaçamento em em."""
    font = QFont(family)
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight(weight))
    if tabular:
        font.setFeature(QFont.Tag("tnum"), 1)
    if letter_spacing_em:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, letter_spacing_em * pixel_size)
    return font
