"""Tokens de design do Aureum Island (fonte: docs/DESIGN.md).

Nenhuma cor, fonte ou medida da UI deve ficar fora deste módulo.
Medidas em pixels lógicos; o Qt converte para o DPI do monitor.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Cores -------------------------------------------------------------------


@dataclass(frozen=True)
class Colors:
    notch_bg: str = "#070605"
    surface: str = "#14110D"
    panel: str = "#0D0B09"
    sidebar: str = "#090806"
    text: str = "#F1E8D3"
    text_muted: str = "#A89F88"
    text_dim: str = "#8F866F"
    track: str = "#2A2419"
    danger_bg: str = "#5A2620"
    danger_text: str = "#F6D5CE"
    on_accent_dark: str = "#0A0908"
    on_accent_light: str = "#FFFFFF"


COLORS = Colors()

# Opacidades das bordas derivadas do accent.
BORDER_ALPHA_NOTCH = 0.20
BORDER_ALPHA_DIVIDER = 0.14
BORDER_ALPHA_BUTTON = 0.30
BORDER_ALPHA_MINIMAL = 0.55

# Contraste mínimo exigido para texto (WCAG AA).
MIN_TEXT_CONTRAST = 4.5

# Presets de destaque (mesmos do Aureum Voice). Chave = id salvo no settings.json.
ACCENT_PRESETS: dict[str, tuple[str, str]] = {
    "dourado": ("Dourado", "#E8B531"),
    "ametista": ("Ametista", "#8B5CF6"),
    "esmeralda": ("Esmeralda", "#3FBF7F"),
    "brasa": ("Brasa", "#E06A4E"),
    "safira": ("Safira", "#4F8CC9"),
}
DEFAULT_ACCENT = ACCENT_PRESETS["dourado"][1]

# Fundos do notch. Todos com contraste >= 4.5 para text, text-muted e text-dim.
NOTCH_BACKGROUNDS: dict[str, tuple[str, str]] = {
    "preto": ("Preto", "#070605"),
    "marrom": ("Marrom escuro", "#1A120C"),
    "grafite": ("Grafite", "#1C1915"),
}
DEFAULT_NOTCH_BG = "preto"

# --- Tipografia --------------------------------------------------------------


@dataclass(frozen=True)
class Typography:
    family_title: str = "Cinzel"
    family_body: str = "Inter"
    title_letter_spacing_em: float = 0.18
    title_size_sm: int = 10
    title_size_md: int = 11
    body_size_min: int = 12
    body_size_max: int = 15
    clock_size: int = 13
    clock_weight: int = 600
    date_size: int = 11
    pomodoro_clock_size: int = 28
    pomodoro_clock_weight: int = 600


TYPOGRAPHY = Typography()

# --- Notch -------------------------------------------------------------------


@dataclass(frozen=True)
class Notch:
    closed_width: int = 190
    closed_height: int = 34
    closed_radius: int = 18
    minimal_width: int = 150
    minimal_height: int = 6
    open_width: int = 620
    open_content_height: int = 178
    open_bar_height: int = 46
    open_radius: int = 30
    border_width: int = 1
    page_button_width: int = 42
    page_button_height: int = 34
    page_active_stroke: int = 2


NOTCH = Notch()

# --- Páginas -----------------------------------------------------------------


@dataclass(frozen=True)
class Pages:
    music_cover: int = 72
    music_title_size: int = 15
    music_title_weight: int = 600
    music_artist_size: int = 13
    music_play_button: int = 42
    lyrics_current_size: int = 17
    lyrics_current_weight: int = 600
    focus_ring: int = 132
    focus_cycles: int = 4
    water_value_size: int = 38
    water_segments: int = 8
    task_checkbox: int = 20


PAGES = Pages()

# --- Avisos ------------------------------------------------------------------


@dataclass(frozen=True)
class Notice:
    width: int = 360
    height: int = 64
    radius: int = 28
    icon: int = 36
    title_size: int = 13
    title_weight: int = 600
    subtitle_size: int = 11
    action_height: int = 30
    duration_ms: int = 8000


NOTICE = Notice()

# --- Janela de Configurações -------------------------------------------------


@dataclass(frozen=True)
class SettingsWindow:
    width: int = 1000
    height: int = 620
    sidebar_width: int = 220
    accent_swatch: int = 40
    switch_width: int = 42
    switch_height: int = 24
    chip_height: int = 32


SETTINGS_WINDOW = SettingsWindow()
