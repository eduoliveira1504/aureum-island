"""Página Foco: anel de progresso, tempo, ciclo e controles.

Leve: o QTimer de 1 s só roda com a página visível (notch aberto nesta página) e o
foco rodando. O progresso sempre vem de `end_at`, então reaparecer já mostra certo.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPalette, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from aureum_island.island.widgets import ActionButton, Segments
from aureum_island.pages.focus_model import Phase, Status
from aureum_island.services.focus import FocusService
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import PAGES, TYPOGRAPHY

_PHASE_LABEL = {
    Phase.FOCUS: "FOCO",
    Phase.SHORT_BREAK: "PAUSA CURTA",
    Phase.LONG_BREAK: "PAUSA LONGA",
}


def format_clock(seconds: float) -> str:
    total = max(0, int(seconds + 0.999))  # arredonda para cima: 00:00 só no fim
    return f"{total // 60:02d}:{total % 60:02d}"


class FocusRing(QWidget):
    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("focus-ring")
        self._theme = theme
        self.progress = 0.0
        self.text = "25:00"
        self._font = make_font(
            TYPOGRAPHY.family_body, PAGES.focus_time_size, PAGES.focus_time_weight, tabular=True
        )
        self.setFixedSize(PAGES.focus_ring, PAGES.focus_ring)
        theme.changed.connect(self.update)

    def set_value(self, progress: float, text: str) -> None:
        if (progress, text) != (self.progress, self.text):
            self.progress, self.text = progress, text
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        stroke = PAGES.focus_ring_stroke
        rect = QRectF(self.rect()).adjusted(stroke / 2, stroke / 2, -stroke / 2, -stroke / 2)
        pen = QPen(qcolor(self._theme.notch.border), stroke)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(rect)
        if self.progress > 0:
            pen.setColor(qcolor(self._theme.accent))
            painter.setPen(pen)
            # Do topo, no sentido horário (ângulos do Qt em 1/16 de grau, anti-horário).
            painter.drawArc(rect, 90 * 16, -round(self.progress * 360 * 16))
        painter.setFont(self._font)
        painter.setPen(qcolor(self._theme.notch.text))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)


class FocusPage(QWidget):
    def __init__(self, service: FocusService, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page-focus")
        self.setAccessibleName("Foco")
        self._service = service
        self._theme = theme
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.refresh)

        self.ring = FocusRing(theme, self)
        self.label = QLabel(self)
        self.label.setFont(
            make_font(
                TYPOGRAPHY.family_title,
                TYPOGRAPHY.title_size_md,
                600,
                letter_spacing_em=TYPOGRAPHY.title_letter_spacing_em,
            )
        )
        self.status = QLabel(self)
        self.status.setFont(
            make_font(TYPOGRAPHY.family_body, TYPOGRAPHY.body_size_min, tabular=True)
        )
        self.segments = Segments(
            theme,
            PAGES.focus_segment_width,
            PAGES.focus_segment_height,
            PAGES.focus_segment_gap,
            parent=self,
        )
        self.primary = ActionButton("Iniciar", theme, primary=True, parent=self)
        self.skip = ActionButton("Pular", theme, parent=self)
        self.restart = ActionButton("Reiniciar", theme, parent=self)
        self.primary.clicked.connect(service.toggle)
        self.skip.clicked.connect(service.skip)
        self.restart.clicked.connect(service.restart)
        self.skip.setToolTip("Pular para a próxima fase")
        self.restart.setToolTip("Voltar ao primeiro ciclo")

        buttons = QHBoxLayout()
        buttons.setSpacing(PAGES.button_gap)
        for b in (self.primary, self.skip, self.restart):
            buttons.addWidget(b)
        buttons.addStretch(1)

        column = QVBoxLayout()
        column.setSpacing(PAGES.task_spacing)
        column.addStretch(1)
        column.addWidget(self.label)
        column.addWidget(self.segments)
        column.addWidget(self.status)
        column.addSpacing(PAGES.task_spacing)
        column.addLayout(buttons)
        column.addStretch(1)

        row = QHBoxLayout(self)
        row.setContentsMargins(PAGES.focus_padding_x, 0, PAGES.focus_padding_x, 0)
        row.setSpacing(PAGES.focus_column_gap)
        row.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(column, 1)

        service.changed.connect(self._on_changed)
        theme.changed.connect(self._apply_theme)
        self._apply_theme()
        self.refresh()

    # --- visibilidade: timer só com a página na tela -------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        self.refresh()
        self._sync_timer()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()

    def _on_changed(self) -> None:
        self.refresh()
        self._sync_timer()

    def _sync_timer(self) -> None:
        running = self._service.model.state.status is Status.RUNNING
        if running and self.isVisible():
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    @property
    def timer_active(self) -> bool:
        return self._timer.isActive()

    # --- conteúdo -----------------------------------------------------------

    def refresh(self) -> None:
        model = self._service.model
        state = model.state
        now = self._service.now()
        remaining = model.remaining(now).total_seconds()
        self.ring.set_value(model.progress(now), format_clock(remaining))
        every = model.config.long_break_every
        label = _PHASE_LABEL[state.phase]
        if state.phase is not Phase.LONG_BREAK:
            label += f" · CICLO {state.cycle} DE {every}"
        self.label.setText(label)
        self.segments.set_value(model.completed_cycles(), every)
        self.primary.setText(
            {Status.STOPPED: "Iniciar", Status.RUNNING: "Pausar", Status.PAUSED: "Retomar"}[
                state.status
            ]
        )
        self.status.setText(self._status_text(state.status, state.end_at))
        self.ring.setAccessibleName(f"{label.capitalize()}, faltam {format_clock(remaining)}")

    @staticmethod
    def _status_text(status: Status, end_at: datetime | None) -> str:
        if status is Status.RUNNING and end_at is not None:
            local = end_at.astimezone()
            return f"Termina às {local.hour:02d}:{local.minute:02d}"
        if status is Status.PAUSED:
            return "Pausado"
        return "Pronto para começar"

    def _apply_theme(self) -> None:
        for widget, fg in (
            (self.label, self._theme.accent_text),
            (self.status, self._theme.notch.text_muted),
        ):
            palette = widget.palette()
            palette.setColor(QPalette.ColorRole.WindowText, qcolor(fg))
            widget.setPalette(palette)
