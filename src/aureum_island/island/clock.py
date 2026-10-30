"""Relógio do notch fechado: hora + data curta em pt-BR.

Atualiza com um único singleShot armado para a virada do próximo minuto.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QFontMetricsF, QPainter
from PySide6.QtWidgets import QWidget

from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import NOTCH, TYPOGRAPHY

WEEKDAYS_SHORT = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
WEEKDAYS_LONG = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)
MONTHS_SHORT = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
MONTHS_LONG = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)

# Folga para o timer não disparar um pouco antes da virada.
_SLACK_MS = 30


def format_time(now: datetime) -> str:
    return f"{now.hour:02d}:{now.minute:02d}"


def format_date(now: datetime) -> str:
    """'qui, 29 out'."""
    return f"{WEEKDAYS_SHORT[now.weekday()]}, {now.day} {MONTHS_SHORT[now.month - 1]}"


def accessible_text(now: datetime) -> str:
    """'14:05, quinta-feira, 29 de outubro'."""
    weekday = WEEKDAYS_LONG[now.weekday()]
    return f"{format_time(now)}, {weekday}, {now.day} de {MONTHS_LONG[now.month - 1]}"


def ms_until_next_minute(now: datetime) -> int:
    return (60 - now.second) * 1000 - now.microsecond // 1000 + _SLACK_MS


class ClockView(QWidget):
    def __init__(
        self,
        theme: Theme,
        parent: QWidget | None = None,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("clock")
        self._theme = theme
        self._now = now
        self._time = self._date = ""
        self._time_font = make_font(
            TYPOGRAPHY.family_body, TYPOGRAPHY.clock_size, TYPOGRAPHY.clock_weight, tabular=True
        )
        self._date_font = make_font(TYPOGRAPHY.family_body, TYPOGRAPHY.date_size, tabular=True)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.refresh)
        self.setFixedSize(NOTCH.closed_width, NOTCH.closed_height)
        theme.changed.connect(self.update)
        self.refresh()

    @property
    def text(self) -> tuple[str, str]:
        return self._time, self._date

    def refresh(self) -> None:
        """Atualiza o texto e rearma o timer (chamado também na troca de horário do
        sistema e ao voltar da suspensão)."""
        now = self._now()
        time, date = format_time(now), format_date(now)
        if (time, date) != (self._time, self._date):
            self._time, self._date = time, date
            self.setAccessibleName(accessible_text(now))
            self.update()
        self._timer.start(ms_until_next_minute(now))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        time_fm = QFontMetricsF(self._time_font)
        date_fm = QFontMetricsF(self._date_font)
        time_w = time_fm.horizontalAdvance(self._time)
        date_w = date_fm.horizontalAdvance(self._date)
        x = (self.width() - (time_w + NOTCH.closed_gap + date_w)) / 2
        h = self.height()

        painter.setFont(self._time_font)
        painter.setPen(qcolor(self._theme.notch.text))
        painter.drawText(QRectF(x, 0, time_w, h), Qt.AlignmentFlag.AlignVCenter, self._time)

        painter.setFont(self._date_font)
        painter.setPen(qcolor(self._theme.notch.text_muted))
        date_rect = QRectF(x + time_w + NOTCH.closed_gap, 0, date_w, h)
        painter.drawText(date_rect, Qt.AlignmentFlag.AlignVCenter, self._date)
