"""Monta o app: configurações, tema, notch, atalho global, tela cheia e tray."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from aureum_island.island import icons
from aureum_island.island.controller import IslandController
from aureum_island.services.fullscreen import create_fullscreen_watcher
from aureum_island.services.hotkey import GlobalHotkey
from aureum_island.services.storage import paths, settings
from aureum_island.services.storage.settings import Settings
from aureum_island.services.system_events import SystemEvents
from aureum_island.theme.theme import Theme

log = logging.getLogger(__name__)

_TRAY_ICON_SIZE = 32


class AureumIsland(QObject):
    def __init__(self, app: QApplication, *, debug_paint: bool = False) -> None:
        super().__init__(app)
        self._app = app
        self._settings_path = paths.settings_path()
        self.settings = settings.load(self._settings_path)
        self.theme = Theme.from_settings(self.settings, self)

        self.controller = IslandController(
            self.theme,
            minimal=self.settings.mode == "minimal",
            last_page=self.settings.last_page,
            parent=self,
        )
        self.controller.page_changed.connect(lambda page: self.update_settings(last_page=page))
        self.controller.settings_requested.connect(
            lambda: log.info("Configurações: chega no Bloco 6")
        )

        self.events = SystemEvents(self)
        self.events.time_changed.connect(self.controller.notch.clock.refresh)
        self.events.resumed.connect(self.controller.notch.clock.refresh)

        self.hotkey = GlobalHotkey(self.events, self)
        self.hotkey.activated.connect(self.controller.toggle)
        self.hotkey.register(self.settings.hotkey)

        self.fullscreen = create_fullscreen_watcher(self, debug=debug_paint)
        self.fullscreen.fullscreen_changed.connect(self.controller.set_suppressed)
        if self.settings.hide_on_fullscreen:
            self.fullscreen.start()

        self.tray = self._build_tray()
        app.aboutToQuit.connect(self._shutdown)

    def start(self) -> None:
        self.controller.show()
        self.tray.show()

    def update_settings(self, **changes) -> Settings:
        self.settings = self.settings.with_changes(**changes)
        try:
            settings.save(self.settings, self._settings_path)
        except OSError:
            log.exception("não foi possível salvar as configurações")
        return self.settings

    def _build_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(icons.icon("app", self.theme.accent, _TRAY_ICON_SIZE), self)
        tray.setToolTip("Aureum Island")
        menu = QMenu()
        open_action = QAction("Abrir", menu)
        open_action.triggered.connect(self.controller.open)
        settings_action = QAction("Configurações", menu)
        settings_action.setEnabled(False)  # Bloco 6
        quit_action = QAction("Sair", menu)
        quit_action.triggered.connect(self._app.quit)
        menu.addAction(open_action)
        menu.addAction(settings_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        self._tray_menu = menu  # QSystemTrayIcon não assume a posse do menu
        tray.activated.connect(self._on_tray_activated)
        self.theme.changed.connect(
            lambda: tray.setIcon(icons.icon("app", self.theme.accent, _TRAY_ICON_SIZE))
        )
        return tray

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.controller.open()

    def _shutdown(self) -> None:
        self.hotkey.unregister()
        self.fullscreen.stop()
        self.events.close()
        self.tray.hide()
