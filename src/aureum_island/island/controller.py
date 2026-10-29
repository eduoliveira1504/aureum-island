"""Liga a máquina de estados às janelas: animação, posição na tela, foco e tela cheia."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QObject, QRect, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QGuiApplication, QScreen
from PySide6.QtWidgets import QApplication

from aureum_island.island import win32
from aureum_island.island.geometry import (
    Rect,
    Shape,
    lerp_shape,
    notch_rect,
    shadow_rect,
    shape_for,
)
from aureum_island.island.state import IslandStateMachine, State
from aureum_island.island.window import NotchWindow, ShadowWindow
from aureum_island.pages import PAGES
from aureum_island.theme.theme import Theme
from aureum_island.theme.tokens import MOTION, NOTCH

log = logging.getLogger(__name__)

# Se o Windows não deixar a janela ganhar foco nesse prazo, o notch volta à regra do hover.
_ACTIVATION_GRACE_MS = 200


class QtScheduler:
    """Scheduler da máquina de estados com QTimer singleShot (só existe enquanto agendado)."""

    def __init__(self, parent: QObject) -> None:
        self._parent = parent
        self._timers: dict[str, QTimer] = {}

    def start(self, name: str, delay_ms: int, callback: Callable[[], None]) -> None:
        self.cancel(name)
        timer = QTimer(self._parent)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._fire(name, timer, callback))
        self._timers[name] = timer
        timer.start(delay_ms)

    def cancel(self, name: str) -> None:
        timer = self._timers.pop(name, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()

    def _fire(self, name: str, timer: QTimer, callback: Callable[[], None]) -> None:
        if self._timers.get(name) is timer:
            del self._timers[name]
            timer.deleteLater()
            callback()


def _to_rect(rect: QRect) -> Rect:
    return Rect(rect.x(), rect.y(), rect.width(), rect.height())


def _to_qrect(rect: Rect) -> QRect:
    return QRect(rect.x, rect.y, rect.width, rect.height)


class IslandController(QObject):
    page_changed = Signal(str)  # id da página
    settings_requested = Signal()

    def __init__(
        self,
        theme: Theme,
        *,
        minimal: bool = False,
        last_page: str = PAGES[0].id,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.machine = IslandStateMachine(QtScheduler(self), minimal=minimal)
        self.notch = NotchWindow(PAGES, theme)
        self.shadow = ShadowWindow(theme)
        self._shape = shape_for(self.machine.state)
        self._shadow_strength = 0.0
        self._anim: QVariantAnimation | None = None
        self._easing = QEasingCurve(QEasingCurve.Type.OutCubic)
        self._screen: QScreen | None = None
        self._suppressed = False

        ids = [p.id for p in PAGES]
        self.notch.open_view.set_page(ids.index(last_page) if last_page in ids else 0)
        self.notch.open_view.bar.page_changed.connect(lambda i: self.page_changed.emit(ids[i]))
        self.notch.open_view.bar.settings_requested.connect(self.settings_requested)

        self.notch.hover_changed.connect(self._on_hover)
        self.notch.pressed.connect(self._on_pressed)
        self.notch.escape_pressed.connect(self.machine.escape)
        self.notch.deactivated.connect(self._on_deactivated)
        self.machine.add_listener(self._on_state)

        app = QGuiApplication.instance()
        app.primaryScreenChanged.connect(self._bind_screen)
        app.screenRemoved.connect(lambda _screen: self._bind_screen(app.primaryScreen()))
        self._bind_screen(app.primaryScreen())

    # --- ciclo de vida ------------------------------------------------------

    def show(self) -> None:
        self.notch.begin_transition(self.machine.state)
        self.notch.end_transition()
        self._apply(self._shape, 0.0)
        self.notch.show()
        win32.set_no_activate(self.notch, True)

    @property
    def suppressed(self) -> bool:
        return self._suppressed

    def set_suppressed(self, suppressed: bool) -> None:
        """Esconde o notch (ex.: app em tela cheia) e volta ao repouso."""
        if suppressed == self._suppressed:
            return
        self._suppressed = suppressed
        log.info("notch %s (tela cheia)", "escondido" if suppressed else "visível")
        if suppressed:
            self.machine.close("fullscreen")
            self._stop_animation()
            self._shape = shape_for(self.machine.state)
            self.notch.begin_transition(self.machine.state)
            self.notch.end_transition()
            self.shadow.hide()
            self.notch.hide()
        else:
            self._apply(self._shape, 0.0)
            self.notch.show()

    def set_minimal(self, minimal: bool) -> None:
        self.machine.set_minimal(minimal)

    def toggle(self) -> None:
        """Atalho global / tray: abre com foco ou fecha."""
        if self._suppressed and not self.notch.isVisible():
            self._apply(self._shape, 0.0)
            self.notch.show()
        self.machine.toggle("hotkey")

    def open(self) -> None:
        if self._suppressed and not self.notch.isVisible():
            self._apply(self._shape, 0.0)
            self.notch.show()
        self.machine.open(focus=True, reason="tray")

    # --- tela ---------------------------------------------------------------

    def _bind_screen(self, screen: QScreen | None) -> None:
        if self._screen is not None:
            with contextlib.suppress(RuntimeError, TypeError):  # tela já removida
                self._screen.geometryChanged.disconnect(self._relayout)
        self._screen = screen
        if screen is None:
            return
        screen.geometryChanged.connect(self._relayout)
        for window in (self.notch, self.shadow):
            handle = window.windowHandle()
            if handle is not None:
                handle.setScreen(screen)
        self._relayout()

    def _relayout(self, *_args) -> None:
        self._apply(self._shape, self._shadow_strength)

    def _screen_rect(self) -> Rect:
        screen = self._screen or QGuiApplication.primaryScreen()
        # geometry(), não availableGeometry(): o notch fica por cima da barra de tarefas.
        return _to_rect(screen.geometry())

    # --- entrada ------------------------------------------------------------

    def _on_hover(self, inside: bool) -> None:
        if inside:
            self.machine.mouse_enter()
        else:
            self.machine.mouse_leave()

    def _on_deactivated(self) -> None:
        if QApplication.activeWindow() is self.shadow:
            # A sombra não deveria receber foco; se recebeu, devolve ao notch.
            self.notch.activateWindow()
            return
        self.machine.focus_lost()

    def _on_pressed(self) -> None:
        # Clique no notch em repouso abre com foco. Clique no notch aberto por hover não
        # muda a regra (e, com WS_EX_NOACTIVATE, não tira o foco do app do usuário).
        if self.machine.at_rest:
            self.machine.open(focus=True, reason="click")

    # --- transições ---------------------------------------------------------

    def _on_state(self, old: State, new: State, reason: str) -> None:
        log.debug("estado %s -> %s (%s)", old.value, new.value, reason)
        if old is not new:
            self._animate(new)
        if new is State.OPEN and self.machine.pinned:
            self._take_focus()
        elif new is not State.OPEN:
            win32.set_no_activate(self.notch, True)

    def _take_focus(self) -> None:
        win32.set_no_activate(self.notch, False)
        self.notch.activateWindow()
        self.notch.open_view.bar.focus_current()
        QTimer.singleShot(_ACTIVATION_GRACE_MS, self._check_activation)

    def _check_activation(self) -> None:
        if (
            self.machine.state is State.OPEN
            and self.machine.pinned
            and not self.notch.isActiveWindow()
        ):
            log.info("o Windows não deu foco ao notch; ele fecha ao tirar o mouse")
            self.machine.unpin()

    def _animate(self, target: State) -> None:
        self._stop_animation()
        start_shape, start_strength = self._shape, self._shadow_strength
        end_shape = shape_for(target)
        end_strength = 1.0 if target is State.OPEN else 0.0
        self.notch.begin_transition(target)
        if end_strength > 0 and not self.shadow.isVisible() and self.notch.isVisible():
            self._apply(start_shape, start_strength)
            self.shadow.show()
            win32.place_below(self.shadow, self.notch)

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(MOTION.transition_ms)

        def tick(progress: float) -> None:
            eased = self._easing.valueForProgress(progress)
            strength = start_strength + (end_strength - start_strength) * eased
            self._apply(lerp_shape(start_shape, end_shape, eased), strength)
            fade_start = MOTION.content_fade_start
            if progress >= fade_start:
                self.notch.set_content_opacity((progress - fade_start) / (1 - fade_start))

        def finished() -> None:
            self._anim = None
            self._apply(end_shape, end_strength)
            self.notch.end_transition()
            if end_strength == 0:
                self.shadow.hide()
            if self._suppressed and self.machine.at_rest:
                self.notch.hide()

        anim.valueChanged.connect(tick)
        anim.finished.connect(finished)
        self._anim = anim
        anim.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)

    def _stop_animation(self) -> None:
        if self._anim is not None:
            anim, self._anim = self._anim, None
            anim.stop()  # DeleteWhenStopped apaga

    def _apply(self, shape: Shape, shadow_strength: float) -> None:
        """Um único passo atualiza as duas janelas (sem descompasso entre notch e sombra)."""
        self._shape = shape
        self._shadow_strength = shadow_strength
        rect = notch_rect(self._screen_rect(), shape)
        self.notch.setGeometry(_to_qrect(rect))
        self.notch.set_shape(shape)
        if shadow_strength > 0 or self.shadow.isVisible():
            self.shadow.setGeometry(_to_qrect(shadow_rect(rect, NOTCH.shadow_margin)))
            self.shadow.set_shape(shape, shadow_strength)
