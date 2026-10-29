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
    shadow: str = "#000000"


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
    page_active_stroke_width: int = 18
    page_icon: int = 18
    page_button_gap: int = 4
    bar_padding_x: int = 18
    minimal_radius: int = 3
    closed_gap: int = 8
    focus_ring_width: int = 2
    focus_ring_radius: int = 8
    # Sombra (janela separada, transparente a cliques): só no estado aberto.
    shadow_margin: int = 24
    shadow_max_alpha: float = 0.11
    shadow_falloff: float = 1.2


NOTCH = Notch()

# --- Movimento ---------------------------------------------------------------


@dataclass(frozen=True)
class Motion:
    hover_open_delay_ms: int = 120
    hover_close_delay_ms: int = 300
    transition_ms: int = 220
    # Fração da transição a partir da qual o conteúdo novo aparece (fade até o fim).
    content_fade_start: float = 0.6
    undo_ms: int = 5000  # "Desfazer" na linha da tarefa excluída


MOTION = Motion()

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
    water_value_weight: int = 600
    water_unit_size: int = 13
    water_segment_width: int = 22
    water_segment_gap: int = 4
    water_chart_width: int = 250
    water_chart_height: int = 96
    water_bar_gap: int = 4
    water_bar_min: int = 2
    water_axis_size: int = 10
    task_checkbox: int = 20
    # Foco
    focus_ring_stroke: int = 8
    focus_time_size: int = 28
    focus_time_weight: int = 600
    focus_padding_x: int = 32
    focus_column_gap: int = 28
    focus_segment_width: int = 28
    focus_segment_height: int = 4
    focus_segment_gap: int = 6
    # Tarefas
    tasks_padding_x: int = 20
    tasks_padding_top: int = 10
    task_row_height: int = 30
    task_title_size: int = 13
    task_time_size: int = 12
    task_pill_height: int = 20
    task_pill_padding_x: int = 8
    task_input_height: int = 30
    task_time_input_width: int = 64
    task_spacing: int = 8
    scrollbar_width: int = 6
    scrollbar_min_handle: int = 20
    menu_padding: int = 4
    menu_item_padding_y: int = 6
    menu_item_padding_x: int = 16
    menu_radius: int = 6
    # Botões de ação (aviso, foco, tarefas)
    button_height: int = 30
    button_padding_x: int = 12
    button_font_size: int = 12
    button_font_weight: int = 600
    button_gap: int = 6


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
    padding_x: int = 14
    gap: int = 10
    icon_glyph: int = 18
    icon_bg_alpha: float = 0.14


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
