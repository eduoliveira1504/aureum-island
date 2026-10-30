"""Widgets pequenos e reutilizáveis, desenhados pelo tema."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QSlider, QToolButton, QWidget

from aureum_island.island import icons
from aureum_island.theme import color
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Scheme, Theme, qcolor
from aureum_island.theme.tokens import NOTCH, PAGES, TYPOGRAPHY


def scheme(theme: Theme, window: bool) -> Scheme:
    """Cores do notch (sempre escuro) ou da janela de Configurações (tema escolhido)."""
    return theme.window if window else theme.notch


class ActionButton(QPushButton):
    """Botão de 30 px em pílula. Principal: fundo accent; secundário: contorno accent 30%.

    `window=True`: usa as cores da janela de Configurações.
    """

    def __init__(
        self,
        text: str,
        theme: Theme,
        *,
        primary: bool = False,
        window: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._theme = theme
        self._window = window
        self.primary = primary
        self.setFont(
            make_font(TYPOGRAPHY.family_body, PAGES.button_font_size, PAGES.button_font_weight)
        )
        self.setAccessibleName(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedHeight(PAGES.button_height)
        theme.changed.connect(self.update)

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(text)
        self.setAccessibleName(text)
        self.updateGeometry()

    def sizeHint(self) -> QSize:  # noqa: N802
        width = QFontMetrics(self.font()).horizontalAdvance(self.text())
        return QSize(width + 2 * PAGES.button_padding_x, PAGES.button_height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def paintEvent(self, event) -> None:  # noqa: N802
        theme = scheme(self._theme, self._window)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2
        hovered = self.underMouse() or self.isDown()
        if self.primary:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(theme.accent_hover if hovered else theme.accent))
            text_color = theme.on_accent
        else:
            painter.setPen(QPen(qcolor(theme.border), 1))
            if hovered:
                painter.setBrush(qcolor(theme.elevated))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            text_color = theme.text
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(qcolor(text_color))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        if self.hasFocus():
            ring = NOTCH.focus_ring_width
            # No botão principal o anel em accent sumiria; usa a cor do texto.
            ring_color = theme.text if self.primary else theme.accent
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(ring_color), ring))
            inner = QRectF(self.rect()).adjusted(ring / 2, ring / 2, -ring / 2, -ring / 2)
            painter.drawRoundedRect(inner, inner.height() / 2, inner.height() / 2)


class Segments(QWidget):
    """N segmentos em pílula: os `filled` primeiros em accent, o resto em track."""

    def __init__(
        self,
        theme: Theme,
        width: int,
        height: int,
        gap: int,
        *,
        total: int = 4,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._w, self._h, self._gap = width, height, gap
        self.total = total
        self.filled = 0
        theme.changed.connect(self.update)
        self._resize()

    def set_value(self, filled: int, total: int) -> None:
        if (filled, total) != (self.filled, self.total):
            self.filled, self.total = filled, total
            self._resize()
            self.update()

    def _resize(self) -> None:
        self.setFixedSize(self.total * self._w + (self.total - 1) * self._gap, self._h)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        w, h, gap = self._w, self._h, self._gap
        for i in range(self.total):
            n = self._theme.notch
            painter.setBrush(qcolor(n.accent if i < self.filled else n.border))
            painter.drawRoundedRect(QRectF(i * (w + gap), 0, w, h), h / 2, h / 2)


class IconButton(QToolButton):
    """Botão redondo só com ícone. `primary`: círculo em accent (ex.: play de 42 px)."""

    def __init__(
        self,
        icon_name: str,
        label: str,
        theme: Theme,
        *,
        size: int,
        icon_size: int,
        primary: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._icon_size = icon_size
        self.primary = primary
        self.icon_name = icon_name
        self.setFixedSize(size, size)
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.set_label(label)
        theme.changed.connect(self.update)

    def set_icon(self, icon_name: str, label: str) -> None:
        if (icon_name, label) != (self.icon_name, self.accessibleName()):
            self.icon_name = icon_name
            self.set_label(label)
            self.update()

    def set_label(self, label: str) -> None:
        self.setAccessibleName(label)
        self.setToolTip(label)

    def paintEvent(self, event) -> None:  # noqa: N802
        theme = self._theme.notch
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        hovered = self.isEnabled() and (self.underMouse() or self.isDown())
        if self.primary:
            fill = theme.accent_hover if hovered else theme.accent
            if not self.isEnabled():
                fill = theme.border
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(fill))
            painter.drawEllipse(rect)
            glyph_color = theme.on_accent if self.isEnabled() else theme.subtle
        else:
            if hovered:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(qcolor(theme.elevated))
                painter.drawEllipse(rect)
            # Desabilitado: fg-subtle (a WCAG isenta controles desabilitados).
            glyph_color = theme.text if self.isEnabled() else theme.subtle
        size = self._icon_size
        pm = icons.pixmap(self.icon_name, glyph_color, size, self.devicePixelRatioF())
        painter.drawPixmap(int((self.width() - size) / 2), int((self.height() - size) / 2), pm)
        if self.hasFocus():
            ring = NOTCH.focus_ring_width
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(theme.text if self.primary else theme.accent), ring))
            painter.drawEllipse(
                QRectF(self.rect()).adjusted(ring / 2, ring / 2, -ring / 2, -ring / 2)
            )


class ThemedSlider(QSlider):
    """QSlider horizontal desenhado pelo tema (mantém a acessibilidade do QSlider).

    Clicar em qualquer ponto pula para lá. `handle=0` desenha só a barra.
    """

    def __init__(
        self,
        theme: Theme,
        *,
        track_height: int,
        handle: int,
        window: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._theme = theme
        self._window = window
        self._track_h = track_height
        self._handle = handle
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        theme.changed.connect(self.update)

    def _value_at(self, x: float) -> int:
        span = max(1.0, self.width() - self._handle)
        ratio = min(1.0, max(0.0, (x - self._handle / 2) / span))
        return round(self.minimum() + ratio * (self.maximum() - self.minimum()))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.setSliderDown(True)
            self.setSliderPosition(self._value_at(event.position().x()))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self.isSliderDown():
            self.setSliderPosition(self._value_at(event.position().x()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self.isSliderDown():
            self.setSliderPosition(self._value_at(event.position().x()))
            self.setSliderDown(False)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        theme = scheme(self._theme, self._window)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        span = self.maximum() - self.minimum()
        ratio = (self.sliderPosition() - self.minimum()) / span if span else 0.0
        h, handle = self._track_h, self._handle
        y = (self.height() - h) / 2
        x0, width = handle / 2, self.width() - handle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(theme.border))
        painter.drawRoundedRect(QRectF(x0, y, width, h), h / 2, h / 2)
        fill = theme.accent if self.isEnabled() else theme.subtle
        painter.setBrush(qcolor(fill))
        if ratio > 0:
            painter.drawRoundedRect(QRectF(x0, y, width * ratio, h), h / 2, h / 2)
        cx = x0 + width * ratio
        if handle and self.isEnabled():
            painter.setBrush(qcolor(theme.text))
            painter.drawEllipse(
                QRectF(cx - handle / 2, (self.height() - handle) / 2, handle, handle)
            )
        if self.hasFocus():
            ring = NOTCH.focus_ring_width
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(theme.accent), ring))
            r = QRectF(self.rect()).adjusted(ring / 2, ring / 2, -ring / 2, -ring / 2)
            painter.drawRoundedRect(r, r.height() / 2, r.height() / 2)


def line_edit_style(theme: Theme, *, error: bool = False, window: bool = False) -> str:
    """Campo de texto no notch ou na janela de Configurações (cores e medidas do tema)."""
    colors = scheme(theme, window)
    border = colors.danger_text if error else colors.border
    background = colors.main if window else colors.panel
    return (
        "QLineEdit {"
        f" background: {background}; color: {colors.text};"
        f" border: 1px solid {_css(border)}; border-radius: {PAGES.button_height // 2}px;"
        f" padding: 0 {PAGES.button_padding_x}px;"
        f" selection-background-color: {colors.accent}; selection-color: {colors.on_accent};"
        "}"
        f"QLineEdit:focus {{ border: {NOTCH.focus_ring_width}px solid {colors.accent}; }}"
    )


def scrollbar_style(theme: Theme) -> str:
    w = PAGES.scrollbar_width
    return (
        f"QScrollBar:vertical {{ background: transparent; width: {w}px; margin: 0; }}"
        f"QScrollBar::handle:vertical {{ background: {theme.notch.border};"
        f" border-radius: {w // 2}px;"
        f" min-height: {PAGES.scrollbar_min_handle}px; }}"
        "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }"
        "QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }"
        "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: 0; }"
    )


def menu_style(theme: Theme) -> str:
    n = theme.notch
    return (
        f"QMenu {{ background: {n.main}; color: {n.text};"
        f" border: 1px solid {n.border}; padding: {PAGES.menu_padding}px; }}"
        f"QMenu::item {{ padding: {PAGES.menu_item_padding_y}px {PAGES.menu_item_padding_x}px;"
        f" border-radius: {PAGES.menu_radius}px; }}"
        f"QMenu::item:selected {{ background: {n.elevated}; color: {n.accent_text}; }}"
        f"QMenu::item:disabled {{ color: {n.subtle}; }}"
        f"QMenu::separator {{ height: 1px; background: {n.border};"
        f" margin: {PAGES.menu_padding}px {2 * PAGES.menu_padding}px; }}"
    )


def _css(value: str) -> str:
    """'#RRGGBBAA' -> 'rgba(...)' (o QSS usa #AARRGGBB, então evita ambiguidade)."""
    if len(value) == 9:
        r, g, b = color.parse_hex(value[:7])
        return f"rgba({r}, {g}, {b}, {int(value[7:9], 16)})"
    return value
