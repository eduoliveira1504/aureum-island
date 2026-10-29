"""Máquina de estados do notch, sem UI.

Os timers de hover entram por um `Scheduler` injetado: no app é um QTimer
singleShot; nos testes, um relógio falso.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Protocol

from aureum_island.theme.tokens import MOTION


class State(Enum):
    CLOSED = "closed"
    MINIMAL = "minimal"
    OPEN = "open"
    NOTICE = "notice"


class Scheduler(Protocol):
    def start(self, name: str, delay_ms: int, callback: Callable[[], None]) -> None:
        """Agenda `callback`; reagendar o mesmo nome substitui o anterior."""

    def cancel(self, name: str) -> None: ...


# (estado anterior, estado novo, motivo). Chamado também quando o notch já aberto
# passa a ter foco (old == new == OPEN).
Listener = Callable[[State, State, str], None]

_HOVER_OPEN = "hover-open"
_HOVER_CLOSE = "hover-close"


class IslandStateMachine:
    def __init__(
        self,
        scheduler: Scheduler,
        *,
        minimal: bool = False,
        open_delay_ms: int = MOTION.hover_open_delay_ms,
        close_delay_ms: int = MOTION.hover_close_delay_ms,
    ) -> None:
        self._scheduler = scheduler
        self._minimal = minimal
        self._open_delay_ms = open_delay_ms
        self._close_delay_ms = close_delay_ms
        self._state = self.rest_state
        self._pinned = False
        self._hovering = False
        self._listeners: list[Listener] = []

    # --- leitura ------------------------------------------------------------

    @property
    def state(self) -> State:
        return self._state

    @property
    def rest_state(self) -> State:
        """Estado de repouso: linha mínima substitui o fechado."""
        return State.MINIMAL if self._minimal else State.CLOSED

    @property
    def minimal(self) -> bool:
        return self._minimal

    @property
    def pinned(self) -> bool:
        """Aberto por atalho/clique: não fecha ao tirar o mouse."""
        return self._pinned

    @property
    def at_rest(self) -> bool:
        return self._state in (State.CLOSED, State.MINIMAL)

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    # --- hover --------------------------------------------------------------

    def mouse_enter(self) -> None:
        self._hovering = True
        self._scheduler.cancel(_HOVER_CLOSE)
        if self.at_rest:
            self._scheduler.start(_HOVER_OPEN, self._open_delay_ms, self._hover_open)

    def mouse_leave(self) -> None:
        self._hovering = False
        self._scheduler.cancel(_HOVER_OPEN)
        if self._state is State.OPEN and not self._pinned:
            self._scheduler.start(_HOVER_CLOSE, self._close_delay_ms, self._hover_close)

    def _hover_open(self) -> None:
        if self.at_rest and self._hovering:
            self._set(State.OPEN, "hover")

    def _hover_close(self) -> None:
        if self._state is State.OPEN and not self._pinned and not self._hovering:
            self.close("hover")

    # --- comandos -----------------------------------------------------------

    def open(self, *, focus: bool, reason: str = "request") -> None:
        """Abre. Com `focus` (atalho, clique), o notch fica aberto até Esc/perda de foco."""
        self._cancel_timers()
        if self._state is State.OPEN:
            if focus and not self._pinned:
                self._pinned = True
                self._notify(State.OPEN, State.OPEN, reason)
            return
        self._pinned = focus
        self._set(State.OPEN, reason)

    def toggle(self, reason: str = "hotkey") -> None:
        if self._state is State.OPEN:
            self.close(reason)
        else:
            self.open(focus=True, reason=reason)

    def close(self, reason: str = "request") -> None:
        self._cancel_timers()
        self._pinned = False
        if self._state is not self.rest_state:
            self._set(self.rest_state, reason)

    def escape(self) -> None:
        if self._state is State.OPEN:
            self.close("escape")

    def focus_lost(self) -> None:
        if self._state is State.OPEN and self._pinned:
            self.close("focus_lost")

    def unpin(self) -> None:
        """Volta à regra do hover (ex.: o Windows não deixou a janela ganhar foco)."""
        if not self._pinned:
            return
        self._pinned = False
        if self._state is State.OPEN and not self._hovering:
            self._scheduler.start(_HOVER_CLOSE, self._close_delay_ms, self._hover_close)

    def set_minimal(self, minimal: bool) -> None:
        self._minimal = minimal
        if self.at_rest and self._state is not self.rest_state:
            self._set(self.rest_state, "mode")

    # --- avisos (usado no Bloco 2) ------------------------------------------

    def show_notice(self) -> bool:
        """Mostra um aviso se o notch está em repouso. Devolve False se não deu."""
        if not self.at_rest:
            return False
        self._scheduler.cancel(_HOVER_OPEN)
        self._set(State.NOTICE, "notice")
        return True

    def dismiss_notice(self) -> None:
        if self._state is State.NOTICE:
            self._set(self.rest_state, "notice_done")

    # --- interno ------------------------------------------------------------

    def _cancel_timers(self) -> None:
        self._scheduler.cancel(_HOVER_OPEN)
        self._scheduler.cancel(_HOVER_CLOSE)

    def _set(self, new: State, reason: str) -> None:
        old, self._state = self._state, new
        if old is not new:
            self._notify(old, new, reason)

    def _notify(self, old: State, new: State, reason: str) -> None:
        for listener in list(self._listeners):
            listener(old, new, reason)
