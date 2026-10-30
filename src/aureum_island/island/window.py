"""Janelas do notch e da sombra.

Em repouso o notch tem exatamente o tamanho do contorno visível (sem margem): fora dele a
janela não existe. A sombra mora numa segunda janela, transparente a cliques, logo abaixo
no z-order. Animações: ver NotchWindow e controller._animate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsOpacityEffect, QStackedWidget, QVBoxLayout, QWidget

from aureum_island.island.clock import ClockView
from aureum_island.island.geometry import Shape
from aureum_island.island.motion import FrameClock, enter_curve
from aureum_island.island.notices import NoticeView
from aureum_island.island.page_bar import PageBar
from aureum_island.island.state import State
from aureum_island.pages import PageInfo
from aureum_island.pages.placeholder import PlaceholderPage
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import MOTION, NOTCH, SHADOW

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
            widget = page_widgets.get(page.id) or PlaceholderPage(page, theme)
            self.stack.addWidget(widget)
        self.bar = PageBar(pages, theme, self)
        self.bar.page_changed.connect(self._on_page)
        self._page_clock: FrameClock | None = None
        self._page_widget: QWidget | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.stack)
        layout.addWidget(self.bar)
        self.setFixedSize(NOTCH.open_width, NOTCH.open_content_height + NOTCH.open_bar_height)

    def set_page(self, index: int) -> None:
        self.bar.set_current(index)
        self.stack.setCurrentIndex(self.bar.current_index)

    @property
    def page_animating(self) -> bool:
        return self._page_clock is not None

    def _on_page(self, index: int) -> None:
        old = self.stack.currentIndex()
        self._finish_page()
        self.stack.setCurrentIndex(index)
        if old == index or old < 0 or not self.isVisible():
            return
        # A página nova entra deslizando um pouco do lado de onde veio, com fade.
        direction = 1 if index > old else -1
        widget = self.stack.currentWidget()
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        self._page_widget = widget

        def frame(t: float) -> None:
            e = enter_curve(t)
            effect.setOpacity(e)
            widget.move(round(direction * MOTION.page_shift * (1 - e)), 0)

        self._page_clock = FrameClock(MOTION.page_ms, frame, self._finish_page, self)
        self._page_clock.start()

    def _finish_page(self) -> None:
        if self._page_clock is not None:
            clock, self._page_clock = self._page_clock, None
            clock.stop()
            clock.deleteLater()
        if self._page_widget is not None:
            widget, self._page_widget = self._page_widget, None
            widget.setGraphicsEffect(None)  # o Qt apaga o efeito
            widget.move(0, 0)

    def hideEvent(self, event) -> None:  # noqa: N802
        self._finish_page()
        super().hideEvent(event)


class NotchWindow(QWidget):
    """Janela do notch. Em repouso tem exatamente o tamanho do contorno. Durante uma
    animação ela fica do tamanho maior (uma mudança de geometria no começo e outra no fim)
    e só o desenho muda a cada quadro; o conteúdo mora num recipiente do tamanho da forma,
    que o revela enquanto cresce. Hover e clique contam só dentro da forma."""

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
        self._hovered = False

        # Recipiente do tamanho da forma: o conteúdo nunca vaza para fora do contorno.
        self.content = QWidget(self)
        self.content.setObjectName("notch-content")
        self.content.installEventFilter(self)
        self.clock = ClockView(theme, self.content)
        self.open_view = OpenView(pages, theme, self.content, page_widgets)
        self.notice_view = NoticeView(theme, self.content)
        self._views: dict[State, QWidget] = {
            State.CLOSED: self.clock,
            State.OPEN: self.open_view,
            State.NOTICE: self.notice_view,
        }
        for view in self._views.values():
            view.hide()
        # Fades: o conteúdo que sai e o que entra, cada um com seu efeito de opacidade.
        self._leaving: QWidget | None = None
        self._leaving_from = 1.0
        self._entering: QWidget | None = None
        self._entering_opacity = 1.0
        theme.changed.connect(self.update)

    # --- forma --------------------------------------------------------------

    def set_shape(self, shape: Shape) -> None:
        self._shape = shape
        self._place_content()
        self.update()

    def shape_rect(self) -> QRect:
        """Retângulo da forma atual dentro da janela (centralizado, colado no topo)."""
        width = round(min(self._shape.width, self.width()))
        height = round(min(max(self._shape.height, 0.0), self.height()))
        return QRect(round((self.width() - width) / 2), 0, width, height)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._place_content()

    def _place_content(self) -> None:
        rect = self.shape_rect()
        self.content.setGeometry(rect)
        # As vistas ficam paradas em relação à janela; o recipiente só recorta.
        for view in self._views.values():
            view.move(round((self.width() - view.width()) / 2) - rect.x(), 0)

    # --- conteúdo -----------------------------------------------------------

    def begin_transition(self, target: State | None) -> None:
        """O conteúdo visível passa a sair (fade-out); o do estado alvo entra com fade.
        `target=None`: nada entra (o notch está se recolhendo para a tela cheia)."""
        current = self._entering if self._entering is not None else self._visible_view()
        current_opacity = self._entering_opacity if self._entering is not None else 1.0
        self._clear_fades()
        if target is not None:
            self._state = target
        entering = self._views.get(target) if target is not None else None
        for view in self._views.values():
            if view is not current and view is not entering:
                view.hide()
        if current is not None and current is not entering and current.isVisible():
            self._leaving = current
            self._leaving_from = current_opacity
            current.setGraphicsEffect(QGraphicsOpacityEffect(current))
            current.graphicsEffect().setOpacity(current_opacity)
        if entering is not None:
            self._entering = entering
            # Se já estava visível (ex.: reabriu no meio do fechamento), segue dali.
            self._entering_opacity = current_opacity if entering is current else 0.0
            entering.setGraphicsEffect(QGraphicsOpacityEffect(entering))
            entering.graphicsEffect().setOpacity(self._entering_opacity)
            entering.show()

    def set_fades(self, leaving: float, entering: float) -> None:
        """leaving: 1 = ainda visível, 0 = sumiu. entering: 0 = invisível, 1 = pronto."""
        if self._leaving is not None:
            self._leaving.graphicsEffect().setOpacity(self._leaving_from * leaving)
        if self._entering is not None:
            self._entering_opacity = max(self._entering_opacity, entering)
            self._entering.graphicsEffect().setOpacity(self._entering_opacity)

    def end_transition(self) -> None:
        """Conteúdo final visível, sem efeitos de opacidade (só existem durante o fade)."""
        self._clear_fades()
        for state, view in self._views.items():
            view.setVisible(state is self._state)

    def hide_content(self) -> None:
        """Nenhum conteúdo visível (antes de o notch descer de volta da tela cheia)."""
        self._clear_fades()
        for view in self._views.values():
            view.hide()

    def _clear_fades(self) -> None:
        if self._leaving is not None:
            self._leaving.setGraphicsEffect(None)  # o Qt apaga o efeito
            self._leaving.hide()
            self._leaving = None
        if self._entering is not None:
            self._entering.setGraphicsEffect(None)
            self._entering = None
        self._entering_opacity = 1.0

    def _visible_view(self) -> QWidget | None:
        return next((v for v in self._views.values() if v.isVisible()), None)

    # --- desenho ------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        theme = self._theme
        rect = self.shape_rect()
        if rect.height() <= 0:
            return
        x, w, h = float(rect.x()), float(rect.width()), float(rect.height())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillPath(notch_path(x, w, h, self._shape.radius), qcolor(theme.notch_bg))
        minimal = self._state is State.MINIMAL
        border = theme.border_minimal if minimal else theme.border_notch
        pen = QPen(qcolor(border), NOTCH.border_width)
        painter.setPen(pen)
        inset = NOTCH.border_width / 2
        painter.drawPath(notch_path(x, w, h, self._shape.radius, inset=inset, closed=False))

    # --- eventos ------------------------------------------------------------

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        # Hover pelo recipiente (do tamanho da forma), não pela janela, que fica maior
        # durante as animações. Em repouso os dois coincidem.
        if watched is self.content and event.type() in (QEvent.Type.Enter, QEvent.Type.Leave):
            self._set_hovered(event.type() == QEvent.Type.Enter)
        return super().eventFilter(watched, event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._set_hovered(False)

    def _set_hovered(self, inside: bool) -> None:
        if inside != self._hovered:
            self._hovered = inside
            self.hover_changed.emit(inside)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self.shape_rect().contains(event.position().toPoint()):
            event.ignore()  # sobra transparente da janela durante uma animação
            return
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
    """Sombra do notch aberto. Transparente a input: cliques passam para o app de baixo.
    Como o notch, fica do tamanho maior durante a animação e só o desenho muda."""

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
        if self._strength <= 0 or self._shape.height <= 0:
            return
        m = self._margin
        notch_w = min(self._shape.width, self.width() - 2 * m)
        notch_h = min(self._shape.height, self.height() - m)
        x = (self.width() - notch_w) / 2
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        base = QColor(qcolor(SHADOW))
        # Camadas concêntricas: mais forte perto do notch, some na borda da margem.
        for i in range(m, 0, -2):
            falloff = 1 - i / m
            base.setAlphaF(
                min(1.0, NOTCH.shadow_max_alpha * self._strength * falloff**NOTCH.shadow_falloff)
            )
            painter.setBrush(base)
            painter.drawPath(
                notch_path(x - i, notch_w + 2 * i, notch_h + i, self._shape.radius + i)
            )
