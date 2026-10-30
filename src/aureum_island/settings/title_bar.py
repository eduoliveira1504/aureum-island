"""Barra própria da janela de Configurações, igual à do Aureum Voice.

Logo (30 px, accent-text) + nome em Sora no fundo bg-rail, e os botões de janela
(minimizar, maximizar/restaurar, fechar) no desenho do Windows, nas cores do tema.
Arrastar a barra move a janela (com encaixe nas laterais); clique duplo maximiza.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QWidget

from aureum_island.island.widgets import Logo
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import SETTINGS_WINDOW, TYPOGRAPHY

PRODUCT_NAME = "Aureum Island"


class WindowButton(QAbstractButton):
    """Minimizar, maximizar/restaurar ou fechar. Fora do Tab, como no Windows (Alt+F4,
    Win+setas e Alt+Espaço continuam valendo); nome acessível para leitores de tela."""

    def __init__(self, kind: str, label: str, theme: Theme, parent: QWidget) -> None:
        super().__init__(parent)
        self.kind = kind
        self._theme = theme
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(SETTINGS_WINDOW.window_button_width, SETTINGS_WINDOW.title_bar_height)
        theme.changed.connect(self.update)

    def set_kind(self, kind: str, label: str) -> None:
        if kind != self.kind:
            self.kind = kind
            self.setAccessibleName(label)
            self.setToolTip(label)
            self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        w = self._theme.window
        painter = QPainter(self)
        hovered = self.underMouse() or self.isDown()
        ink = w.text
        if hovered:
            if self.kind == "close":
                painter.fillRect(self.rect(), qcolor(w.danger))
                ink = w.on_danger
            else:
                painter.fillRect(self.rect(), qcolor(w.elevated))
        g = SETTINGS_WINDOW.window_glyph
        c = QRectF(self.rect()).center()
        box = QRectF(round(c.x() - g / 2) + 0.5, round(c.y() - g / 2) + 0.5, g, g)
        pen = QPen(qcolor(ink), 1)
        painter.setPen(pen)
        if self.kind == "minimize":
            painter.drawLine(QPointF(box.left(), c.y()), QPointF(box.right(), c.y()))
        elif self.kind == "maximize":
            painter.drawRect(box)
        elif self.kind == "restore":
            o = 2
            front = box.adjusted(0, o, -o, 0)
            painter.drawRect(front)
            painter.drawPolyline(
                [
                    QPointF(box.left() + o, front.top()),
                    QPointF(box.left() + o, box.top()),
                    QPointF(box.right(), box.top()),
                    QPointF(box.right(), front.bottom() - o),
                    QPointF(front.right(), front.bottom() - o),
                ]
            )
        else:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.drawLine(box.topLeft(), box.bottomRight())
            painter.drawLine(box.topRight(), box.bottomLeft())


class TitleBar(QWidget):
    def __init__(self, theme: Theme, window: QWidget) -> None:
        super().__init__(window)
        self.setObjectName("titleBar")
        self._theme = theme
        self._window = window
        self.setFixedHeight(SETTINGS_WINDOW.title_bar_height)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.logo = Logo(theme, SETTINGS_WINDOW.title_logo, window=True, parent=self)
        self.title = QLabel(PRODUCT_NAME, self)
        self.title.setObjectName("windowTitle")
        self.title.setFont(
            make_font(
                TYPOGRAPHY.family_title,
                SETTINGS_WINDOW.title_text_size,
                SETTINGS_WINDOW.title_text_weight,
                letter_spacing_em=SETTINGS_WINDOW.title_text_letter_spacing_em,
            )
        )
        self.minimize = WindowButton("minimize", "Minimizar", theme, self)
        self.maximize = WindowButton("maximize", "Maximizar", theme, self)
        self.close_button = WindowButton("close", "Fechar", theme, self)
        self.minimize.clicked.connect(window.showMinimized)
        self.maximize.clicked.connect(self.toggle_maximized)
        self.close_button.clicked.connect(window.close)

        row = QHBoxLayout(self)
        row.setContentsMargins(SETTINGS_WINDOW.title_padding_x, 0, 0, 0)
        row.setSpacing(SETTINGS_WINDOW.title_logo_gap)
        row.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.title, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addStretch(1)
        buttons = QHBoxLayout()
        buttons.setSpacing(0)
        for button in (self.minimize, self.maximize, self.close_button):
            buttons.addWidget(button)
        row.addLayout(buttons)

    def toggle_maximized(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def sync_state(self) -> None:
        """Ícone e nome do botão do meio seguem o estado da janela."""
        if self._window.isMaximized():
            self.maximize.set_kind("restore", "Restaurar")
        else:
            self.maximize.set_kind("maximize", "Maximizar")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
