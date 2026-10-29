"""Theme: cores derivadas do accent e do fundo do notch escolhidos pelo usuário.

Emite `changed` quando o accent ou o fundo mudam, para a UI se atualizar sem reiniciar.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor

from aureum_island.services.storage.settings import Settings
from aureum_island.theme import color
from aureum_island.theme.tokens import (
    BORDER_ALPHA_BUTTON,
    BORDER_ALPHA_DIVIDER,
    BORDER_ALPHA_MINIMAL,
    BORDER_ALPHA_NOTCH,
    COLORS,
    DEFAULT_ACCENT,
    DEFAULT_NOTCH_BG,
    NOTCH_BACKGROUNDS,
)


def qcolor(value: str) -> QColor:
    """'#RRGGBB' ou '#RRGGBBAA' -> QColor."""
    rgb = color.parse_hex(value[:7])
    alpha = int(value[7:9], 16) if len(value) == 9 else 255
    return QColor(*rgb, alpha)


class Theme(QObject):
    changed = Signal()

    def __init__(
        self,
        accent: str = DEFAULT_ACCENT,
        notch_bg: str = DEFAULT_NOTCH_BG,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._accent = color.to_hex(color.parse_hex(accent))
        self._notch_bg_id = notch_bg if notch_bg in NOTCH_BACKGROUNDS else DEFAULT_NOTCH_BG
        self._derive()

    @classmethod
    def from_settings(cls, settings: Settings, parent: QObject | None = None) -> Theme:
        return cls(settings.accent, settings.notch_bg, parent)

    # --- entradas -----------------------------------------------------------

    @property
    def accent(self) -> str:
        return self._accent

    @property
    def notch_bg_id(self) -> str:
        return self._notch_bg_id

    @property
    def notch_bg(self) -> str:
        return NOTCH_BACKGROUNDS[self._notch_bg_id][1]

    def set_accent(self, accent: str) -> None:
        accent = color.to_hex(color.parse_hex(accent))
        if accent != self._accent:
            self._accent = accent
            self._derive()
            self.changed.emit()

    def set_notch_bg(self, notch_bg_id: str) -> None:
        if notch_bg_id not in NOTCH_BACKGROUNDS:
            raise ValueError(f"fundo do notch desconhecido: {notch_bg_id!r}")
        if notch_bg_id != self._notch_bg_id:
            self._notch_bg_id = notch_bg_id
            self._derive()
            self.changed.emit()

    # --- derivadas ----------------------------------------------------------

    def _derive(self) -> None:
        surfaces = (self.notch_bg, COLORS.surface, COLORS.panel, COLORS.sidebar)
        self.on_accent = color.on_accent(self._accent)
        self.accent_text = color.accent_text(self._accent, surfaces)
        self.border_notch = color.with_alpha(self._accent, BORDER_ALPHA_NOTCH)
        self.border_divider = color.with_alpha(self._accent, BORDER_ALPHA_DIVIDER)
        self.border_button = color.with_alpha(self._accent, BORDER_ALPHA_BUTTON)
        self.border_minimal = color.with_alpha(self._accent, BORDER_ALPHA_MINIMAL)

    def q(self, value: str) -> QColor:
        return qcolor(value)
