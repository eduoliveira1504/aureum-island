"""Barra de páginas do notch aberto: marca | 5 páginas | engrenagem."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QWidget,
)

from aureum_island.island import icons
from aureum_island.pages import PageInfo
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import NOTCH, TYPOGRAPHY

_WHEEL_STEP = 120  # um "dente" da roda


class PageButton(QToolButton):
    """Botão de ícone desenhado pelo tema: ativo em accent com traço embaixo,
    anel de foco em accent."""

    def __init__(
        self,
        icon_name: str,
        label: str,
        theme: Theme,
        *,
        checkable: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._theme = theme
        self.setObjectName(f"button-{icon_name}")
        self.setCheckable(checkable)
        self.setAutoRaise(True)
        self.setFixedSize(NOTCH.page_button_width, NOTCH.page_button_height)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(label)
        self.setAccessibleName(label)
        theme.changed.connect(self.update)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        # Setas ficam com a barra (troca de página), não com o botão.
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            event.ignore()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        theme = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isChecked():
            color = theme.accent_text
        elif self.underMouse() or self.isDown():
            color = self._theme.notch.text
        else:
            color = self._theme.notch.text_muted
        size = NOTCH.page_icon
        pm = icons.pixmap(self._icon_name, color, size, self.devicePixelRatioF())
        painter.drawPixmap(int((self.width() - size) / 2), int((self.height() - size) / 2), pm)

        if self.isChecked():
            stroke_w, stroke_h = NOTCH.page_active_stroke_width, NOTCH.page_active_stroke
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(theme.accent))
            painter.drawRoundedRect(
                QRectF((self.width() - stroke_w) / 2, self.height() - stroke_h, stroke_w, stroke_h),
                stroke_h / 2,
                stroke_h / 2,
            )

        if self.hasFocus():
            ring = NOTCH.focus_ring_width
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(theme.accent), ring))
            inset = ring / 2
            painter.drawRoundedRect(
                QRectF(self.rect()).adjusted(inset, inset, -inset, -inset),
                NOTCH.focus_ring_radius,
                NOTCH.focus_ring_radius,
            )


class PageBar(QWidget):
    page_changed = Signal(int)
    settings_requested = Signal()

    def __init__(
        self, pages: Sequence[PageInfo], theme: Theme, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page-bar")
        self.setAccessibleName("Páginas")
        self._theme = theme
        self._wheel_acc = 0
        self.setFixedHeight(NOTCH.open_bar_height)

        self._brand = QLabel("AUREUM ISLAND", self)
        self._brand.setFont(
            make_font(
                TYPOGRAPHY.family_title,
                TYPOGRAPHY.title_size_sm,
                600,
                letter_spacing_em=TYPOGRAPHY.title_letter_spacing_em,
            )
        )
        self._brand.setAccessibleName("Aureum Island")

        center = QWidget(self)
        row = QHBoxLayout(center)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(NOTCH.page_button_gap)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.buttons: list[PageButton] = []
        for index, page in enumerate(pages):
            button = PageButton(page.icon, page.label, theme, checkable=True, parent=center)
            self._group.addButton(button, index)
            row.addWidget(button)
            self.buttons.append(button)
        self._group.idClicked.connect(self._on_clicked)

        self.settings_button = PageButton(
            "settings", "Configurações", theme, checkable=False, parent=self
        )
        self.settings_button.clicked.connect(self.settings_requested)

        grid = QGridLayout(self)
        grid.setContentsMargins(NOTCH.bar_padding_x, 0, NOTCH.bar_padding_x, 0)
        grid.setSpacing(0)
        v = Qt.AlignmentFlag.AlignVCenter
        grid.addWidget(self._brand, 0, 0, Qt.AlignmentFlag.AlignLeft | v)
        grid.addWidget(center, 0, 1, Qt.AlignmentFlag.AlignHCenter | v)
        grid.addWidget(self.settings_button, 0, 2, Qt.AlignmentFlag.AlignRight | v)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 1)

        chain = [*self.buttons, self.settings_button]
        for a, b in zip(chain, chain[1:], strict=False):
            QWidget.setTabOrder(a, b)

        self.buttons[0].setChecked(True)
        theme.changed.connect(self._apply_theme)
        self._apply_theme()

    # --- página atual -------------------------------------------------------

    @property
    def current_index(self) -> int:
        return self._group.checkedId()

    def set_current(self, index: int, *, focus: bool = False) -> None:
        index %= len(self.buttons)
        changed = index != self.current_index
        self.buttons[index].setChecked(True)
        if focus:
            self.buttons[index].setFocus(Qt.FocusReason.TabFocusReason)
        if changed:
            self.page_changed.emit(index)

    def step(self, delta: int, *, focus: bool = False) -> None:
        self.set_current(self.current_index + delta, focus=focus)

    def focus_current(self) -> None:
        self.buttons[self.current_index].setFocus(Qt.FocusReason.TabFocusReason)

    def _on_clicked(self, index: int) -> None:
        self.page_changed.emit(index)

    # --- teclado e roda -----------------------------------------------------

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Left:
            self.step(-1, focus=True)
        elif event.key() == Qt.Key.Key_Right:
            self.step(1, focus=True)
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta()
        self._wheel_acc += delta.y() or delta.x()
        # Acumula para touchpads, que mandam deltas pequenos.
        while abs(self._wheel_acc) >= _WHEEL_STEP:
            direction = 1 if self._wheel_acc < 0 else -1  # rolar para baixo = próxima
            self._wheel_acc += _WHEEL_STEP * direction
            self.step(direction)
        event.accept()

    # --- tema ---------------------------------------------------------------

    def _apply_theme(self) -> None:
        palette = self._brand.palette()
        palette.setColor(QPalette.ColorRole.WindowText, qcolor(self._theme.accent_text))
        self._brand.setPalette(palette)
