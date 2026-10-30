"""Seção Aparência, igual à do Aureum Voice: tema, cor de destaque, código hex e prévia.

Toda mudança vale para o app inteiro na hora (notch e Configurações). O seletor livre é o
QColorDialog do Qt: enquanto o usuário arrasta, só pré-visualiza (no máximo uma vez por
frame, sem re-tint e sem salvar); confirmar salva; cancelar volta à cor salva.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from aureum_island.island import icons
from aureum_island.island.widgets import _css
from aureum_island.island.window import notch_path
from aureum_island.settings.controls import Segmented, field_style
from aureum_island.settings.store import SettingsStore
from aureum_island.theme import color
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import (
    ACCENT_PRESETS,
    MOTION,
    NOTCH,
    PAGES,
    SETTINGS_WINDOW,
    TYPOGRAPHY,
)

THEME_OPTIONS = (
    ("dark", "Escuro", "moon"),
    ("light", "Claro", "sun"),
    ("system", "Sistema", "monitor"),
)
SYSTEM_HINT = "Segue o modo claro/escuro do Windows."
CONTRAST_HINT = (
    "O texto sobre a cor e os links ajustam o contraste sozinhos para continuarem legíveis."
)


def parse_accent(text: str) -> str | None:
    """'#e8b531' -> '#E8B531'. None se não for '#' + 6 dígitos hex (como o HEX_RE do Voice)."""
    value = text.strip()
    if len(value) != 7 or not color.is_hex_color(value):
        return None
    return value.upper()


def field_label(text: str, parent: QWidget) -> QLabel:
    """Rótulo pequeno em caixa alta acima de um controle (labelClass do Voice)."""
    label = QLabel(text.upper(), parent)
    label.setObjectName("label")  # cor no stylesheet da janela (text-muted)
    label.setFont(
        make_font(
            TYPOGRAPHY.family_body,
            SETTINGS_WINDOW.label_size,
            SETTINGS_WINDOW.label_weight,
            letter_spacing_em=SETTINGS_WINDOW.label_letter_spacing_em,
        )
    )
    return label


def subtle(text: str, parent: QWidget) -> QLabel:
    """Texto pequeno em fg-subtle (a versão legível, ≥ 4.5:1)."""
    label = QLabel(text, parent)
    label.setObjectName("subtle")
    label.setWordWrap(True)
    label.setFont(make_font(TYPOGRAPHY.family_body, SETTINGS_WINDOW.hint_size))
    return label


class AccentSwatch(QAbstractButton):
    """Bolinha de 40 px com o nome embaixo. Selecionada: anel na cor do texto e ✓ em
    on-accent. `other`: "Outra" (borda tracejada e conta-gotas; preenchida com o accent e
    com anel quando a cor atual não é um preset)."""

    def __init__(
        self, name: str, hex_color: str | None, theme: Theme, parent: QWidget, *, other=False
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self.hex = hex_color
        self.other = other
        self.selected = False
        self.setText(name)
        self.setFont(make_font(TYPOGRAPHY.family_body, SETTINGS_WINDOW.label_size))
        self.setAccessibleName("Escolher outra cor" if other else f"Cor de destaque {name}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        fm = QFontMetricsF(self.font())
        height = SETTINGS_WINDOW.accent_swatch + SETTINGS_WINDOW.swatch_label_gap + fm.height()
        ring = SETTINGS_WINDOW.swatch_ring_offset + SETTINGS_WINDOW.swatch_ring_width
        self.setFixedSize(SETTINGS_WINDOW.swatch_column, round(height) + 2 * ring)
        theme.changed.connect(self.update)

    def set_selected(self, selected: bool) -> None:
        if selected != self.selected:
            self.selected = selected
            self.setAccessibleDescription("selecionada" if selected else "")
            self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.size()

    def paintEvent(self, event) -> None:  # noqa: N802
        w = self._theme.window
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = SETTINGS_WINDOW.accent_swatch
        ring_space = SETTINGS_WINDOW.swatch_ring_offset + SETTINGS_WINDOW.swatch_ring_width
        circle = QRectF((self.width() - s) / 2, ring_space, s, s)
        if self.other and not self.selected:
            pen = QPen(qcolor(w.subtle), 1)  # contorno, não é texto
            pen.setDashPattern([SETTINGS_WINDOW.swatch_dash, SETTINGS_WINDOW.swatch_dash])
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(circle.adjusted(0.5, 0.5, -0.5, -0.5))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(w.accent if self.other else self.hex))
            painter.drawEllipse(circle)
        if self.selected or self.hasFocus():
            offset = SETTINGS_WINDOW.swatch_ring_offset + SETTINGS_WINDOW.swatch_ring_width / 2
            painter.setBrush(Qt.BrushStyle.NoBrush)
            ring = w.text if self.selected else w.accent
            painter.setPen(QPen(qcolor(ring), SETTINGS_WINDOW.swatch_ring_width))
            painter.drawEllipse(circle.adjusted(-offset, -offset, offset, offset))
        glyph = SETTINGS_WINDOW.swatch_check
        name, ink = None, ""
        if self.other:
            name, ink = "pipette", (w.on_accent if self.selected else w.text_muted)
        elif self.selected:
            name, ink = "check", color.ink_on(self.hex)
        if name is not None:
            pm = icons.pixmap(name, ink, glyph, self.devicePixelRatioF())
            c = circle.center()
            painter.drawPixmap(int(c.x() - glyph / 2), int(c.y() - glyph / 2), pm)
        painter.setPen(qcolor(w.text if self.underMouse() else w.text_muted))
        top = circle.bottom() + ring_space + SETTINGS_WINDOW.swatch_label_gap - 2
        painter.drawText(
            QRectF(0, top, self.width(), self.height() - top),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            self.text(),
        )


class NotchPreview(QWidget):
    """Notch aberto em miniatura, com os tokens do notch (sempre escuro), numa moldura
    no fundo da janela."""

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
        t, n, win = self._theme, self._theme.notch, self._theme.window
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = SETTINGS_WINDOW.preview_radius
        painter.setPen(QPen(qcolor(win.border), 1))
        painter.setBrush(qcolor(win.rail))
        painter.drawRoundedRect(frame, radius, radius)

        # O notch pendurado na borda de cima, como na tela.
        w, h = SETTINGS_WINDOW.preview_notch_width, SETTINGS_WINDOW.preview_notch_height
        x = (self.width() - w) / 2
        painter.setClipRect(frame)
        painter.translate(0, 0.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(n.rail))
        painter.drawPath(notch_path(x, w, h, radius))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(qcolor(t.border_notch), NOTCH.border_width))
        painter.drawPath(notch_path(x, w, h, radius, inset=0.5, closed=False))

        pad = SETTINGS_WINDOW.gap + radius / 2
        inner = QRectF(x + pad, 0, w - 2 * pad, h)
        painter.setFont(self._brand)
        painter.setPen(qcolor(n.accent_text))
        painter.drawText(
            inner, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "AUREUM"
        )
        painter.setFont(self._clock)
        painter.setPen(qcolor(n.text))
        painter.drawText(inner, Qt.AlignmentFlag.AlignCenter, "14:32")

        painter.setFont(self._button)
        label = "Feito"
        bw = QFontMetricsF(self._button).horizontalAdvance(label) + 2 * PAGES.button_padding_x
        bh = PAGES.button_height
        pill = QRectF(inner.right() - bw, (h - bh) / 2, bw, bh)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(n.accent))
        painter.drawRoundedRect(pill, bh / 2, bh / 2)
        painter.setPen(qcolor(n.on_accent))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, label)


class AppearanceSection(QWidget):
    def __init__(self, theme: Theme, store: SettingsStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from aureum_island.settings.window import section_title

        self.setAccessibleName("Aparência")
        self.theme, self.store = theme, store
        self.dialog: QColorDialog | None = None
        self._pending_preview: str | None = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(MOTION.frame_ms)
        self._preview_timer.timeout.connect(self._flush_preview)

        # Tema
        self.window_theme = Segmented(theme, "Tema", THEME_OPTIONS, self)
        self.window_theme.selected.connect(lambda v: store.update(window_theme=v))
        self.system_hint = subtle(SYSTEM_HINT, self)

        # Cor de destaque
        swatches = QWidget(self)
        swatch_row = QHBoxLayout(swatches)
        swatch_row.setContentsMargins(0, 0, 0, 0)
        swatch_row.setSpacing(SETTINGS_WINDOW.gap)
        self.presets: list[AccentSwatch] = []
        for name, hex_color in ACCENT_PRESETS.values():
            swatch = AccentSwatch(name, hex_color, theme, swatches)
            swatch.clicked.connect(lambda _c=False, h=hex_color: store.update(accent=h))
            self.presets.append(swatch)
            swatch_row.addWidget(swatch)
        self.other = AccentSwatch("Outra", None, theme, swatches, other=True)
        self.other.clicked.connect(self.open_picker)
        swatch_row.addWidget(self.other)
        swatch_row.addStretch(1)

        self.hex = QLineEdit(self)
        self.hex.setAccessibleName("Código hex da cor de destaque")
        self.hex.setMaxLength(7)
        self.hex.setFont(make_font(TYPOGRAPHY.family_mono, SETTINGS_WINDOW.body_size))
        self.hex.setFixedSize(SETTINGS_WINDOW.hex_width, SETTINGS_WINDOW.input_height)
        self.hex.textEdited.connect(self._on_hex_edited)
        self.hex.editingFinished.connect(self._reset_hex)
        hex_label = subtle("Código hex", self)
        hex_label.setBuddy(self.hex)

        self.preview = NotchPreview(theme, self)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)
        theme_label = field_label("Tema", self)
        theme_label.setBuddy(self.window_theme.chips[0])
        accent_label = field_label("Cor de destaque", self)
        accent_label.setBuddy(self.presets[0])
        label_gap = SETTINGS_WINDOW.row_gap + 2
        for item, after in (
            (theme_label, label_gap),
            (self.window_theme, SETTINGS_WINDOW.row_gap),
            (self.system_hint, SETTINGS_WINDOW.section_gap),
            (accent_label, label_gap),
            (swatches, SETTINGS_WINDOW.gap + 4),
            (hex_label, SETTINGS_WINDOW.row_gap - 2),
            (self.hex, label_gap),
            (subtle(CONTRAST_HINT, self), 0),
        ):
            left.addWidget(item)
            left.addSpacing(after)
        left.addStretch(1)

        right_box = QWidget(self)
        right_box.setFixedWidth(SETTINGS_WINDOW.preview_column)
        right = QVBoxLayout(right_box)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(label_gap)
        right.addWidget(field_label("Prévia", right_box))
        right.addWidget(self.preview)
        right.addStretch(1)

        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(SETTINGS_WINDOW.columns_gap)
        columns.addLayout(left, 1)
        columns.addWidget(right_box)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_WINDOW.section_gap)
        layout.addWidget(section_title("Aparência", self))
        layout.addLayout(columns, 1)

        store.changed.connect(lambda _keys: self.load())
        theme.changed.connect(self._apply_theme)
        self._apply_theme()
        self.load()

    # --- estado --------------------------------------------------------------

    def load(self) -> None:
        s = self.store.value
        self.window_theme.set_value(s.window_theme)
        self.system_hint.setVisible(s.window_theme == "system")
        accent = s.accent.upper()
        for swatch in self.presets:
            swatch.set_selected(swatch.hex == accent)
        self.other.set_selected(not any(sw.hex == accent for sw in self.presets))
        if not self.hex.hasFocus():
            self.hex.setText(accent)

    def _on_hex_edited(self, text: str) -> None:
        # Maiúsculas no próprio campo; aplica a cada cor válida digitada.
        if text != text.upper():
            cursor = self.hex.cursorPosition()
            self.hex.setText(text.upper())
            self.hex.setCursorPosition(cursor)
        value = parse_accent(text)
        if value is not None:
            self.store.update(accent=value)

    def _reset_hex(self) -> None:
        self.hex.setText(self.store.value.accent.upper())

    # --- seletor livre -------------------------------------------------------

    def open_picker(self) -> None:
        dialog = QColorDialog(QColor(self.store.value.accent), self.window())
        # O do Qt (não o nativo): avisa enquanto arrasta e tem "Pick Screen Color".
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        dialog.setWindowTitle("Escolher outra cor")
        dialog.setStyleSheet(dialog_style(self.theme))
        dialog.currentColorChanged.connect(self._queue_preview)
        dialog.colorSelected.connect(self._on_picked)
        dialog.rejected.connect(self._end_preview)
        dialog.finished.connect(self._on_dialog_finished)
        self.dialog = dialog
        dialog.open()

    def _on_dialog_finished(self, _result: int) -> None:
        if self.dialog is not None:
            self.dialog.deleteLater()
            self.dialog = None

    def _queue_preview(self, qc: QColor) -> None:
        # Arrastar dispara muitas vezes por segundo: junta tudo num frame.
        self._pending_preview = qc.name().upper()
        if not self._preview_timer.isActive():
            self._preview_timer.start()

    def _flush_preview(self) -> None:
        if self._pending_preview is not None:
            self.theme.preview_accent(self._pending_preview)
            self._pending_preview = None

    def _on_picked(self, qc: QColor) -> None:
        self._preview_timer.stop()
        self._pending_preview = None
        chosen = qc.name().upper()
        if chosen != self.store.value.accent.upper():
            self.store.update(accent=chosen)  # re-tinge tudo e salva
        else:
            self.theme.end_preview()  # mesma cor: só larga a prévia

    def _end_preview(self) -> None:
        self._preview_timer.stop()
        self._pending_preview = None
        self.theme.end_preview()

    def _apply_theme(self) -> None:
        self.hex.setStyleSheet(field_style(self.theme, "QLineEdit"))
        if self.dialog is not None:
            self.dialog.setStyleSheet(dialog_style(self.theme))


def dialog_style(theme: Theme) -> str:
    """O QColorDialog é filho da janela: recebe as cores do tema escolhido."""
    w = theme.window
    r = SETTINGS_WINDOW.input_radius
    return (
        f"QColorDialog {{ background: {w.panel}; }}"
        f"QColorDialog QLabel {{ color: {w.text}; }}"
        f"QColorDialog QLineEdit, QColorDialog QSpinBox {{ background: {w.main}; color: {w.text};"
        f" border: 1px solid {_css(w.border)}; border-radius: {r}px; padding: 2px 6px; }}"
        f"QColorDialog QPushButton {{ background: {w.elevated}; color: {w.text};"
        f" border: 1px solid {_css(w.border)}; border-radius: {r}px; padding: 6px 14px; }}"
        f"QColorDialog QPushButton:default {{ background: {w.accent}; color: {w.on_accent};"
        " border: none; }"
        f"QColorDialog QPushButton:focus {{ border: {NOTCH.focus_ring_width}px solid {w.accent}; }}"
    )
