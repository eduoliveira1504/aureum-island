"""Widgets pequenos e reutilizáveis, desenhados pelo tema."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QSlider, QToolButton, QWidget

from aureum_island.island import icons
from aureum_island.theme import color
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import BORDER_ALPHA_DIVIDER, COLORS, NOTCH, PAGES, TYPOGRAPHY


class ActionButton(QPushButton):
    """Botão de 30 px em pílula. Principal: fundo accent; secundário: contorno accent 30%."""

    def __init__(
        self, text: str, theme: Theme, *, primary: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(text, parent)
        self._theme = theme
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
        theme = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2
        hovered = self.underMouse() or self.isDown()
        if self.primary:
            fill = (
                color.mix(theme.accent, COLORS.on_accent_light, 0.12) if hovered else theme.accent
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(fill))
            text_color = theme.on_accent
        else:
            painter.setPen(QPen(qcolor(theme.border_button), 1))
            if hovered:
                painter.setBrush(qcolor(color.with_alpha(theme.accent, BORDER_ALPHA_DIVIDER)))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            text_color = COLORS.text
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(qcolor(text_color))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        if self.hasFocus():
            ring = NOTCH.focus_ring_width
            # No botão principal o anel em accent sumiria; usa a cor do texto.
            ring_color = COLORS.text if self.primary else theme.accent
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
            painter.setBrush(qcolor(self._theme.accent if i < self.filled else COLORS.track))
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
        theme = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        hovered = self.isEnabled() and (self.underMouse() or self.isDown())
        if self.primary:
            fill = (
                color.mix(theme.accent, COLORS.on_accent_light, 0.12) if hovered else theme.accent
            )
            if not self.isEnabled():
                fill = COLORS.track
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(fill))
            painter.drawEllipse(rect)
            glyph_color = theme.on_accent if self.isEnabled() else COLORS.text_dim
        else:
            if hovered:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(qcolor(color.with_alpha(theme.accent, BORDER_ALPHA_DIVIDER)))
                painter.drawEllipse(rect)
            glyph_color = COLORS.text if self.isEnabled() else COLORS.text_dim
        size = self._icon_size
        pm = icons.pixmap(self.icon_name, glyph_color, size, self.devicePixelRatioF())
        painter.drawPixmap(int((self.width() - size) / 2), int((self.height() - size) / 2), pm)
        if self.hasFocus():
            ring = NOTCH.focus_ring_width
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(COLORS.text if self.primary else theme.accent), ring))
            painter.drawEllipse(
                QRectF(self.rect()).adjusted(ring / 2, ring / 2, -ring / 2, -ring / 2)
            )


class ThemedSlider(QSlider):
    """QSlider horizontal desenhado pelo tema (mantém a acessibilidade do QSlider).

    Clicar em qualquer ponto pula para lá. `handle=0` desenha só a barra.
    """

    def __init__(
        self, theme: Theme, *, track_height: int, handle: int, parent: QWidget | None = None
    ) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._theme = theme
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
        theme = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        span = self.maximum() - self.minimum()
        ratio = (self.sliderPosition() - self.minimum()) / span if span else 0.0
        h, handle = self._track_h, self._handle
        y = (self.height() - h) / 2
        x0, width = handle / 2, self.width() - handle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(COLORS.track))
        painter.drawRoundedRect(QRectF(x0, y, width, h), h / 2, h / 2)
        fill = theme.accent if self.isEnabled() else COLORS.text_dim
        painter.setBrush(qcolor(fill))
        if ratio > 0:
            painter.drawRoundedRect(QRectF(x0, y, width * ratio, h), h / 2, h / 2)
        cx = x0 + width * ratio
        if handle and self.isEnabled():
            painter.setBrush(qcolor(COLORS.text))
            painter.drawEllipse(
                QRectF(cx - handle / 2, (self.height() - handle) / 2, handle, handle)
            )
        if self.hasFocus():
            ring = NOTCH.focus_ring_width
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(theme.accent), ring))
            r = QRectF(self.rect()).adjusted(ring / 2, ring / 2, -ring / 2, -ring / 2)
            painter.drawRoundedRect(r, r.height() / 2, r.height() / 2)


def line_edit_style(theme: Theme, *, error: bool = False) -> str:
    """Campo de texto no notch (cores e medidas do tema)."""
    border = COLORS.danger_text if error else theme.border_button
    return (
        "QLineEdit {"
        f" background: {COLORS.surface}; color: {COLORS.text};"
        f" border: 1px solid {_css(border)}; border-radius: {PAGES.button_height // 2}px;"
        f" padding: 0 {PAGES.button_padding_x}px;"
        f" selection-background-color: {theme.accent}; selection-color: {theme.on_accent};"
        "}"
        f"QLineEdit:focus {{ border: {NOTCH.focus_ring_width}px solid {theme.accent}; }}"
    )


def scrollbar_style() -> str:
    w = PAGES.scrollbar_width
    return (
        f"QScrollBar:vertical {{ background: transparent; width: {w}px; margin: 0; }}"
        f"QScrollBar::handle:vertical {{ background: {COLORS.track}; border-radius: {w // 2}px;"
        f" min-height: {PAGES.scrollbar_min_handle}px; }}"
        "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }"
        "QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }"
        "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: 0; }"
    )


def menu_style(theme: Theme) -> str:
    return (
        f"QMenu {{ background: {COLORS.panel}; color: {COLORS.text};"
        f" border: 1px solid {_css(theme.border_divider)}; padding: {PAGES.menu_padding}px; }}"
        f"QMenu::item {{ padding: {PAGES.menu_item_padding_y}px {PAGES.menu_item_padding_x}px;"
        f" border-radius: {PAGES.menu_radius}px; }}"
        f"QMenu::item:selected {{ background: {COLORS.surface}; color: {theme.accent_text}; }}"
        f"QMenu::item:disabled {{ color: {COLORS.text_dim}; }}"
        f"QMenu::separator {{ height: 1px; background: {_css(theme.border_divider)};"
        f" margin: {PAGES.menu_padding}px {2 * PAGES.menu_padding}px; }}"
    )


def _css(value: str) -> str:
    """'#RRGGBBAA' -> 'rgba(...)' (o QSS usa #AARRGGBB, então evita ambiguidade)."""
    if len(value) == 9:
        r, g, b = color.parse_hex(value[:7])
        return f"rgba({r}, {g}, {b}, {int(value[7:9], 16)})"
    return value
