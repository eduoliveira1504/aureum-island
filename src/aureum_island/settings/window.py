"""Janela de Configurações (1000x620, sidebar 220, docs/DESIGN.md).

Bloco 5: só a seção Calendário funciona; as outras entram no Bloco 6. O tema Claro/
Escuro/Sistema desta janela também é do Bloco 6; por enquanto ela usa o escuro.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from aureum_island.island import icons
from aureum_island.services.calendar_sync import CalendarSync
from aureum_island.settings.calendar_section import CalendarSection
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme
from aureum_island.theme.tokens import COLORS, NOTCH, SETTINGS_WINDOW, TYPOGRAPHY

SECTIONS = (
    ("general", "Geral"),
    ("calendar", "Calendário"),
    ("notices", "Avisos"),
    ("focus_water", "Foco e água"),
    ("appearance", "Aparência"),
)


def section_title(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setFont(
        make_font(
            TYPOGRAPHY.family_body,
            SETTINGS_WINDOW.section_title_size,
            SETTINGS_WINDOW.section_title_weight,
        )
    )
    label.setAccessibleName(text)
    return label


def hint(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("hint")  # cor no stylesheet da janela (text-muted)
    label.setWordWrap(True)
    label.setFont(make_font(TYPOGRAPHY.family_body, SETTINGS_WINDOW.hint_size))
    return label


class PlaceholderSection(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName(title)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_WINDOW.gap)
        layout.addWidget(section_title(title, self))
        layout.addWidget(hint("Disponível em breve.", self))
        layout.addStretch(1)


class SettingsWindow(QWidget):
    def __init__(self, theme: Theme, sync: CalendarSync, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("settings")
        self.setWindowTitle("Configurações · Aureum Island")
        self.setAccessibleName("Configurações")
        self.setWindowIcon(icons.icon("app", theme.accent, 32))
        self.resize(SETTINGS_WINDOW.width, SETTINGS_WINDOW.height)
        self.setMinimumSize(SETTINGS_WINDOW.width, SETTINGS_WINDOW.height)
        self._theme = theme

        sidebar = QWidget(self)
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SETTINGS_WINDOW.sidebar_width)
        brand = QLabel("AUREUM ISLAND", sidebar)
        brand.setObjectName("brand")
        brand.setFont(
            make_font(
                TYPOGRAPHY.family_title,
                TYPOGRAPHY.title_size_md,
                600,
                letter_spacing_em=TYPOGRAPHY.title_letter_spacing_em,
            )
        )
        self.nav = QListWidget(sidebar)
        self.nav.setObjectName("nav")
        self.nav.setAccessibleName("Seções")
        self.nav.setFont(make_font(TYPOGRAPHY.family_body, SETTINGS_WINDOW.body_size))
        side = QVBoxLayout(sidebar)
        pad = SETTINGS_WINDOW.sidebar_padding
        side.setContentsMargins(pad, SETTINGS_WINDOW.padding, pad, pad)
        side.setSpacing(SETTINGS_WINDOW.padding)
        side.addWidget(brand)
        side.addWidget(self.nav, 1)

        self.stack = QStackedWidget(self)
        self.sections: dict[str, QWidget] = {}
        for key, title in SECTIONS:
            widget = (
                CalendarSection(theme, sync) if key == "calendar" else PlaceholderSection(title)
            )
            self.sections[key] = widget
            self.stack.addWidget(widget)
            item = QListWidgetItem(title, self.nav)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setSizeHint(item.sizeHint().expandedTo(self._nav_size()))
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        content = QWidget(self)
        content.setObjectName("content")
        inner = QVBoxLayout(content)
        p = SETTINGS_WINDOW.padding
        inner.setContentsMargins(p, p, p, p)
        inner.addWidget(self.stack)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(sidebar)
        row.addWidget(content, 1)

        theme.changed.connect(self._apply_theme)
        self._apply_theme()
        self.show_section("calendar")

    @staticmethod
    def _nav_size():
        from PySide6.QtCore import QSize

        return QSize(0, SETTINGS_WINDOW.nav_item_height)

    def show_section(self, key: str) -> None:
        keys = [k for k, _ in SECTIONS]
        if key in keys:
            self.nav.setCurrentRow(keys.index(key))

    def open(self, section: str | None = None) -> None:
        if section:
            self.show_section(section)
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def _apply_theme(self) -> None:
        t = self._theme
        r = SETTINGS_WINDOW.nav_item_radius
        self.setStyleSheet(
            f"#settings {{ background: {COLORS.panel}; }}"
            f"#settings QLabel {{ color: {COLORS.text}; }}"
            f"#sidebar {{ background: {COLORS.sidebar}; }}"
            f"#content {{ background: {COLORS.panel}; }}"
            f"#settings QLabel#brand {{ color: {t.accent_text}; }}"
            f"#settings QLabel#hint {{ color: {COLORS.text_muted}; }}"
            f"#settings QLabel#error {{ color: {COLORS.danger_text}; }}"
            f"#nav {{ background: transparent; border: 0; color: {COLORS.text_muted};"
            " outline: 0; }"
            f"#nav::item {{ border-radius: {r}px; padding: 0 {SETTINGS_WINDOW.gap}px; }}"
            f"#nav::item:hover {{ background: {COLORS.surface}; color: {COLORS.text}; }}"
            f"#nav::item:selected {{ background: {COLORS.surface}; color: {t.accent_text}; }}"
            f"#nav::item:selected:focus {{ border: {NOTCH.focus_ring_width}px solid {t.accent}; }}"
        )
