"""Página provisória: só o título (Sora, caixa alta) com o nome da página."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from aureum_island.pages import PageInfo
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import TYPOGRAPHY


class PlaceholderPage(QWidget):
    def __init__(self, page: PageInfo, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setObjectName(f"page-{page.id}")
        self.setAccessibleName(page.label)
        title = QLabel(page.label.upper(), self)
        title.setFont(
            make_font(
                TYPOGRAPHY.family_title,
                TYPOGRAPHY.title_size_md,
                600,
                letter_spacing_em=TYPOGRAPHY.title_letter_spacing_em,
            )
        )
        self._title = title
        self._apply_theme()
        theme.changed.connect(self._apply_theme)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(title)

    def _apply_theme(self) -> None:
        palette = self._title.palette()
        palette.setColor(QPalette.ColorRole.WindowText, qcolor(self._theme.notch.text_muted))
        self._title.setPalette(palette)
