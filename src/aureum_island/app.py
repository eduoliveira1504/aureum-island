"""Monta o app: configurações, tema, notch, serviços, avisos, atalho global, tela cheia e tray."""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from aureum_island.island import icons
from aureum_island.island.controller import IslandController
from aureum_island.island.notices import Notice, NoticeAction, NoticeCenter, collapse_missed
from aureum_island.pages.calendar import CalendarPage
from aureum_island.pages.focus import FocusPage
from aureum_island.pages.focus_model import FocusConfig, FocusState, Phase
from aureum_island.pages.music import MusicPage
from aureum_island.pages.tasks import TasksPage
from aureum_island.pages.water import WaterPage, format_ml
from aureum_island.pages.water_model import WaterConfig, parse_time
from aureum_island.services import events as event_service
from aureum_island.services import focus as focus_service
from aureum_island.services import tasks as task_service
from aureum_island.services import water as water_service
from aureum_island.services.calendar_sync import CalendarSync
from aureum_island.services.events import EventRepo, EventService
from aureum_island.services.focus import FocusService
from aureum_island.services.fullscreen import create_fullscreen_watcher
from aureum_island.services.hotkey import GlobalHotkey
from aureum_island.services.lyrics import LyricsService
from aureum_island.services.media import create_media_service
from aureum_island.services.reminders import Due, ReminderEngine
from aureum_island.services.sound import Sound
from aureum_island.services.storage import db, paths, settings
from aureum_island.services.storage.settings import Settings
from aureum_island.services.storage.tasks import TaskRepo
from aureum_island.services.system_events import SystemEvents
from aureum_island.services.tasks import TaskService
from aureum_island.services.volume import create_volume_service
from aureum_island.services.water import WaterService
from aureum_island.theme.theme import Theme
from aureum_island.theme.tokens import NOTICE

log = logging.getLogger(__name__)

_TRAY_ICON_SIZE = 32
_BREAK_NAME = {Phase.SHORT_BREAK: "pausa curta", Phase.LONG_BREAK: "pausa longa"}


def _hhmm(dt: datetime) -> str:
    local = dt.astimezone()
    return f"{local.hour:02d}:{local.minute:02d}"


class AureumIsland(QObject):
    def __init__(self, app: QApplication, *, debug_paint: bool = False) -> None:
        super().__init__(app)
        self._app = app
        self._settings_path = paths.settings_path()
        self.settings = settings.load(self._settings_path)
        self.theme = Theme.from_settings(self.settings, self)
        self.conn = db.connect(paths.db_path())

        # Serviços (provedores de avisos)
        self.tasks = TaskService(
            TaskRepo(self.conn),
            global_offset=lambda: self.settings.reminder_offset_min,
            parent=self,
        )
        s = self.settings
        state = FocusState.from_dict(s.focus_state) if s.focus_state else None
        self.focus = FocusService(
            FocusConfig(
                s.focus_minutes, s.short_break_minutes, s.long_break_minutes, s.long_break_every
            ),
            state,
            save=lambda data: self.update_settings(focus_state=data),
            parent=self,
        )

        self.water = WaterService(self.conn, config=self._water_config, parent=self)
        self.calendar_events = EventService(
            EventRepo(self.conn),
            global_offset=lambda: self.settings.reminder_offset_min,
            parent=self,
        )
        self.calendar_sync = CalendarSync(
            self.conn,
            self.calendar_events.repo,
            global_offset=lambda: self.settings.reminder_offset_min,
            parent=self,
        )
        self.calendar_sync.events_changed.connect(self.calendar_events.changed)
        self.media = create_media_service(self)
        self.volume = create_volume_service(self)
        self.lyrics = LyricsService(
            self.conn, enabled=lambda: self.settings.lyrics_enabled, parent=self
        )

        # Páginas reais; as outras seguem provisórias.
        self.tasks_page = TasksPage(
            self.tasks, self.theme, global_offset=lambda: self.settings.reminder_offset_min
        )
        self.focus_page = FocusPage(self.focus, self.theme)
        self.water_page = WaterPage(self.water, self.theme)
        self.music_page = MusicPage(self.media, self.volume, self.lyrics, self.theme)
        self.calendar_page = CalendarPage(
            self.tasks,
            self.calendar_events,
            self.calendar_sync,
            self.theme,
            week_start=lambda: self.settings.week_start,
        )

        self.controller = IslandController(
            self.theme,
            minimal=s.mode == "minimal",
            last_page=s.last_page,
            page_widgets={
                "tasks": self.tasks_page,
                "focus": self.focus_page,
                "water": self.water_page,
                "music": self.music_page,
                "calendar": self.calendar_page,
            },
            parent=self,
        )
        self.controller.page_changed.connect(lambda page: self.update_settings(last_page=page))
        self.controller.settings_requested.connect(self.open_settings)
        for page in (self.tasks_page, self.calendar_page):
            page.keyboard_requested.connect(self.controller.request_keyboard)
            page.popup_closed.connect(self.controller.popup_closed)
        self.settings_window = None  # criada na primeira abertura

        # Som, tray e avisos
        self.sound = Sound(self)
        self.sound.configure(enabled=s.sound_enabled, volume=s.sound_volume)
        self.tray = self._build_tray()
        self.notices = NoticeCenter(
            self.controller,
            play_sound=self.sound.play,
            native=self._native_notification,
            open_tasks=lambda: self.controller.open_page("tasks"),
            parent=self,
        )

        # Motor de avisos
        self.reminders = ReminderEngine(self.conn, parent=self)
        self.reminders.register(self.tasks)
        self.reminders.register(self.focus)
        self.reminders.register(self.water)
        self.reminders.register(self.calendar_events)
        self.reminders.fired.connect(self._on_fired)
        self.reminders.missed.connect(self._on_missed)

        # Eventos do Windows
        self.events = SystemEvents(self)
        for signal in (self.events.time_changed, self.events.resumed):
            signal.connect(self.controller.notch.clock.refresh)
            signal.connect(self.reminders.catch_up)
        self.events.resumed.connect(self.calendar_sync.sync_all)

        self.hotkey = GlobalHotkey(self.events, self)
        self.hotkey.activated.connect(self.controller.toggle)
        self.hotkey.register(s.hotkey)
        self.update_settings(
            hotkey_active=self.hotkey.active, hotkey_status=self.hotkey.status.value
        )

        self.fullscreen = create_fullscreen_watcher(self, debug=debug_paint)
        self.fullscreen.fullscreen_changed.connect(self.controller.set_suppressed)
        if s.hide_on_fullscreen:
            self.fullscreen.start()

        app.aboutToQuit.connect(self._shutdown)

    def start(self) -> None:
        self.controller.show()
        self.tray.show()
        self.media.start()
        self.calendar_sync.start()
        if self.settings.sound_enabled:
            self.sound.preload()
        self.reminders.start()  # perdidos com o app fechado
        self.focus.settle()  # fase que venceu há mais de 12 h (sem aviso)

    def open_settings(self, section: str | None = None) -> None:
        if self.settings_window is None:
            from aureum_island.settings.window import SettingsWindow

            self.settings_window = SettingsWindow(self.theme, self.calendar_sync)
        self.settings_window.open(section)

    def open_calendar_day(self, when: datetime) -> None:
        self.controller.open_page("calendar")
        self.calendar_page.select_day(when.astimezone().date())

    def update_settings(self, **changes) -> Settings:
        self.settings = self.settings.with_changes(**changes)
        try:
            settings.save(self.settings, self._settings_path)
        except OSError:
            log.exception("não foi possível salvar as configurações")
        return self.settings

    def _water_config(self) -> WaterConfig:
        s = self.settings
        return WaterConfig(
            goal_ml=s.water_goal_ml,
            cup_ml=s.water_cup_ml,
            reminders=s.water_reminders,
            interval_min=s.water_interval_min,
            start=parse_time(s.water_start),
            end=parse_time(s.water_end),
        )

    # --- avisos -------------------------------------------------------------

    def _on_fired(self, dues: list[Due]) -> None:
        for due in dues:
            notice = self._notice_for(due, missed=False)
            if notice is not None:
                self.notices.push(notice)

    def _on_missed(self, dues: list[Due]) -> None:
        notices = [n for d in dues if (n := self._notice_for(d, missed=True)) is not None]
        see = lambda: self.controller.open_page("tasks")  # noqa: E731
        self.notices.push_many(collapse_missed(notices, "Enquanto você estava fora", see))

    def _notice_for(self, due: Due, *, missed: bool) -> Notice | None:
        if due.item_type == task_service.ITEM_TYPE:
            task = self.tasks.get(due.item_id)
            if task is None or task.done:
                return None
            when = _hhmm(task.due_at) if task.due_at else _hhmm(due.fire_at)
            return Notice(
                title=task.title,
                subtitle=f"Era às {when}" if missed else f"Às {when}",
                icon="tasks",
                kind="task",
                actions=[
                    NoticeAction("+10 min", lambda: self.tasks.snooze(task.id)),
                    NoticeAction("Feito", lambda: self.tasks.set_done(task.id), primary=True),
                ],
            )
        if due.item_type == focus_service.ITEM_TYPE:
            ended = self.focus.settle()
            if ended is None:
                return None
            state, config = self.focus.model.state, self.focus.model.config
            if ended is Phase.FOCUS:
                minutes = int(config.duration(state.phase).total_seconds() // 60)
                subtitle = f"Hora de uma {_BREAK_NAME[state.phase]} de {minutes} min"
                title, action = "Foco concluído", "Iniciar pausa"
            else:
                subtitle = f"Pronto para o ciclo {state.cycle} de {config.long_break_every}"
                title, action = "Pausa concluída", "Iniciar foco"
            if missed:
                subtitle = f"Terminou às {_hhmm(due.fire_at)}"
            return Notice(
                title=title,
                subtitle=subtitle,
                icon="focus",
                kind="focus",
                actions=[NoticeAction(action, self.focus.start, primary=True)],
            )
        if due.item_type == event_service.ITEM_TYPE:
            event = self.calendar_events.get(due.item_id)
            if event is None:
                return None
            when = _hhmm(event.start_at)
            subtitle = f"Era às {when}" if missed else f"Às {when}"
            if event.location:
                subtitle += f" · {event.location}"
            return Notice(
                title=event.title,
                subtitle=subtitle,
                icon="calendar",
                kind="event",
                actions=[
                    NoticeAction(
                        "Ver agenda",
                        lambda: self.open_calendar_day(event.start_at),
                        primary=True,
                    )
                ],
            )
        if due.item_type == water_service.ITEM_TYPE:
            cfg = self._water_config()
            total = self.water.total_today()
            if total >= cfg.goal_ml:
                return None
            cup = cfg.cup_ml
            return Notice(
                title="Hora de beber água",
                subtitle=f"Hoje: {format_ml(total)} de {format_ml(cfg.goal_ml)} ml",
                icon="water",
                kind="water",
                stale_ok=False,
                actions=[NoticeAction(f"+{cup} ml", lambda: self.water.add(cup), primary=True)],
            )
        log.warning("aviso de tipo desconhecido: %s", due.item_type)
        return None

    def _native_notification(self, notice: Notice) -> None:
        if self.settings.native_notifications and self.tray.isVisible():
            self.tray.showMessage(
                notice.title,
                notice.subtitle,
                QSystemTrayIcon.MessageIcon.Information,
                NOTICE.duration_ms,
            )

    # --- tray ---------------------------------------------------------------

    def _build_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(icons.icon("app", self.theme.accent, _TRAY_ICON_SIZE), self)
        tray.setToolTip("Aureum Island")
        menu = QMenu()
        open_action = QAction("Abrir", menu)
        open_action.triggered.connect(self.controller.open)
        settings_action = QAction("Configurações", menu)
        settings_action.triggered.connect(lambda: self.open_settings())
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
        self.media.stop()
        self.volume.close()
        self.hotkey.unregister()
        self.fullscreen.stop()
        self.events.close()
        self.tray.hide()
        self.conn.close()
