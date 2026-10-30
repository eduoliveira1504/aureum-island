"""Theme: cores derivadas do accent e do fundo do notch escolhidos pelo usuário.

O notch é sempre escuro. A janela de Configurações tem o próprio esquema (`window`):
Escuro, Claro ou Sistema. Emite `changed` quando qualquer entrada muda, para a UI se
atualizar sem reiniciar.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor

from aureum_island.services.storage.settings import WINDOW_THEMES, Settings
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
    WINDOW_DARK,
    WINDOW_PALETTES,
    WindowPalette,
)


def qcolor(value: str) -> QColor:
    """'#RRGGBB' ou '#RRGGBBAA' -> QColor."""
    rgb = color.parse_hex(value[:7])
    alpha = int(value[7:9], 16) if len(value) == 9 else 255
    return QColor(*rgb, alpha)


@dataclass(frozen=True)
class WindowScheme:
    """Cores prontas da janela de Configurações (paleta + derivadas do accent)."""

    name: str  # dark | light
    palette: WindowPalette
    accent: str
    on_accent: str
    accent_text: str
    border_button: str
    border_divider: str

    def __getattr__(self, item: str) -> str:
        # panel, sidebar, surface, text, ... vêm da paleta.
        return getattr(self.palette, item)


class Theme(QObject):
    changed = Signal()

    def __init__(
        self,
        accent: str = DEFAULT_ACCENT,
        notch_bg: str = DEFAULT_NOTCH_BG,
        parent: QObject | None = None,
        *,
        window_theme: str = "dark",
        system_dark: bool = True,
    ) -> None:
        super().__init__(parent)
        self._accent = color.to_hex(color.parse_hex(accent))
        self._notch_bg_id = notch_bg if notch_bg in NOTCH_BACKGROUNDS else DEFAULT_NOTCH_BG
        self._window_theme = window_theme if window_theme in WINDOW_THEMES else "dark"
        self._system_dark = system_dark
        self._derive()

    @classmethod
    def from_settings(
        cls, settings: Settings, parent: QObject | None = None, *, system_dark: bool = True
    ) -> Theme:
        return cls(
            settings.accent,
            settings.notch_bg,
            parent,
            window_theme=settings.window_theme,
            system_dark=system_dark,
        )

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

    @property
    def window_theme(self) -> str:
        """Escolha do usuário: dark | light | system."""
        return self._window_theme

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

    def set_window_theme(self, window_theme: str) -> None:
        if window_theme not in WINDOW_THEMES:
            raise ValueError(f"tema desconhecido: {window_theme!r}")
        if window_theme != self._window_theme:
            self._window_theme = window_theme
            self._derive()
            self.changed.emit()

    def set_system_dark(self, dark: bool) -> None:
        """Esquema do Windows (só importa com o tema "system")."""
        if dark != self._system_dark:
            self._system_dark = dark
            if self._window_theme == "system":
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
        self.notch_scheme = self._scheme("dark", WINDOW_DARK, self.accent_text)
        name = self._window_theme
        if name == "system":
            name = "dark" if self._system_dark else "light"
        self.window = self.scheme_for(name)

    def scheme_for(self, name: str) -> WindowScheme:
        """Esquema da janela para `name` (dark | light) com o accent atual."""
        palette = WINDOW_PALETTES[name]
        surfaces = (palette.panel, palette.sidebar, palette.surface)
        text = color.accent_text(self._accent, surfaces, palette.accent_toward)
        return self._scheme(
            name,
            palette,
            text,
            color.with_alpha(text, palette.border_alpha_button),
            color.with_alpha(text, palette.border_alpha_divider),
        )

    def _scheme(
        self,
        name: str,
        palette: WindowPalette,
        accent_text: str,
        border_button: str | None = None,
        border_divider: str | None = None,
    ) -> WindowScheme:
        return WindowScheme(
            name=name,
            palette=palette,
            accent=self._accent,
            on_accent=self.on_accent,
            accent_text=accent_text,
            border_button=border_button or self.border_button,
            border_divider=border_divider or self.border_divider,
        )

    def q(self, value: str) -> QColor:
        return qcolor(value)
