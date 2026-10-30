"""Liga a máquina de estados às janelas: animação, posição na tela, foco e tela cheia."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable, Mapping

from PySide6.QtCore import QObject, QRect, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QScreen
from PySide6.QtWidgets import QApplication, QWidget

from aureum_island.island import win32
from aureum_island.island.geometry import (
    Rect,
    Shape,
    lerp_shape,
    notch_rect,
    shadow_rect,
    shape_for,
)
from aureum_island.island.motion import (
    FrameClock,
    close_curve,
    enter_curve,
    ramp,
    spring,
    spring_overshoot,
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
    hover_changed = Signal(bool)
    suppressed_changed = Signal(bool)
    notice_focus_changed = Signal(bool)  # aviso com foco de teclado (atalho/clique)

    def __init__(
        self,
        theme: Theme,
        *,
        minimal: bool = False,
        last_page: str = PAGES[0].id,
        page_widgets: Mapping[str, QWidget] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.machine = IslandStateMachine(QtScheduler(self), minimal=minimal)
        self.notch = NotchWindow(PAGES, theme, page_widgets)
        self.shadow = ShadowWindow(theme)
        self._shape = shape_for(self.machine.state)
        self._shadow_strength = 0.0
        self._anim: FrameClock | None = None
        self._screen: QScreen | None = None
        self._suppressed = False

        ids = self._page_ids = [p.id for p in PAGES]
        self.notch.open_view.set_page(ids.index(last_page) if last_page in ids else 0)
        self.notch.open_view.bar.page_changed.connect(lambda i: self.page_changed.emit(ids[i]))
        self.notch.open_view.bar.settings_requested.connect(self.settings_requested)

        self.notch.hover_changed.connect(self._on_hover)
        self.notch.pressed.connect(self._on_pressed)
        self.notch.escape_pressed.connect(self.machine.escape)
        self.notch.deactivated.connect(self._on_deactivated)
        self.machine.add_listener(self._on_state)
        self.notch.destroyed.connect(self._stop_animation)

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
        """Esconde o notch (ex.: app em tela cheia) e volta ao repouso. Ele se recolhe
        para cima com fade e, ao sair da tela cheia, desce de volta."""
        if suppressed == self._suppressed:
            return
        self._suppressed = suppressed
        log.info("notch %s (tela cheia)", "escondido" if suppressed else "visível")
        if suppressed:
            self.machine.close("fullscreen")  # a animação de recolher substitui a de fechar
            self._retract()
        else:
            self._reveal()
        self.suppressed_changed.emit(suppressed)

    def set_minimal(self, minimal: bool) -> None:
        self.machine.set_minimal(minimal)

    def toggle(self) -> None:
        """Atalho global / tray: abre com foco ou fecha. Com aviso na tela, foca o aviso."""
        if self.machine.state is State.NOTICE:
            self.focus_notice()
            return
        if self._suppressed and not self.notch.isVisible():
            self._apply(self._shape, 0.0)
            self.notch.show()
        self.machine.toggle("hotkey")

    def open(self) -> None:
        if self._suppressed and not self.notch.isVisible():
            self._apply(self._shape, 0.0)
            self.notch.show()
        self.machine.open(focus=True, reason="tray")

    def open_page(self, page_id: str) -> None:
        """Abre o notch com foco já na página pedida (ex.: "Ver" nos avisos perdidos)."""
        if page_id in self._page_ids:
            self.notch.open_view.set_page(self._page_ids.index(page_id))
            self.page_changed.emit(page_id)
        self.open()

    def request_keyboard(self) -> None:
        """Uma página precisa de teclado (campo de texto): o notch passa a ter foco."""
        if self.machine.state is State.OPEN and not self.machine.pinned:
            self.machine.open(focus=True, reason="keyboard")

    def popup_closed(self) -> None:
        """Menu de contexto fechou: se o mouse ficou fora do notch, vale como saída."""
        if not self.notch.geometry().contains(QCursor.pos()):
            self.machine.mouse_leave()

    # --- avisos -------------------------------------------------------------

    def present_notice(self, notice) -> bool:
        if self._suppressed:
            return False
        self.notch.notice_view.set_notice(notice)
        return self.machine.show_notice()

    def dismiss_notice(self) -> None:
        self.machine.dismiss_notice()

    def focus_notice(self) -> None:
        if self.machine.state is not State.NOTICE:
            return
        win32.set_no_activate(self.notch, False)
        self.notch.activateWindow()
        self.notch.notice_view.focus_primary()
        self.notice_focus_changed.emit(True)

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
        # Sempre a tela principal atual (o objeto guardado pode ter sido removido).
        # geometry(), não availableGeometry(): o notch fica por cima da barra de tarefas.
        return _to_rect(QGuiApplication.primaryScreen().geometry())

    # --- entrada ------------------------------------------------------------

    def _on_hover(self, inside: bool) -> None:
        self.hover_changed.emit(inside)
        if inside:
            self.machine.mouse_enter()
        elif QApplication.activePopupWidget() is None:
            # Com um menu aberto, a saída é decidida quando ele fechar (popup_closed).
            self.machine.mouse_leave()

    def _on_deactivated(self) -> None:
        if QApplication.activeWindow() is self.shadow:
            # A sombra não deveria receber foco; se recebeu, devolve ao notch.
            self.notch.activateWindow()
            return
        self.notice_focus_changed.emit(False)
        self.machine.focus_lost()

    def _on_pressed(self) -> None:
        # Clique no notch em repouso abre com foco. Clique no notch aberto por hover não
        # muda a regra (e, com WS_EX_NOACTIVATE, não tira o foco do app do usuário).
        if self.machine.at_rest:
            self.machine.open(focus=True, reason="click")
        elif self.machine.state is State.NOTICE:
            self.focus_notice()

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
        """Abrir e aviso entrando: mola. Fechar: suave. O conteúdo que sai some logo; o que
        entra vem junto com a forma, revelado por ela."""
        start, start_strength = self._shape, self._shadow_strength
        end = shape_for(target)
        end_strength = 1.0 if target in (State.OPEN, State.NOTICE) else 0.0
        grow = target in (State.OPEN, State.NOTICE)
        curve = spring if grow else close_curve
        fade_in = MOTION.content_in_grow if grow else MOTION.content_in_shrink
        self.notch.begin_transition(target)

        def frame(t: float) -> None:
            e = curve(t)
            strength = start_strength + (end_strength - start_strength) * min(e, 1.0)
            self._frame(lerp_shape(start, end, e), max(0.0, min(1.0, strength)))
            self.notch.set_fades(1 - ramp(t, 0.0, MOTION.content_out_end), ramp(t, *fade_in))

        def done() -> None:
            self._apply(end, end_strength)
            self.notch.end_transition()
            if end_strength == 0:
                self.shadow.hide()
            if self._suppressed and self.machine.at_rest:
                self.notch.hide()

        room = spring_overshoot() if grow else 0.0
        duration = MOTION.spring_ms if grow else MOTION.close_ms
        self._run(duration, start, end, room, max(start_strength, end_strength) > 0, frame, done)

    def _retract(self) -> None:
        """Tela cheia: recolhe para cima (altura -> 0) com fade e esconde as janelas."""
        rest = shape_for(self.machine.state)
        if not self.notch.isVisible():
            self._stop_animation()
            self._shape, self._shadow_strength = rest, 0.0
            return
        start, start_strength = self._shape, self._shadow_strength
        end = Shape(start.width, 0.0, start.radius)
        self.notch.begin_transition(None)

        def frame(t: float) -> None:
            e = close_curve(t)
            self._frame(lerp_shape(start, end, e), start_strength * (1 - e))
            self.notch.set_fades(1 - ramp(t, 0.0, MOTION.content_out_end * 2), 0.0)

        def done() -> None:
            self.shadow.hide()
            self.notch.hide()
            self.notch.hide_content()
            self._apply(rest, 0.0)  # pronto para voltar

        self._run(MOTION.fullscreen_hide_ms, start, end, 0.0, start_strength > 0, frame, done)

    def _reveal(self) -> None:
        """Saiu da tela cheia: o notch desce de volta, com o conteúdo entrando em fade."""
        if self.notch.isVisible() and self._anim is None:
            return  # já à mostra (o atalho abriu durante a tela cheia)
        rest = shape_for(self.machine.state)
        start = Shape(rest.width, 0.0, rest.radius)
        self.notch.hide_content()
        self.notch.begin_transition(self.machine.state)

        def frame(t: float) -> None:
            self._frame(lerp_shape(start, rest, enter_curve(t)), 0.0)
            self.notch.set_fades(0.0, ramp(t, *MOTION.content_in_shrink))

        def done() -> None:
            self._apply(rest, 0.0)
            self.notch.end_transition()

        self._run(MOTION.fullscreen_show_ms, start, rest, 0.0, False, frame, done)
        self.notch.show()
        win32.set_no_activate(self.notch, True)

    def _run(
        self,
        duration_ms: int,
        start: Shape,
        end: Shape,
        room: float,
        with_shadow: bool,
        on_frame: Callable[[float], None],
        on_done: Callable[[], None],
    ) -> None:
        """Uma animação de cada vez. As janelas mudam de tamanho uma vez aqui (para caber
        o maior quadro, inclusive o quique da mola) e uma no fim; a cada quadro só o
        desenho muda."""
        self._stop_animation()
        canvas = Shape(
            max(start.width, end.width) + abs(end.width - start.width) * room,
            max(start.height, end.height) + abs(end.height - start.height) * room,
            0.0,
        )
        rect = notch_rect(self._screen_rect(), canvas)
        self.notch.setGeometry(_to_qrect(rect))
        if with_shadow:
            self.shadow.setGeometry(_to_qrect(shadow_rect(rect, NOTCH.shadow_margin)))
            if not self.shadow.isVisible() and self.notch.isVisible():
                self.shadow.set_shape(start, self._shadow_strength)
                self.shadow.show()
                win32.place_below(self.shadow, self.notch)

        def finished() -> None:
            if self._anim is clock:
                self._anim = None
                clock.deleteLater()
                on_done()

        clock = FrameClock(duration_ms, on_frame, finished, self)
        self._anim = clock
        clock.start()

    def _stop_animation(self) -> None:
        if self._anim is not None:
            anim, self._anim = self._anim, None
            anim.stop()
            anim.deleteLater()

    def _frame(self, shape: Shape, shadow_strength: float) -> None:
        """Um quadro: só o desenho das duas janelas (a geometria já cabe a animação)."""
        self._shape = shape
        self._shadow_strength = shadow_strength
        self.notch.set_shape(shape)
        if shadow_strength > 0 or self.shadow.isVisible():
            self.shadow.set_shape(shape, shadow_strength)

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
