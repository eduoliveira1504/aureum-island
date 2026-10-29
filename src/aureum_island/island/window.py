"""Janelas do notch e da sombra.

O notch tem exatamente o tamanho do contorno visível (sem margem): fora dele a
janela não existe, então hover e clique ficam precisos. A sombra mora numa
segunda janela, transparente a cliques, logo abaixo no z-order.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsOpacityEffect, QStackedWidget, QVBoxLayout, QWidget

from aureum_island.island.clock import ClockView
from aureum_island.island.geometry import Shape
from aureum_island.island.notices import NoticeView
from aureum_island.island.page_bar import PageBar
from aureum_island.island.state import State
from aureum_island.pages import PageInfo
from aureum_island.pages.placeholder import PlaceholderPage
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import COLORS, NOTCH

_FLAGS = (
    Qt.WindowType.Tool
    | Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.NoDropShadowWindowHint
)


def notch_path(
    x: float, width: float, height: float, radius: float, *, inset: float = 0.0, closed: bool = True
) -> QPainterPath:
    """Topo reto colado na borda da tela; só os cantos de baixo arredondados.
    Com `closed=False`, devolve só laterais + base (para a borda, sem traço no topo)."""
    left, right, bottom = x + inset, x + width - inset, height - inset
    r = max(0.0, min(radius, (right - left) / 2, bottom))
    path = QPainterPath(QPointF(left, 0))
    path.lineTo(left, bottom - r)
    path.arcTo(QRectF(left, bottom - 2 * r, 2 * r, 2 * r), 180, 90)
    path.lineTo(right - r, bottom)
    path.arcTo(QRectF(right - 2 * r, bottom - 2 * r, 2 * r, 2 * r), 270, 90)
    path.lineTo(right, 0)
    if closed:
        path.closeSubpath()
    return path


class OpenView(QWidget):
    """Conteúdo do notch aberto: páginas (178) + barra (46)."""

    def __init__(
        self,
        pages: Sequence[PageInfo],
        theme: Theme,
        parent: QWidget,
        page_widgets: Mapping[str, QWidget] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("open-view")
        self.stack = QStackedWidget(self)
        self.stack.setFixedHeight(NOTCH.open_content_height)
        page_widgets = page_widgets or {}
        for page in pages:
            widget = page_widgets.get(page.id) or PlaceholderPage(page)
            self.stack.addWidget(widget)
        self.bar = PageBar(pages, theme, self)
        self.bar.page_changed.connect(self.stack.setCurrentIndex)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.stack)
        layout.addWidget(self.bar)
        self.setFixedSize(NOTCH.open_width, NOTCH.open_content_height + NOTCH.open_bar_height)

    def set_page(self, index: int) -> None:
        self.bar.set_current(index)
        self.stack.setCurrentIndex(self.bar.current_index)


class NotchWindow(QWidget):
    hover_changed = Signal(bool)
    pressed = Signal()
    escape_pressed = Signal()
    deactivated = Signal()

    def __init__(
        self,
        pages: Sequence[PageInfo],
        theme: Theme,
        page_widgets: Mapping[str, QWidget] | None = None,
    ) -> None:
        super().__init__(None, _FLAGS)
        self.setObjectName("notch")
        self.setWindowTitle("Aureum Island")
        self.setAccessibleName("Aureum Island")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._theme = theme
        self._shape = Shape(NOTCH.closed_width, NOTCH.closed_height, NOTCH.closed_radius)
        self._state = State.CLOSED
        self._was_active = False

        self.clock = ClockView(theme, self)
        self.open_view = OpenView(pages, theme, self, page_widgets)
        self.notice_view = NoticeView(theme, self)
        self._views: dict[State, QWidget] = {
            State.CLOSED: self.clock,
            State.OPEN: self.open_view,
            State.NOTICE: self.notice_view,
        }
        for view in self._views.values():
            view.hide()
        self._fading: QWidget | None = None
        self._effect: QGraphicsOpacityEffect | None = None
        theme.changed.connect(self.update)

    # --- forma --------------------------------------------------------------

    def set_shape(self, shape: Shape) -> None:
        self._shape = shape
        self._center_views()
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._center_views()

    def _center_views(self) -> None:
        for view in self._views.values():
            view.move(round((self.width() - view.width()) / 2), 0)

    # --- conteúdo -----------------------------------------------------------

    def begin_transition(self, target: State) -> None:
        """Esconde o conteúdo atual; o do estado alvo entra com fade no fim."""
        self._end_fade()
        self._state = target
        for view in self._views.values():
            view.hide()

    def set_content_opacity(self, opacity: float) -> None:
        view = self._views.get(self._state)
        if view is None:
            return
        if self._fading is not view:
            self._end_fade()
            self._effect = QGraphicsOpacityEffect(view)
            view.setGraphicsEffect(self._effect)
            self._fading = view
            view.show()
        self._effect.setOpacity(opacity)

    def end_transition(self) -> None:
        """Conteúdo final visível, sem efeito de opacidade (o efeito só existe no fade)."""
        self._end_fade()
        view = self._views.get(self._state)
        if view is not None:
            view.show()

    def _end_fade(self) -> None:
        if self._fading is not None:
            self._fading.setGraphicsEffect(None)  # o Qt apaga o efeito
            self._fading = None
            self._effect = None

    # --- desenho ------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        theme = self._theme
        w, h = float(self.width()), float(self.height())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillPath(notch_path(0, w, h, self._shape.radius), qcolor(theme.notch_bg))
        minimal = self._state is State.MINIMAL
        border = theme.border_minimal if minimal else theme.border_notch
        pen = QPen(qcolor(border), NOTCH.border_width)
        painter.setPen(pen)
        inset = NOTCH.border_width / 2
        painter.drawPath(notch_path(0, w, h, self._shape.radius, inset=inset, closed=False))

    # --- eventos ------------------------------------------------------------

    def enterEvent(self, event) -> None:  # noqa: N802
        self.hover_changed.emit(True)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.hover_changed.emit(False)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed.emit()
        event.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event) -> None:  # noqa: N802
        # Só conta como perda de foco se a janela chegou a estar ativa.
        if event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                self._was_active = True
            elif self._was_active:
                self._was_active = False
                self.deactivated.emit()
        super().changeEvent(event)


class ShadowWindow(QWidget):
    """Sombra do notch aberto. Transparente a input: cliques passam para o app de baixo."""

    def __init__(self, theme: Theme) -> None:
        flags = (
            _FLAGS
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        super().__init__(None, flags)
        self.setObjectName("shadow")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._shape = Shape(0, 0, 0)
        self._strength = 0.0
        self._margin = NOTCH.shadow_margin

    def set_shape(self, shape: Shape, strength: float) -> None:
        self._shape = shape
        self._strength = strength
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._strength <= 0:
            return
        m = self._margin
        notch_w = self.width() - 2 * m
        notch_h = self.height() - m
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        base = QColor(qcolor(COLORS.shadow))
        # Camadas concêntricas: mais forte perto do notch, some na borda da margem.
        for i in range(m, 0, -2):
            falloff = 1 - i / m
            base.setAlphaF(
                min(1.0, NOTCH.shadow_max_alpha * self._strength * falloff**NOTCH.shadow_falloff)
            )
            painter.setBrush(base)
            painter.drawPath(
                notch_path(m - i, notch_w + 2 * i, notch_h + i, self._shape.radius + i)
            )
