"""Serviço do Foco: guarda o modelo, salva o estado e é provedor de avisos (fim da fase)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from PySide6.QtCore import QObject, Signal

from aureum_island.pages.focus_model import FocusConfig, FocusModel, FocusState, Phase, Status
from aureum_island.services.reminders import Due
from aureum_island.services.storage.db import utc_now

ITEM_TYPE = "focus"
ITEM_ID = 0  # um só pomodoro; o fire_at diferencia cada fase


class FocusService(QObject):
    changed = Signal()

    def __init__(
        self,
        config: FocusConfig,
        state: FocusState | None = None,
        *,
        save: Callable[[dict[str, Any]], None] = lambda _state: None,
        now: Callable[[], datetime] = utc_now,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.model = FocusModel(config, state)
        self._save = save
        self._now = now

    def now(self) -> datetime:
        return self._now()

    # --- provedor de avisos -------------------------------------------------

    def upcoming(self, after: datetime) -> list[Due]:
        s = self.model.state
        if s.status is Status.RUNNING and s.end_at > after:
            return [Due(ITEM_TYPE, ITEM_ID, s.end_at, {"phase": s.phase.value, "cycle": s.cycle})]
        return []

    # --- ações --------------------------------------------------------------

    def start(self) -> None:
        self._do(lambda: self.model.start(self._now()))

    def pause(self) -> None:
        self._do(lambda: self.model.pause(self._now()))

    def resume(self) -> None:
        self._do(lambda: self.model.resume(self._now()))

    def toggle(self) -> None:
        """Botão principal: iniciar, pausar ou retomar."""
        if self.model.state.status is Status.RUNNING:
            self.pause()
        else:
            self.start()

    def skip(self) -> None:
        self._do(self.model.skip)

    def restart(self) -> None:
        self._do(self.model.restart)

    def settle(self) -> Phase | None:
        """Conclui a fase que venceu (chamado quando o aviso dispara e no início)."""
        ended = self.model.settle(self._now())
        if ended is not None:
            self._commit()
        return ended

    def _do(self, action: Callable[[], None]) -> None:
        before = self.model.state
        action()
        if self.model.state != before:
            self._commit()

    def _commit(self) -> None:
        self._save(self.model.state.to_dict())
        self.changed.emit()
