"""Registro das fontes empacotadas (Inter e Cinzel, OFL)."""

from __future__ import annotations

import logging
from importlib import resources

from PySide6.QtGui import QFontDatabase

log = logging.getLogger(__name__)

FONT_FILES = ("Inter[opsz,wght].ttf", "Cinzel[wght].ttf")


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
