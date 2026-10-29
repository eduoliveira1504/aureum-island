"""Página provisória: só o título em Cinzel com o nome da página."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from aureum_island.pages import PageInfo
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import qcolor
from aureum_island.theme.tokens import COLORS, TYPOGRAPHY


class PlaceholderPage(QWidget):
    def __init__(self, page: PageInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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
        palette = title.palette()
        palette.setColor(QPalette.ColorRole.WindowText, qcolor(COLORS.text_muted))
        title.setPalette(palette)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(title)
