"""Theme: as paletas do Aureum Voice re-tingidas pelo accent escolhido.

- `notch`: sempre a paleta escura re-tingida (o notch é sempre escuro).
- `window`: a janela de Configurações, no tema escolhido (Escuro, Claro ou Sistema).

Tudo é calculado só quando o accent ou o tema mudam, nunca por frame. Emite `changed`
para a UI repintar sem reiniciar. Ver docs/decisions/0009.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor

from aureum_island.services.storage.settings import WINDOW_THEMES, Settings
from aureum_island.theme import color
from aureum_island.theme.tokens import (
    BORDER_ALPHA_MINIMAL,
    BORDER_ALPHA_NOTCH,
    DEFAULT_ACCENT,
    ON_DANGER,
    PALETTES,
    RETINT_REFERENCE,
    SUBTLE_MUTED_WEIGHT,
)


def qcolor(value: str) -> QColor:
    """'#RRGGBB' ou '#RRGGBBAA' -> QColor."""
    rgb = color.parse_hex(value[:7])
    alpha = int(value[7:9], 16) if len(value) == 9 else 255
    return QColor(*rgb, alpha)


@dataclass(frozen=True)
class Scheme:
    """Cores prontas de um tema. Fundos, borda e texto já re-tingidos pelo accent.

    Os `*_text` são as versões legíveis (≥ 4.5:1 contra os quatro fundos) de cores que
    também existem como preenchimento: fg-subtle, success, danger e o accent.
    """

    name: str  # dark | light
    rail: str
    panel: str
    main: str
    elevated: str
    border: str
    text: str
    text_muted: str
    subtle: str  # fg-subtle como no Voice (preenchimento; texto desabilitado)
    subtle_text: str
    success: str
    success_text: str
    danger: str
    danger_text: str
    on_danger: str
    accent: str
    on_accent: str
    accent_text: str
    accent_hover: str

    @property
    def surfaces(self) -> tuple[str, str, str, str]:
        return self.rail, self.panel, self.main, self.elevated


def build_scheme(name: str, accent: str) -> Scheme:
    """Paleta `name` do Voice re-tingida para `accent`, com as cores derivadas."""
    p = PALETTES[name]

    def tint(value: str) -> str:
        return color.retint(value, accent, RETINT_REFERENCE)

    rail, panel, main, elevated = (
        tint(c) for c in (p.bg_rail, p.bg_panel, p.bg_main, p.bg_elevated)
    )
    surfaces = (rail, panel, main, elevated)
    text_muted = tint(p.text_muted)
    subtle = color.mix_oklab(text_muted, main, SUBTLE_MUTED_WEIGHT)
    return Scheme(
        name=name,
        rail=rail,
        panel=panel,
        main=main,
        elevated=elevated,
        border=tint(p.border),
        text=tint(p.text),
        text_muted=text_muted,
        subtle=subtle,
        subtle_text=color.readable_on(subtle, surfaces),
        success=p.success,
        success_text=color.readable_on(p.success, surfaces),
        danger=p.danger,
        danger_text=color.readable_on(p.danger, surfaces),
        on_danger=ON_DANGER,
        **_accent_colors(name, accent, surfaces),
    )


def _accent_colors(name: str, accent: str, surfaces: tuple[str, ...]) -> dict[str, str]:
    p = PALETTES[name]
    return {
        "accent": accent,
        "on_accent": color.ink_on(accent),
        "accent_text": color.readable_on(accent, surfaces),
        "accent_hover": color.mix_oklab(accent, p.accent_hover_mix, 1 - p.accent_hover_amount),
    }


class Theme(QObject):
    changed = Signal()

    def __init__(
        self,
        accent: str = DEFAULT_ACCENT,
        parent: QObject | None = None,
        *,
        window_theme: str = "dark",
        system_dark: bool = True,
    ) -> None:
        super().__init__(parent)
        self._accent = color.to_hex(color.parse_hex(accent))
        self._window_theme = window_theme if window_theme in WINDOW_THEMES else "dark"
        self._system_dark = system_dark
        self._previewing = False
        self._derive()

    @classmethod
    def from_settings(
        cls, settings: Settings, parent: QObject | None = None, *, system_dark: bool = True
    ) -> Theme:
        return cls(
            settings.accent, parent, window_theme=settings.window_theme, system_dark=system_dark
        )

    # --- entradas -----------------------------------------------------------

    @property
    def accent(self) -> str:
        """Accent em uso (durante a prévia do seletor, a cor sendo arrastada)."""
        return self.notch.accent

    @property
    def window_theme(self) -> str:
        """Escolha do usuário: dark | light | system."""
        return self._window_theme

    def set_accent(self, accent: str) -> None:
        accent = color.to_hex(color.parse_hex(accent))
        if accent != self._accent or self._previewing:
            self._accent = accent
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

    def preview_accent(self, accent: str) -> None:
        """Enquanto o seletor de cor é arrastado: troca só accent, on-accent, accent-text
        e hover, sem re-tingir a paleta e sem salvar (como o previewAccent do Voice)."""
        accent = color.to_hex(color.parse_hex(accent))
        self._previewing = True
        self.notch = replace(self.notch, **_accent_colors("dark", accent, self.notch.surfaces))
        self.window = replace(
            self.window, **_accent_colors(self.window.name, accent, self.window.surfaces)
        )
        self._derive_notch_borders()
        self.changed.emit()

    def end_preview(self) -> None:
        """Seletor fechado sem escolher: volta tudo para a cor salva."""
        if self._previewing:
            self._derive()
            self.changed.emit()

    # --- derivadas ----------------------------------------------------------

    @property
    def window_scheme_name(self) -> str:
        if self._window_theme == "system":
            return "dark" if self._system_dark else "light"
        return self._window_theme

    def _derive(self) -> None:
        self._previewing = False
        self.notch = build_scheme("dark", self._accent)
        name = self.window_scheme_name
        self.window = self.notch if name == "dark" else build_scheme(name, self._accent)
        self._derive_notch_borders()

    def _derive_notch_borders(self) -> None:
        # Contorno do notch aberto e linha mínima continuam com o accent (marca do notch).
        self.border_notch = color.with_alpha(self.notch.accent, BORDER_ALPHA_NOTCH)
        self.border_minimal = color.with_alpha(self.notch.accent, BORDER_ALPHA_MINIMAL)

    # Atalhos do notch (sempre escuro), para o código das páginas.
    @property
    def notch_bg(self) -> str:
        return self.notch.rail

    @property
    def on_accent(self) -> str:
        return self.notch.on_accent

    @property
    def accent_text(self) -> str:
        return self.notch.accent_text

    @property
    def accent_hover(self) -> str:
        return self.notch.accent_hover
