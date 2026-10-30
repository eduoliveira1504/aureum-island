"""Janela de Configurações (1000x620, sidebar 220, docs/DESIGN.md).

Seções: Geral, Calendário, Avisos, Foco e água, Aparência. Tudo se aplica na hora,
sem botão Salvar. Cores do esquema da janela (theme.window: Escuro, Claro ou Sistema).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from aureum_island.island import icons, win32
from aureum_island.island.widgets import Logo
from aureum_island.services.autostart import Autostart
from aureum_island.services.calendar_sync import CalendarSync
from aureum_island.services.hotkey import GlobalHotkey
from aureum_island.services.sound import Sound
from aureum_island.settings.appearance_section import AppearanceSection
from aureum_island.settings.calendar_section import CalendarSection
from aureum_island.settings.focus_water_section import FocusWaterSection
from aureum_island.settings.general_section import GeneralSection
from aureum_island.settings.notices_section import NoticesSection
from aureum_island.settings.store import SettingsStore
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme
from aureum_island.theme.tokens import NOTCH, PAGES, SETTINGS_WINDOW, TYPOGRAPHY

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


class SettingsWindow(QWidget):
    def __init__(
        self,
        theme: Theme,
        sync: CalendarSync,
        *,
        store: SettingsStore,
        hotkey: GlobalHotkey,
        autostart: Autostart,
        sound: Sound,
        parent: QWidget | None = None,
    ) -> None:
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
        brand = Logo(theme, SETTINGS_WINDOW.brand_logo, window=True, parent=sidebar)
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
        self.sections: dict[str, QWidget] = {
            "general": GeneralSection(theme, store, hotkey, autostart),
            "calendar": CalendarSection(theme, sync),
            "notices": NoticesSection(theme, store, sound),
            "focus_water": FocusWaterSection(theme, store),
            "appearance": AppearanceSection(theme, store),
        }
        for key, title in SECTIONS:
            widget = self.sections[key]
            widget.setObjectName("section")
            widget.setMaximumWidth(
                SETTINGS_WINDOW.width - SETTINGS_WINDOW.sidebar_width - 2 * SETTINGS_WINDOW.padding
            )
            scroll = QScrollArea(self.stack)
            scroll.setObjectName("sectionScroll")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setWidget(widget)
            self.stack.addWidget(scroll)
            item = QListWidgetItem(title, self.nav)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setSizeHint(item.sizeHint().expandedTo(self._nav_size()))
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        content = QWidget(self)
        content.setObjectName("content")
        inner = QVBoxLayout(content)
        p = SETTINGS_WINDOW.padding
        inner.setContentsMargins(p, p, p // 2, p)
        inner.addWidget(self.stack)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(sidebar)
        row.addWidget(content, 1)

        theme.changed.connect(self._apply_theme)
        self._apply_theme()
        self.show_section("general")

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
        win32.set_dark_title_bar(self, self._theme.window.name == "dark")
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def _apply_theme(self) -> None:
        w = self._theme.window
        r = SETTINGS_WINDOW.nav_item_radius
        sb = PAGES.scrollbar_width
        self.setStyleSheet(
            f"#settings {{ background: {w.panel}; }}"
            f"#settings QLabel {{ color: {w.text}; }}"
            f"#sidebar {{ background: {w.rail}; }}"
            f"#content, #sectionScroll, #section {{ background: {w.panel}; }}"
            f"#settings QLabel#hint {{ color: {w.text_muted}; }}"
            f"#settings QLabel#error {{ color: {w.danger_text}; }}"
            f"#settings QLabel#label {{ color: {w.text_muted}; }}"
            f"#settings QLabel#subtle {{ color: {w.subtle_text}; }}"
            f"#nav {{ background: transparent; border: 0; color: {w.text_muted};"
            " outline: 0; }"
            f"#nav::item {{ border-radius: {r}px; padding: 0 {SETTINGS_WINDOW.gap}px; }}"
            f"#nav::item:hover {{ background: {w.elevated}; color: {w.text}; }}"
            f"#nav::item:selected {{ background: {w.elevated}; color: {w.accent_text}; }}"
            f"#nav::item:selected:focus {{ border: {NOTCH.focus_ring_width}px solid {w.accent}; }}"
            f"#settings QScrollBar:vertical {{ background: transparent; width: {sb}px; }}"
            f"#settings QScrollBar::handle:vertical {{ background: {w.border};"
            f" border-radius: {sb // 2}px; min-height: {PAGES.scrollbar_min_handle}px; }}"
            "#settings QScrollBar::add-line, #settings QScrollBar::sub-line { height: 0; }"
            "#settings QScrollBar::add-page, #settings QScrollBar::sub-page"
            " { background: transparent; }"
            f"#settings QToolTip {{ background: {w.elevated}; color: {w.text};"
            f" border: 1px solid {w.border}; }}"
        )
        if self.isVisible():
            win32.set_dark_title_bar(self, w.name == "dark")
