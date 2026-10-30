"""Controles da janela de Configurações, desenhados com o esquema da janela (theme.window).

Todos navegáveis por teclado e com nome acessível.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QRectF, QSize, Qt, QTime, Signal
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from aureum_island.island import icons
from aureum_island.island.widgets import ActionButton, _css
from aureum_island.services import hotkey as hotkey_service
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import NOTCH, SETTINGS_WINDOW, TYPOGRAPHY

_MODS = (
    (Qt.KeyboardModifier.ControlModifier, hotkey_service.MOD_CONTROL),
    (Qt.KeyboardModifier.ShiftModifier, hotkey_service.MOD_SHIFT),
    (Qt.KeyboardModifier.AltModifier, hotkey_service.MOD_ALT),
    (Qt.KeyboardModifier.MetaModifier, hotkey_service.MOD_WIN),
)
_MODIFIER_KEYS = {
    Qt.Key.Key_Control,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Alt,
    Qt.Key.Key_AltGr,
    Qt.Key.Key_Meta,
}


_ARROWS = {Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down}


def body_font():
    return make_font(TYPOGRAPHY.family_body, SETTINGS_WINDOW.body_size)


def subsection_title(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setFont(
        make_font(
            TYPOGRAPHY.family_body,
            SETTINGS_WINDOW.subsection_size,
            SETTINGS_WINDOW.subsection_weight,
        )
    )
    label.setAccessibleName(text)
    return label


def field_style(theme: Theme, selector: str, *, error: bool = False) -> str:
    """QSpinBox / QTimeEdit / QLineEdit da janela: fundo surface, contorno accent 30%."""
    w = theme.window
    border = w.danger_text if error else w.border
    return (
        f"{selector} {{ background: {w.main}; color: {w.text};"
        f" border: 1px solid {_css(border)};"
        f" border-radius: {SETTINGS_WINDOW.input_radius}px;"
        f" padding: 0 {SETTINGS_WINDOW.gap}px;"
        f" selection-background-color: {w.accent}; selection-color: {w.on_accent}; }}"
        f"{selector}:focus {{ border: {NOTCH.focus_ring_width}px solid {w.accent}; }}"
        # Sem setas: o estilo ainda reservaria a largura delas e esconderia o número.
        f"{selector}::up-button, {selector}::down-button {{ subcontrol-origin: border;"
        " width: 0; height: 0; border: none; image: none; }"
    )


class Switch(QAbstractButton):
    """Liga/desliga 42x24. Espaço alterna; o nome acessível vem do rótulo da linha."""

    def __init__(self, theme: Theme, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setCheckable(True)
        self.setAccessibleName(name)
        self.setFixedSize(SETTINGS_WINDOW.switch_width, SETTINGS_WINDOW.switch_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toggled.connect(lambda _on: self.update())
        theme.changed.connect(self.update)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(SETTINGS_WINDOW.switch_width, SETTINGS_WINDOW.switch_height)

    def paintEvent(self, event) -> None:  # noqa: N802
        w = self._theme.window
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        on = self.isChecked()
        painter.setPen(Qt.PenStyle.NoPen if on else QPen(qcolor(w.subtle), 1))
        painter.setBrush(qcolor(w.accent if on else w.border))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        m = SETTINGS_WINDOW.switch_knob_margin
        knob = rect.height() - 2 * m
        x = rect.width() - m - knob if on else m
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(w.on_accent if on else w.text_muted))
        painter.drawEllipse(QRectF(x, m, knob, knob))
        if self.hasFocus():
            ring = NOTCH.focus_ring_width
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(w.text if on else w.accent), ring))
            inner = rect.adjusted(ring / 2, ring / 2, -ring / 2, -ring / 2)
            painter.drawRoundedRect(inner, inner.height() / 2, inner.height() / 2)


class Chip(QAbstractButton):
    """Opção de 32 px em pílula. Selecionada: fundo accent."""

    def __init__(self, text: str, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setText(text)
        self.setCheckable(True)
        self.setFont(body_font())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(SETTINGS_WINDOW.chip_height)
        self.toggled.connect(lambda _on: self.update())
        theme.changed.connect(self.update)

    def sizeHint(self) -> QSize:  # noqa: N802
        width = QFontMetrics(self.font()).horizontalAdvance(self.text())
        return QSize(width + 2 * SETTINGS_WINDOW.chip_padding_x, SETTINGS_WINDOW.chip_height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        # Setas ficam com o ChipGroup (o QAbstractButton só moveria o foco).
        if event.key() in _ARROWS:
            event.ignore()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        w = self._theme.window
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2
        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(w.accent))
            fg = w.on_accent
        else:
            painter.setPen(QPen(qcolor(w.border), 1))
            painter.setBrush(qcolor(w.elevated if self.underMouse() else w.main))
            fg = w.text
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(qcolor(fg))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        if self.hasFocus():
            ring = NOTCH.focus_ring_width
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(w.text if self.isChecked() else w.accent), ring))
            inner = QRectF(self.rect()).adjusted(ring / 2, ring / 2, -ring / 2, -ring / 2)
            painter.drawRoundedRect(inner, inner.height() / 2, inner.height() / 2)


class ChipGroup(QWidget):
    """Escolha única entre chips. Setas movem a escolha (como botões de rádio); Tab
    entra e sai do grupo pelo chip selecionado."""

    selected = Signal(object)  # valor da opção escolhida pelo usuário

    def __init__(
        self,
        theme: Theme,
        name: str,
        options: Sequence[tuple],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setAccessibleName(name)
        self.values = [value for value, *_ in options]
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.chips: list[QAbstractButton] = []
        row = QHBoxLayout(self)
        m = self.margin
        row.setContentsMargins(m, m, m, m)
        row.setSpacing(self.spacing)
        for i, (_value, label, *extra) in enumerate(options):
            chip = self.make_chip(label, *extra)
            chip.setAccessibleName(f"{name}: {label}")
            self.group.addButton(chip, i)
            self.chips.append(chip)
            row.addWidget(chip, self.chip_stretch)
        if not self.chip_stretch:
            row.addStretch(1)
        self.group.idClicked.connect(self._on_clicked)
        self._sync_focus()

    margin = 0
    spacing = SETTINGS_WINDOW.chip_gap
    chip_stretch = 0

    def make_chip(self, label: str) -> QAbstractButton:
        return Chip(label, self._theme, self)

    def value(self) -> object | None:
        index = self.group.checkedId()
        return self.values[index] if index >= 0 else None

    def set_value(self, value: object) -> None:
        """Marca sem emitir `selected`. Valor fora das opções desmarca todos."""
        self.group.setExclusive(False)
        for chip, v in zip(self.chips, self.values, strict=True):
            chip.setChecked(v == value)
        self.group.setExclusive(True)
        self._sync_focus()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        step = {
            Qt.Key.Key_Left: -1,
            Qt.Key.Key_Up: -1,
            Qt.Key.Key_Right: 1,
            Qt.Key.Key_Down: 1,
        }.get(event.key())
        focused = self.focusWidget()
        current = self.chips.index(focused) if focused in self.chips else None
        if step is None or current is None:
            super().keyPressEvent(event)
            return
        target = (current + step) % len(self.chips)
        self.chips[target].setFocus(Qt.FocusReason.TabFocusReason)
        self.chips[target].click()
        event.accept()

    def _on_clicked(self, index: int) -> None:
        self._sync_focus()
        self.selected.emit(self.values[index])

    def _sync_focus(self) -> None:
        # Só o chip marcado (ou o primeiro) entra no Tab; os outros, pelas setas.
        checked = self.group.checkedId()
        tab_index = checked if checked >= 0 else 0
        for i, chip in enumerate(self.chips):
            chip.setFocusPolicy(
                Qt.FocusPolicy.StrongFocus if i == tab_index else Qt.FocusPolicy.ClickFocus
            )


class NumberField(QSpinBox):
    """Número com sufixo. Só grava ao confirmar (Enter, sair do campo ou setas)."""

    def __init__(
        self,
        theme: Theme,
        name: str,
        minimum: int,
        maximum: int,
        *,
        suffix: str = "",
        step: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setAccessibleName(name)
        self.setRange(minimum, maximum)
        self.setSingleStep(step)
        self.setSuffix(suffix)
        self.setKeyboardTracking(False)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFont(body_font())
        self.setFixedSize(SETTINGS_WINDOW.number_width, SETTINGS_WINDOW.input_height)
        theme.changed.connect(self._apply_theme)
        self._apply_theme()

    def set_quiet(self, value: int) -> None:
        self.blockSignals(True)
        self.setValue(value)
        self.blockSignals(False)

    def wheelEvent(self, event) -> None:  # noqa: N802
        # Rolar a página não deve mudar o número sem querer.
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

    def _apply_theme(self) -> None:
        self.setStyleSheet(field_style(self._theme, "QSpinBox"))


class TimeField(QTimeEdit):
    """Horário HH:mm. Só grava ao confirmar."""

    def __init__(self, theme: Theme, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setAccessibleName(name)
        self.setDisplayFormat("HH:mm")
        self.setKeyboardTracking(False)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFont(body_font())
        self.setFixedSize(SETTINGS_WINDOW.time_width, SETTINGS_WINDOW.input_height)
        theme.changed.connect(self._apply_theme)
        self._apply_theme()

    def text_value(self) -> str:
        return self.time().toString("HH:mm")

    def set_text_quiet(self, hhmm: str) -> None:
        self.blockSignals(True)
        self.setTime(QTime.fromString(hhmm, "HH:mm"))
        self.blockSignals(False)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

    def _apply_theme(self) -> None:
        self.setStyleSheet(field_style(self._theme, "QTimeEdit"))


class SettingRow(QWidget):
    """Rótulo (e dica) à esquerda, controle à direita."""

    def __init__(
        self,
        title: str,
        control: QWidget,
        parent: QWidget,
        *,
        hint_text: str = "",
    ) -> None:
        super().__init__(parent)
        from aureum_island.settings.window import hint

        self.setMinimumHeight(SETTINGS_WINDOW.row_min_height)
        self.label = QLabel(title, self)
        self.label.setFont(body_font())
        if control.focusPolicy() != Qt.FocusPolicy.NoFocus:
            self.label.setBuddy(control)
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(SETTINGS_WINDOW.row_gap)
        text.addWidget(self.label)
        self.hint = hint(hint_text, self) if hint_text else None
        if self.hint is not None:
            text.addWidget(self.hint)
            control.setAccessibleDescription(hint_text)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SETTINGS_WINDOW.padding)
        row.addLayout(text, 1)
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)


class HotkeyField(ActionButton):
    """Mostra o atalho; Enter ou clique começam a gravar a próxima combinação.

    Esc cancela. Teclas que não são aceitas (ou só modificadores) são ignoradas.
    """

    recording_changed = Signal(bool)
    captured = Signal(str)

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__("", theme, window=True, parent=parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(SETTINGS_WINDOW.hotkey_width)
        self.recording = False
        self._shown = ""
        self.clicked.connect(self.start)

    def set_hotkey(self, text: str) -> None:
        self._shown = hotkey_service.display(text) if text else "Sem atalho"
        if not self.recording:
            self._show(self._shown)

    def start(self) -> None:
        if self.recording:
            return
        self.recording = True
        self._show("Pressione a combinação… (Esc cancela)")
        self.recording_changed.emit(True)

    def cancel(self) -> None:
        if self.recording:
            self._stop()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if not self.recording:
            super().keyPressEvent(event)
            return
        event.accept()
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._stop()
            return
        if key in _MODIFIER_KEYS:
            return
        mods = 0
        for qt_mod, win_mod in _MODS:
            if event.modifiers() & qt_mod:
                mods |= win_mod
        text = hotkey_service.format_hotkey(mods, event.nativeVirtualKey())
        if text is None:
            return
        self._stop()
        self.captured.emit(text)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self.cancel()
        super().focusOutEvent(event)

    def _stop(self) -> None:
        self.recording = False
        self._show(self._shown)
        self.recording_changed.emit(False)

    def _show(self, text: str) -> None:
        self.setText(text)
        self.setAccessibleName(f"Atalho global: {text}")


class Segment(QAbstractButton):
    """Opção do controle segmentado: ícone + texto. Selecionada: fundo elevated."""

    def __init__(self, text: str, icon_name: str, theme: Theme, parent: QWidget) -> None:
        super().__init__(parent)
        self._theme = theme
        self.icon_name = icon_name
        self.setText(text)
        self.setCheckable(True)
        self.setFont(make_font(TYPOGRAPHY.family_body, SETTINGS_WINDOW.body_size, 500))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(SETTINGS_WINDOW.segment_height)
        self.toggled.connect(lambda _on: self.update())
        theme.changed.connect(self.update)

    def sizeHint(self) -> QSize:  # noqa: N802
        text = QFontMetrics(self.font()).horizontalAdvance(self.text())
        icon = SETTINGS_WINDOW.segment_icon + SETTINGS_WINDOW.segment_icon_gap
        width = text + icon + 2 * SETTINGS_WINDOW.chip_padding_x
        return QSize(width, SETTINGS_WINDOW.segment_height)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in _ARROWS:
            event.ignore()  # setas ficam com o grupo
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        w = self._theme.window
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = SETTINGS_WINDOW.segment_radius
        on = self.isChecked()
        if on:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(w.elevated))
            painter.drawRoundedRect(rect, radius, radius)
        fg = w.text if on or self.underMouse() else w.text_muted
        fm = QFontMetrics(self.font())
        size, gap = SETTINGS_WINDOW.segment_icon, SETTINGS_WINDOW.segment_icon_gap
        total = size + gap + fm.horizontalAdvance(self.text())
        x = (self.width() - total) / 2
        pm = icons.pixmap(self.icon_name, fg, size, self.devicePixelRatioF())
        painter.drawPixmap(int(x), (self.height() - size) // 2, pm)
        painter.setPen(qcolor(fg))
        text_rect = QRectF(x + size + gap, 0, self.width(), self.height())
        left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        painter.drawText(text_rect, left, self.text())
        if self.hasFocus():
            ring = NOTCH.focus_ring_width
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(w.accent), ring))
            inner = rect.adjusted(ring / 2, ring / 2, -ring / 2, -ring / 2)
            painter.drawRoundedRect(inner, radius, radius)


class Segmented(ChipGroup):
    """Controle segmentado do Voice: moldura bg-main com borda; opções (valor, texto,
    ícone) com o mesmo tamanho. Setas trocam a opção."""

    margin = SETTINGS_WINDOW.segment_padding
    spacing = SETTINGS_WINDOW.segment_padding
    chip_stretch = 1

    def make_chip(self, label: str, icon_name: str = "") -> QAbstractButton:
        return Segment(label, icon_name, self._theme, self)

    def paintEvent(self, event) -> None:  # noqa: N802
        w = self._theme.window
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(qcolor(w.border), 1))
        painter.setBrush(qcolor(w.main))
        r = SETTINGS_WINDOW.control_radius
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), r, r)


class ColorSwatch(QAbstractButton):
    """Bolinha de cor (cor de uma agenda) com anel quando selecionada ou com foco."""

    def __init__(self, name: str, hex_color: str, theme: Theme, size: int, parent: QWidget) -> None:
        super().__init__(parent)
        self.hex = hex_color
        self._theme = theme
        self._size = size
        self.setCheckable(True)
        self.setFixedSize(size + 6, size + 6)
        self.setAccessibleName(f"Cor {name}")
        self.setToolTip(name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(lambda _on: self.update())
        theme.changed.connect(self.update)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self._size
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(self.hex))
        painter.drawEllipse(QRectF(3, 3, s, s))
        if self.isChecked() or self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(self._theme.window.text), NOTCH.focus_ring_width))
            painter.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))
