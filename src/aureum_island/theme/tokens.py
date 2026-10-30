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


@dataclass(frozen=True)
class WindowPalette:
    """Cores da janela de Configurações (o notch é sempre escuro e usa COLORS).

    `accent_toward`: para onde o accent é misturado até virar texto legível
    (branco no escuro, preto no claro).
    """

    panel: str
    sidebar: str
    surface: str
    text: str
    text_muted: str
    text_dim: str
    track: str
    danger_bg: str
    danger_text: str
    accent_toward: str
    # Contornos (botões, chips, campos) e divisores: accent_text com esta opacidade.
    border_alpha_button: float
    border_alpha_divider: float


WINDOW_DARK = WindowPalette(
    panel=COLORS.panel,
    sidebar=COLORS.sidebar,
    surface=COLORS.surface,
    text=COLORS.text,
    text_muted=COLORS.text_muted,
    text_dim=COLORS.text_dim,
    track=COLORS.track,
    danger_bg=COLORS.danger_bg,
    danger_text=COLORS.danger_text,
    accent_toward=COLORS.on_accent_light,
    border_alpha_button=0.30,
    border_alpha_divider=0.14,
)
WINDOW_LIGHT = WindowPalette(
    panel="#FAF7F0",
    sidebar="#F1ECE1",
    surface="#E8E0CF",
    text="#1E1A14",
    text_muted="#5C5446",
    text_dim="#665D4E",
    track="#D9D0BD",
    danger_bg="#F6D5CE",
    danger_text="#7A1F16",
    accent_toward="#000000",
    # No claro o accent a 30% some no fundo creme: contorno mais forte.
    border_alpha_button=0.55,
    border_alpha_divider=0.25,
)
WINDOW_PALETTES = {"dark": WINDOW_DARK, "light": WINDOW_LIGHT}

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
    music_cover: int = 120
    music_title_size: int = 15
    music_title_weight: int = 600
    music_artist_size: int = 13
    music_play_button: int = 42
    music_padding_x: int = 24
    music_column_gap: int = 20
    music_gap: int = 12
    music_cover_radius: int = 8
    music_cover_icon: int = 40
    music_title_gap: int = 2
    music_progress_height: int = 4
    music_progress_hit: int = 14
    music_time_size: int = 11
    music_control: int = 32
    music_icon: int = 18
    music_play_icon: int = 20
    music_volume_width: int = 96
    music_volume_handle: int = 10
    # Calendário
    cal_padding_x: int = 20
    cal_padding_y: int = 8
    cal_cell_width: int = 30
    cal_cell_height: int = 20
    cal_header_height: int = 24
    cal_weekday_height: int = 16
    cal_day_size: int = 12
    cal_weekday_size: int = 10
    cal_dot: int = 4
    cal_column_gap: int = 24
    cal_nav: int = 24
    cal_nav_icon: int = 14
    agenda_row_height: int = 26
    agenda_time_width: int = 56
    agenda_title_size: int = 13
    agenda_tag_size: int = 10
    agenda_tag_height: int = 16
    agenda_tag_padding_x: int = 6
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
    padding: int = 32
    sidebar_padding: int = 16
    nav_item_height: int = 36
    nav_item_radius: int = 8
    section_title_size: int = 20
    section_title_weight: int = 600
    body_size: int = 13
    hint_size: int = 12
    gap: int = 12
    input_height: int = 34
    input_radius: int = 8
    color_swatch: int = 22
    list_row_height: int = 52
    list_dot: int = 10
    # Bloco 6: linhas e controles das seções
    row_min_height: int = 44
    row_gap: int = 6  # entre o rótulo e a dica
    subsection_size: int = 15
    subsection_weight: int = 600
    subsection_gap: int = 20
    switch_knob_margin: int = 3
    chip_padding_x: int = 14
    chip_gap: int = 8
    number_width: int = 110
    time_width: int = 90
    hotkey_width: int = 200
    slider_width: int = 200
    slider_track: int = 4
    slider_handle: int = 14
    slider_hit: int = 24
    control_max_width: int = 520  # coluna dos controles (chips quebram antes disso)
    preview_width: int = 360
    preview_height: int = 120
    preview_notch_width: int = 300
    preview_notch_height: int = 64
    preview_radius: int = 22


SETTINGS_WINDOW = SettingsWindow()
