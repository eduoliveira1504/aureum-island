"""Seção Aparência: tema da janela, cor de destaque, fundo do notch e prévia."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from aureum_island.island.widgets import ActionButton
from aureum_island.island.window import notch_path
from aureum_island.settings.controls import (
    ChipGroup,
    ColorSwatch,
    EyeDropper,
    SettingRow,
    body_font,
    field_style,
)
from aureum_island.settings.general_section import error_label, show_error
from aureum_island.settings.store import SettingsStore
from aureum_island.theme import color
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import (
    ACCENT_PRESETS,
    COLORS,
    NOTCH,
    NOTCH_BACKGROUNDS,
    PAGES,
    SETTINGS_WINDOW,
    TYPOGRAPHY,
)

THEME_OPTIONS = (("dark", "Escuro"), ("light", "Claro"), ("system", "Sistema"))


def parse_accent(text: str) -> str | None:
    """'#e8b531', 'E8B531' -> '#E8B531'. None se não for uma cor hex de 6 dígitos."""
    value = text.strip()
    if not value.startswith("#"):
        value = "#" + value
    if not color.is_hex_color(value):
        return None
    return color.to_hex(color.parse_hex(value))


class NotchPreview(QWidget):
    """Notch aberto em miniatura com as cores escolhidas (sempre escuro)."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setFixedSize(SETTINGS_WINDOW.preview_width, SETTINGS_WINDOW.preview_height)
        self.setAccessibleName("Prévia do notch")
        self._brand = make_font(
            TYPOGRAPHY.family_title,
            TYPOGRAPHY.title_size_sm,
            600,
            letter_spacing_em=TYPOGRAPHY.title_letter_spacing_em,
        )
        self._clock = make_font(
            TYPOGRAPHY.family_body, TYPOGRAPHY.clock_size, TYPOGRAPHY.clock_weight, tabular=True
        )
        self._button = make_font(
            TYPOGRAPHY.family_body, PAGES.button_font_size, PAGES.button_font_weight
        )
        theme.changed.connect(self.update)

    def paintEvent(self, event) -> None:  # noqa: N802
        t = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = SETTINGS_WINDOW.preview_notch_width, SETTINGS_WINDOW.preview_notch_height
        x = (self.width() - w) / 2
        radius = SETTINGS_WINDOW.preview_radius
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(t.notch_bg))
        painter.drawPath(notch_path(x, w, h, radius))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(qcolor(t.border_notch), NOTCH.border_width))
        painter.drawPath(notch_path(x, w, h, radius, inset=0.5, closed=False))

        pad = SETTINGS_WINDOW.gap + radius / 2
        inner = QRectF(x + pad, 0, w - 2 * pad, h)
        painter.setFont(self._brand)
        painter.setPen(qcolor(t.accent_text))
        painter.drawText(
            inner, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "AUREUM"
        )
        painter.setFont(self._clock)
        painter.setPen(qcolor(COLORS.text))
        painter.drawText(inner, Qt.AlignmentFlag.AlignCenter, "14:32")

        painter.setFont(self._button)
        label = "Feito"
        bw = QFontMetricsF(self._button).horizontalAdvance(label) + 2 * PAGES.button_padding_x
        bh = PAGES.button_height
        pill = QRectF(inner.right() - bw, (h - bh) / 2, bw, bh)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(t.accent))
        painter.drawRoundedRect(pill, bh / 2, bh / 2)
        painter.setPen(qcolor(t.on_accent))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, label)


class AppearanceSection(QWidget):
    def __init__(self, theme: Theme, store: SettingsStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from aureum_island.settings.window import hint, section_title

        self.setAccessibleName("Aparência")
        self.theme, self.store = theme, store
        self._droppers: list[EyeDropper] = []

        self.window_theme = ChipGroup(theme, "Tema da janela", THEME_OPTIONS, self)
        self.window_theme.selected.connect(lambda v: store.update(window_theme=v))

        # Cor de destaque: presets + "Outra" (campo hex e conta-gotas).
        swatches = QWidget(self)
        swatch_row = QHBoxLayout(swatches)
        swatch_row.setContentsMargins(0, 0, 0, 0)
        swatch_row.setSpacing(SETTINGS_WINDOW.chip_gap)
        self.accents = QButtonGroup(self)
        self.accents.setExclusive(True)
        size = SETTINGS_WINDOW.accent_swatch
        for name, hex_color in ACCENT_PRESETS.values():
            swatch = ColorSwatch(name, hex_color, theme, size, swatches)
            swatch.clicked.connect(lambda _c=False, h=hex_color: self._set_accent(h))
            self.accents.addButton(swatch)
            swatch_row.addWidget(swatch)
        self.other = ColorSwatch("Outra", None, theme, size, swatches)
        self.other.setToolTip("Outra: digite o código ou use o conta-gotas")
        self.other.clicked.connect(self._focus_hex)
        self.accents.addButton(self.other)
        swatch_row.addWidget(self.other)
        swatch_row.addStretch(1)

        self.hex = QLineEdit(self)
        self.hex.setAccessibleName("Código hex da cor de destaque")
        self.hex.setPlaceholderText("#E8B531")
        self.hex.setMaxLength(7)
        self.hex.setFont(body_font())
        self.hex.setFixedSize(SETTINGS_WINDOW.number_width, SETTINGS_WINDOW.input_height)
        self.hex.editingFinished.connect(self._on_hex)
        self.dropper_button = ActionButton("Conta-gotas", theme, window=True, parent=self)
        self.dropper_button.setAccessibleName("Escolher a cor na tela com o conta-gotas")
        self.dropper_button.clicked.connect(self._start_dropper)
        hex_controls = QWidget(self)
        hex_row = QHBoxLayout(hex_controls)
        hex_row.setContentsMargins(0, 0, 0, 0)
        hex_row.setSpacing(SETTINGS_WINDOW.chip_gap)
        hex_row.addWidget(self.hex)
        hex_row.addWidget(self.dropper_button)
        self.hex_error = error_label(self)

        self.notch_bg = ChipGroup(
            theme,
            "Fundo do notch",
            tuple((key, name) for key, (name, _hex) in NOTCH_BACKGROUNDS.items()),
            self,
        )
        self.notch_bg.selected.connect(lambda v: store.update(notch_bg=v))
        self.preview = NotchPreview(theme, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_WINDOW.gap)
        layout.addWidget(section_title("Aparência", self))
        layout.addWidget(
            SettingRow(
                "Tema da janela",
                self.window_theme,
                self,
                hint_text="Vale para esta janela. O notch é sempre escuro.",
            )
        )
        accent_setting = SettingRow(
            "Cor de destaque",
            swatches,
            self,
            hint_text="Textos em destaque se ajustam sozinhos para continuar legíveis.",
        )
        accent_setting.label.setBuddy(self.accents.buttons()[0])
        layout.addWidget(accent_setting)
        hex_setting = SettingRow("Código da cor", hex_controls, self)
        hex_setting.label.setBuddy(self.hex)
        layout.addWidget(hex_setting)
        layout.addWidget(self.hex_error)
        layout.addWidget(SettingRow("Fundo do notch", self.notch_bg, self))
        layout.addSpacing(SETTINGS_WINDOW.gap)
        layout.addWidget(hint("Prévia", self))
        layout.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

        store.changed.connect(lambda _keys: self.load())
        theme.changed.connect(self._apply_theme)
        self._apply_theme()
        self.load()

    def load(self) -> None:
        s = self.store.value
        self.window_theme.set_value(s.window_theme)
        self.notch_bg.set_value(s.notch_bg)
        accent = color.to_hex(color.parse_hex(s.accent))
        preset = next(
            (b for b in self.accents.buttons() if b is not self.other and b.hex == accent), None
        )
        if preset is None:
            self.other.set_hex(accent)
            preset = self.other
        else:
            self.other.set_hex(None)
        preset.setChecked(True)
        if not self.hex.hasFocus():
            self.hex.setText(accent)

    def _set_accent(self, hex_color: str) -> None:
        show_error(self.hex_error, "")
        self.store.update(accent=hex_color)

    def _focus_hex(self) -> None:
        self.load()  # "Outra" só fica marcada quando a cor é mesmo outra
        self.hex.setFocus()
        self.hex.selectAll()

    def _on_hex(self) -> None:
        value = parse_accent(self.hex.text())
        if value is None:
            show_error(self.hex_error, "Use o formato #RRGGBB (ex.: #E8B531).")
            self.hex.setStyleSheet(field_style(self.theme, "QLineEdit", error=True))
            return
        self.hex.setStyleSheet(field_style(self.theme, "QLineEdit"))
        self._set_accent(value)
        self.hex.setText(value)

    def _start_dropper(self) -> None:
        self._droppers = EyeDropper.start()
        for dropper in self._droppers:
            dropper.picked.connect(self._on_picked)

    def _on_picked(self, hex_color: str) -> None:
        self.hex.setText(hex_color)
        self._set_accent(hex_color)
        self.window().activateWindow()

    def _apply_theme(self) -> None:
        error = self.hex_error.isVisible()
        self.hex.setStyleSheet(field_style(self.theme, "QLineEdit", error=error))
