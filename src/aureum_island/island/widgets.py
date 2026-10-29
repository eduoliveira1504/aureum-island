"""Widgets pequenos e reutilizáveis, desenhados pelo tema."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QWidget

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
