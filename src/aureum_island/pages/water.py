"""Página Água: total do dia / meta, 8 segmentos, copo e 2 copos, mini gráfico por hora.

Sem timers: o conteúdo é recalculado ao aparecer e quando os dados mudam. O "Desfazer"
do último registro usa um singleShot de 5 s que só existe logo depois de registrar.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QFontMetricsF, QPainter, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from aureum_island.island.widgets import ActionButton, Segments
from aureum_island.pages.water_model import hourly_totals, segments_filled
from aureum_island.services.water import WaterService
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import COLORS, MOTION, PAGES, TYPOGRAPHY


def format_ml(ml: int) -> str:
    """2000 -> '2.000' (milhar com ponto, pt-BR)."""
    return f"{ml:,}".replace(",", ".")


class WaterValue(QWidget):
    """'750' grande + ' / 2.000 ml' na mesma linha de base."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.total, self.goal = 0, 2000
        self._big = make_font(
            TYPOGRAPHY.family_body, PAGES.water_value_size, PAGES.water_value_weight, tabular=True
        )
        self._small = make_font(TYPOGRAPHY.family_body, PAGES.water_unit_size, tabular=True)
        self.setFixedHeight(round(QFontMetricsF(self._big).height()))

    def set_value(self, total: int, goal: int) -> None:
        if (total, goal) != (self.total, self.goal):
            self.total, self.goal = total, goal
            self.updateGeometry()
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        big_fm = QFontMetricsF(self._big)
        baseline = big_fm.ascent()
        big = format_ml(self.total)
        painter.setFont(self._big)
        painter.setPen(qcolor(COLORS.text))
        painter.drawText(0, round(baseline), big)
        painter.setFont(self._small)
        painter.setPen(qcolor(COLORS.text_muted))
        x = big_fm.horizontalAdvance(big) + PAGES.button_gap
        painter.drawText(round(x), round(baseline), f"/ {format_ml(self.goal)} ml")


class HourlyChart(QWidget):
    """Barras por hora da janela ativa. Hora atual em accent."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("water-chart")
        self._theme = theme
        self.data: list[tuple[int, int]] = []
        self.current_hour = -1
        self.scale_ml = 500
        self._axis = make_font(TYPOGRAPHY.family_body, PAGES.water_axis_size, tabular=True)
        self.setFixedSize(PAGES.water_chart_width, PAGES.water_chart_height)
        theme.changed.connect(self.update)

    def set_data(self, data: list[tuple[int, int]], current_hour: int, scale_ml: int) -> None:
        self.data, self.current_hour = data, current_hour
        self.scale_ml = max([scale_ml, *(ml for _, ml in data)])
        parts = [f"{h}h {ml} ml" for h, ml in data if ml]
        self.setAccessibleName(
            "Consumo por hora: " + (", ".join(parts) if parts else "nenhum registro hoje")
        )
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self.data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        axis_fm = QFontMetricsF(self._axis)
        axis_h = axis_fm.height()
        chart_h = self.height() - axis_h - PAGES.water_bar_gap
        n = len(self.data)
        gap = PAGES.water_bar_gap
        bar_w = (self.width() - gap * (n - 1)) / n
        painter.setPen(Qt.PenStyle.NoPen)
        for i, (hour, ml) in enumerate(self.data):
            x = i * (bar_w + gap)
            h = (
                max(PAGES.water_bar_min, chart_h * ml / self.scale_ml)
                if ml
                else PAGES.water_bar_min
            )
            if hour == self.current_hour:
                fill = self._theme.accent
            elif ml:
                fill = COLORS.text_muted
            else:
                fill = COLORS.track
            painter.setBrush(qcolor(fill))
            radius = min(bar_w / 2, PAGES.water_bar_min)
            painter.drawRoundedRect(QRectF(x, chart_h - h, bar_w, h), radius, radius)
        # Rótulos: primeira, do meio e última hora.
        painter.setFont(self._axis)
        painter.setPen(qcolor(COLORS.text_dim))
        for i in sorted({0, n // 2, n - 1}):
            label = f"{self.data[i][0]}h"
            center = i * (bar_w + gap) + bar_w / 2
            half = axis_fm.horizontalAdvance(label) / 2
            # Mantém o rótulo dentro do widget (o último não pode cortar na borda).
            left = min(max(0.0, center - half), self.width() - 2 * half)
            painter.drawText(QRectF(left, chart_h + gap, 2 * half + 1, axis_h), 0, label)


class WaterPage(QWidget):
    def __init__(self, service: WaterService, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page-water")
        self.setAccessibleName("Água")
        self._service = service
        self._theme = theme
        self._last_entry: int | None = None
        self._undo_timer = QTimer(self)
        self._undo_timer.setSingleShot(True)
        self._undo_timer.timeout.connect(self._hide_undo)

        self.value = WaterValue(self)
        self.remaining = QLabel(self)
        self.remaining.setFont(make_font(TYPOGRAPHY.family_body, TYPOGRAPHY.body_size_min))
        self.segments = Segments(
            theme,
            PAGES.water_segment_width,
            PAGES.focus_segment_height,
            PAGES.water_segment_gap,
            total=PAGES.water_segments,
            parent=self,
        )
        self.cup = ActionButton("", theme, primary=True, parent=self)
        self.double = ActionButton("", theme, parent=self)
        self.undo = ActionButton("Desfazer", theme, parent=self)
        self.undo.setAccessibleName("Desfazer último registro")
        self.undo.hide()
        self.cup.clicked.connect(lambda: self.add(1))
        self.double.clicked.connect(lambda: self.add(2))
        self.undo.clicked.connect(self.undo_last)
        self.chart = HourlyChart(theme, self)

        buttons = QHBoxLayout()
        buttons.setSpacing(PAGES.button_gap)
        for b in (self.cup, self.double, self.undo):
            buttons.addWidget(b)
        buttons.addStretch(1)

        column = QVBoxLayout()
        column.setSpacing(PAGES.task_spacing)
        column.addStretch(1)
        column.addWidget(self.value)
        column.addWidget(self.remaining)
        column.addWidget(self.segments)
        column.addSpacing(PAGES.task_spacing)
        column.addLayout(buttons)
        column.addStretch(1)

        row = QHBoxLayout(self)
        row.setContentsMargins(PAGES.focus_padding_x, 0, PAGES.focus_padding_x, 0)
        row.setSpacing(PAGES.focus_column_gap)
        row.addLayout(column, 1)
        row.addWidget(self.chart, 0, Qt.AlignmentFlag.AlignVCenter)

        service.changed.connect(self.refresh)
        theme.changed.connect(self._apply_theme)
        self._apply_theme()
        self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802
        self.refresh()  # pode ter virado o dia com a página escondida

    # --- ações --------------------------------------------------------------

    def add(self, cups: int) -> None:
        self._last_entry = self._service.add(self._service.config().cup_ml * cups)
        self.undo.show()
        self._undo_timer.start(MOTION.undo_ms)

    def undo_last(self) -> None:
        if self._last_entry is not None:
            self._service.undo(self._last_entry)
        self._hide_undo()

    def _hide_undo(self) -> None:
        self._undo_timer.stop()
        self._last_entry = None
        self.undo.hide()

    @property
    def undo_visible(self) -> bool:
        return not self.undo.isHidden()

    # --- conteúdo -----------------------------------------------------------

    def refresh(self) -> None:
        cfg = self._service.config()
        now = self._service.now_local()
        total = self._service.total_today()
        self.value.set_value(total, cfg.goal_ml)
        self.value.setAccessibleName(f"{total} de {cfg.goal_ml} ml hoje")
        left = cfg.goal_ml - total
        self.remaining.setText(f"faltam {format_ml(left)} ml" if left > 0 else "Meta do dia batida")
        filled = segments_filled(total, cfg.goal_ml, PAGES.water_segments)
        self.segments.set_value(filled, PAGES.water_segments)
        self.cup.setText(f"+{cfg.cup_ml} ml")
        self.double.setText(f"+{2 * cfg.cup_ml} ml")
        entries = self._service.entries_today()
        data = hourly_totals(entries, now.date(), cfg, now.tzinfo)
        self.chart.set_data(data, now.hour, 2 * cfg.cup_ml)

    def _apply_theme(self) -> None:
        palette = self.remaining.palette()
        palette.setColor(QPalette.ColorRole.WindowText, qcolor(COLORS.text_muted))
        self.remaining.setPalette(palette)
