"""Tokens de design do Aureum Island (fonte: docs/DESIGN.md).

Nenhuma cor, fonte ou medida da UI deve ficar fora deste módulo.
Medidas em pixels lógicos; o Qt converte para o DPI do monitor.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Cores -------------------------------------------------------------------
#
# Paletas iguais às do Aureum Voice (apps/desktop/src/renderer/src/main.css), desenhadas em
# volta do Dourado. Em runtime o Theme re-tinge os neutros (fundos, borda, texto) para o
# matiz do accent; success e danger não mudam. Ver docs/decisions/0009.


@dataclass(frozen=True)
class Palette:
    bg_rail: str
    bg_panel: str
    bg_main: str
    bg_elevated: str
    border: str
    text: str
    text_muted: str
    success: str
    danger: str
    # Hover do accent: color-mix(in oklab, accent, <cor> <quanto>)
    accent_hover_mix: str
    accent_hover_amount: float


DARK = Palette(
    bg_rail="#0A0908",
    bg_panel="#12110D",
    bg_main="#17150F",
    bg_elevated="#201D16",
    border="#2A261D",
    text="#F4EFE4",
    text_muted="#A8A090",
    success="#3FBF7F",
    danger="#C7363B",
    accent_hover_mix="#FFFFFF",
    accent_hover_amount=0.12,
)
LIGHT = Palette(
    bg_rail="#EFE9DC",
    bg_panel="#F6F2E8",
    bg_main="#FFFFFF",
    bg_elevated="#F3EEE2",
    border="#E4DCCB",
    text="#1C1810",
    text_muted="#6B6354",
    success="#2E9E65",
    danger="#C7363B",
    accent_hover_mix="#000000",
    accent_hover_amount=0.10,
)
PALETTES = {"dark": DARK, "light": LIGHT}

# fg-subtle = color-mix(in oklab, text-muted 72%, bg-main)
SUBTLE_MUTED_WEIGHT = 0.72

# Tinta sobre o accent (on-accent): a que contrastar mais. Texto sobre danger: branco.
INK_DARK = "#1A1406"
INK_LIGHT = "#FFFFFF"
ON_DANGER = "#FFFFFF"
SHADOW = "#000000"

# Opacidades do accent que continuam no notch: contorno do notch aberto e linha mínima.
BORDER_ALPHA_NOTCH = 0.20
BORDER_ALPHA_MINIMAL = 0.55

# Contraste mínimo exigido para texto (WCAG AA). Só texto de controle desabilitado
# pode ficar abaixo (a WCAG isenta).
MIN_TEXT_CONTRAST = 4.5

# Presets de destaque (mesmos do Aureum Voice).
ACCENT_PRESETS: dict[str, tuple[str, str]] = {
    "dourado": ("Dourado", "#E8B531"),
    "ametista": ("Ametista", "#8B5CF6"),
    "esmeralda": ("Esmeralda", "#3FBF7F"),
    "brasa": ("Brasa", "#E06A4E"),
    "safira": ("Safira", "#4F8CC9"),
}
DEFAULT_ACCENT = ACCENT_PRESETS["dourado"][1]
# As paletas foram desenhadas em volta do Dourado: é a referência do re-tint.
RETINT_REFERENCE = DEFAULT_ACCENT

# --- Tipografia --------------------------------------------------------------


@dataclass(frozen=True)
class Typography:
    family_title: str = "Sora"  # títulos e display
    family_body: str = "Figtree"  # texto
    family_mono: str = "Consolas"  # código hex (fonte do Windows, como o font-mono do Voice)
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
    frame_ms: int = 16  # prévia da cor ao arrastar o seletor: no máximo 1 por frame


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
    preview_width: int = 280
    preview_height: int = 96
    preview_notch_width: int = 248
    preview_notch_height: int = 64
    preview_radius: int = 18
    # Aparência (igual ao Voice): duas colunas, prévia de 280 à direita
    preview_column: int = 280
    columns_gap: int = 24
    control_radius: int = 12  # botões, campos, cartões (radius-control do Voice)
    segment_height: int = 32
    segment_radius: int = 8  # radius-item do Voice
    segment_padding: int = 4
    segment_icon: int = 16
    segment_icon_gap: int = 8
    swatch_column: int = 64  # bolinha + nome embaixo
    swatch_label_gap: int = 6
    swatch_check: int = 18
    swatch_ring_offset: int = 2
    swatch_ring_width: int = 2
    swatch_dash: float = 3.0
    label_size: int = 12  # rótulo em caixa alta acima dos controles
    label_weight: int = 600
    label_letter_spacing_em: float = 0.05
    hex_width: int = 160
    section_gap: int = 24


SETTINGS_WINDOW = SettingsWindow()
