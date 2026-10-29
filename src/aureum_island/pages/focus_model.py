"""Pomodoro sem UI.

O tempo vem do horário de término (`end_at`, UTC), não de contagem: sobrevive a
reinício e suspensão. O estado é salvo em settings.json (`focus_state`).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class Phase(Enum):
    FOCUS = "focus"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


class Status(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


@dataclass(frozen=True)
class FocusConfig:
    focus_min: int = 25
    short_break_min: int = 5
    long_break_min: int = 15
    long_break_every: int = 4

    def duration(self, phase: Phase) -> timedelta:
        minutes = {
            Phase.FOCUS: self.focus_min,
            Phase.SHORT_BREAK: self.short_break_min,
            Phase.LONG_BREAK: self.long_break_min,
        }[phase]
        return timedelta(minutes=minutes)


@dataclass(frozen=True)
class FocusState:
    status: Status = Status.STOPPED
    phase: Phase = Phase.FOCUS  # fase atual (ou a próxima, se parado)
    cycle: int = 1  # ciclo de foco atual, 1..long_break_every
    end_at: datetime | None = None  # rodando
    remaining_s: float | None = None  # pausado

    @property
    def mode(self) -> str:
        """parado | foco | pausa curta | pausa longa | pausado."""
        if self.status is Status.STOPPED:
            return "parado"
        if self.status is Status.PAUSED:
            return "pausado"
        return {
            Phase.FOCUS: "foco",
            Phase.SHORT_BREAK: "pausa curta",
            Phase.LONG_BREAK: "pausa longa",
        }[self.phase]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "phase": self.phase.value,
            "cycle": self.cycle,
            "end_at": self.end_at.isoformat() if self.end_at else None,
            "remaining_s": self.remaining_s,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> FocusState:
        """Estado salvo; qualquer coisa inválida volta ao parado."""
        try:
            status = Status(raw["status"])
            phase = Phase(raw["phase"])
            cycle = int(raw["cycle"])
            end_at = datetime.fromisoformat(raw["end_at"]) if raw.get("end_at") else None
            remaining = raw.get("remaining_s")
            remaining = float(remaining) if remaining is not None else None
        except (KeyError, TypeError, ValueError):
            return cls()
        if cycle < 1 or (status is Status.RUNNING and (end_at is None or end_at.tzinfo is None)):
            return cls()
        if status is Status.PAUSED and (remaining is None or remaining < 0):
            return cls()
        return cls(status, phase, cycle, end_at, remaining)


class FocusModel:
    def __init__(self, config: FocusConfig, state: FocusState | None = None) -> None:
        self.config = config
        self.state = state or FocusState()
        if self.state.cycle > config.long_break_every:
            self.state = replace(self.state, cycle=1)

    # --- leitura ------------------------------------------------------------

    def total(self, phase: Phase | None = None) -> timedelta:
        return self.config.duration(phase or self.state.phase)

    def remaining(self, now: datetime) -> timedelta:
        s = self.state
        if s.status is Status.RUNNING:
            return max(s.end_at - now, timedelta(0))
        if s.status is Status.PAUSED:
            return timedelta(seconds=s.remaining_s)
        return self.total()

    def progress(self, now: datetime) -> float:
        """0 no começo da fase, 1 no fim."""
        total = self.total().total_seconds()
        if total <= 0:
            return 1.0
        return min(1.0, max(0.0, 1 - self.remaining(now).total_seconds() / total))

    def completed_cycles(self) -> int:
        """Segmentos preenchidos: focos concluídos na volta atual."""
        s = self.state
        return s.cycle if s.phase is not Phase.FOCUS else s.cycle - 1

    # --- ações --------------------------------------------------------------

    def start(self, now: datetime) -> None:
        if self.state.status is Status.PAUSED:
            self.resume(now)
        elif self.state.status is Status.STOPPED:
            self.state = replace(
                self.state, status=Status.RUNNING, end_at=now + self.total(), remaining_s=None
            )

    def pause(self, now: datetime) -> None:
        if self.state.status is Status.RUNNING:
            left = self.remaining(now).total_seconds()
            self.state = replace(self.state, status=Status.PAUSED, end_at=None, remaining_s=left)

    def resume(self, now: datetime) -> None:
        if self.state.status is Status.PAUSED:
            end_at = now + timedelta(seconds=self.state.remaining_s)
            self.state = replace(self.state, status=Status.RUNNING, end_at=end_at, remaining_s=None)

    def skip(self) -> None:
        """Pula para a próxima fase, parada (sem aviso)."""
        self._advance()

    def restart(self) -> None:
        self.state = FocusState()

    def settle(self, now: datetime) -> Phase | None:
        """Se a fase em andamento terminou, avança e devolve a fase que terminou."""
        s = self.state
        if s.status is Status.RUNNING and s.end_at <= now:
            ended = s.phase
            self._advance()
            return ended
        return None

    def _advance(self) -> None:
        s, every = self.state, self.config.long_break_every
        if s.phase is Phase.FOCUS:
            nxt = Phase.LONG_BREAK if s.cycle % every == 0 else Phase.SHORT_BREAK
            cycle = s.cycle
        else:
            nxt = Phase.FOCUS
            cycle = 1 if s.phase is Phase.LONG_BREAK else s.cycle + 1
        self.state = FocusState(Status.STOPPED, nxt, cycle)
