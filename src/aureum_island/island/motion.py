"""Curvas de movimento e o relógio de quadros das animações do notch.

As curvas são funções puras de `t` (fração do tempo, 0..1) para progresso (0..1, a mola
passa um pouco de 1 e volta). O relógio roda na taxa do monitor (240 Hz -> 4 ms) e só
existe enquanto uma animação está em andamento: parado, nenhum timer.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer
from PySide6.QtGui import QGuiApplication

from aureum_island.theme.tokens import MOTION

Curve = Callable[[float], float]

_FALLBACK_HZ = 60.0


def spring(
    t: float,
    damping: float = MOTION.spring_damping,
    residual: float = MOTION.spring_residual,
) -> float:
    """Mola subamortecida normalizada: em t=1 falta só `residual` (o fim crava 1)."""
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    omega = math.log(1 / residual) / damping  # envelope e^(-ζωt) = residual em t=1
    omega_d = omega * math.sqrt(1 - damping**2)
    envelope = math.exp(-damping * omega * t)
    return 1 - envelope * (
        math.cos(omega_d * t) + damping * omega / omega_d * math.sin(omega_d * t)
    )


def spring_overshoot(damping: float = MOTION.spring_damping) -> float:
    """Quanto a mola passa de 1 no pico (fração do caminho)."""
    return math.exp(-damping * math.pi / math.sqrt(1 - damping**2))


def cubic_bezier(x1: float, y1: float, x2: float, y2: float) -> Curve:
    """Como o cubic-bezier() do CSS: resolve x(s) = t por Newton e devolve y(s)."""

    def coord(s: float, p1: float, p2: float) -> float:
        return 3 * (1 - s) ** 2 * s * p1 + 3 * (1 - s) * s**2 * p2 + s**3

    def slope(s: float, p1: float, p2: float) -> float:
        return 3 * (1 - s) ** 2 * p1 + 6 * (1 - s) * s * (p2 - p1) + 3 * s**2 * (1 - p2)

    def curve(t: float) -> float:
        if t <= 0:
            return 0.0
        if t >= 1:
            return 1.0
        s = t
        for _ in range(8):
            d = slope(s, x1, x2)
            if abs(d) < 1e-6:
                break
            s = min(1.0, max(0.0, s - (coord(s, x1, x2) - t) / d))
        lo, hi = 0.0, 1.0  # bisseção, caso Newton não convirja nas pontas
        for _ in range(30):
            if abs(coord(s, x1, x2) - t) < 1e-5:
                break
            if coord(s, x1, x2) < t:
                lo = s
            else:
                hi = s
            s = (lo + hi) / 2
        return coord(s, y1, y2)

    return curve


close_curve = cubic_bezier(*MOTION.close_curve)
enter_curve = cubic_bezier(*MOTION.enter_curve)


def ramp(t: float, start: float, end: float) -> float:
    """0 antes de `start`, 1 depois de `end`, linear no meio (para os fades)."""
    if t <= start:
        return 0.0
    if t >= end:
        return 1.0
    return (t - start) / (end - start)


def frame_interval_ms() -> int:
    """Intervalo de um quadro na tela principal (240 Hz -> 4 ms, 60 Hz -> 16 ms)."""
    screen = QGuiApplication.primaryScreen()
    hz = screen.refreshRate() if screen is not None else 0.0
    return max(1, int(1000 / (hz if hz > 1 else _FALLBACK_HZ)))


class FrameClock(QObject):
    """Chama `on_frame(t)` a cada quadro do monitor até t=1, por tempo decorrido (um quadro
    atrasado não atrasa a animação), e depois `on_done()`. O timer só existe durante a
    animação."""

    def __init__(
        self,
        duration_ms: int,
        on_frame: Callable[[float], None],
        on_done: Callable[[], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._duration = max(1, duration_ms)
        self._on_frame = on_frame
        self._on_done = on_done
        self._elapsed = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)

    @property
    def running(self) -> bool:
        return self._timer.isActive()

    def start(self) -> None:
        self._elapsed.start()
        self._timer.start(frame_interval_ms())
        self._on_frame(0.0)

    def stop(self) -> None:
        """Para onde está, sem chamar on_done."""
        self._timer.stop()

    def _tick(self) -> None:
        t = min(1.0, self._elapsed.elapsed() / self._duration)
        self._on_frame(t)
        if t >= 1.0:
            self._timer.stop()
            if self._on_done is not None:
                self._on_done()
