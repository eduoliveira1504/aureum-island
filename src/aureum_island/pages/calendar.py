"""Página Calendário: mês (hoje em accent, pontos nos dias com compromisso) e agenda do
dia selecionado, misturando tarefas e eventos. Evento local novo inline.

Sem timers: recalcula ao aparecer e quando os dados mudam.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

from PySide6.QtCore import QEvent, QObject, QRectF, Qt, Signal
from PySide6.QtGui import QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from aureum_island.island.widgets import (
    ActionButton,
    IconButton,
    line_edit_style,
    menu_style,
)
from aureum_island.pages.calendar_model import (
    MONTHS,
    AgendaItem,
    add_months,
    agenda_for_day,
    busy_days,
    day_title,
    month_grid,
    weekday_labels,
)
from aureum_island.pages.tasks import HoverScrollArea, InlineEdit
from aureum_island.pages.tasks_model import parse_hhmm
from aureum_island.services.calendar_sync import CalendarSync
from aureum_island.services.events import EventService
from aureum_island.services.tasks import TaskService
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import NOTCH, PAGES, TYPOGRAPHY


def _local_now() -> datetime:
    return datetime.now().astimezone()


class MonthView(QWidget):
    """Grade do mês, navegável por mouse e teclado (setas, PageUp/PageDown, Home)."""

    day_selected = Signal(object)  # date

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("month")
        self._theme = theme
        self.week_start = "sunday"
        self.today = date.today()
        self.selected = self.today
        self.busy: set[date] = set()
        self._title_font = make_font(
            TYPOGRAPHY.family_title,
            TYPOGRAPHY.title_size_md,
            600,
            letter_spacing_em=TYPOGRAPHY.title_letter_spacing_em,
        )
        self._day_font = make_font(TYPOGRAPHY.family_body, PAGES.cal_day_size, tabular=True)
        self._today_font = make_font(TYPOGRAPHY.family_body, PAGES.cal_day_size, 600, tabular=True)
        self._weekday_font = make_font(TYPOGRAPHY.family_body, PAGES.cal_weekday_size, 600)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(
            7 * PAGES.cal_cell_width,
            PAGES.cal_header_height + PAGES.cal_weekday_height + 6 * PAGES.cal_cell_height,
        )
        nav, icon = PAGES.cal_nav, PAGES.cal_nav_icon
        self.prev = IconButton("previous", "Mês anterior", theme, size=nav, icon_size=icon,
                               parent=self)  # fmt: skip
        self.next = IconButton("next", "Próximo mês", theme, size=nav, icon_size=icon, parent=self)
        self.next.move(self.width() - nav, 0)
        self.prev.move(self.width() - 2 * nav, 0)
        self.prev.clicked.connect(lambda: self.select(add_months(self.selected, -1)))
        self.next.clicked.connect(lambda: self.select(add_months(self.selected, 1)))
        theme.changed.connect(self.update)

    def set_data(self, today: date, busy: set[date], week_start: str) -> None:
        self.today, self.busy, self.week_start = today, busy, week_start
        self._update_name()
        self.update()

    def select(self, day: date) -> None:
        if day != self.selected:
            self.selected = day
            self._update_name()
            self.update()
            self.day_selected.emit(day)

    def _update_name(self) -> None:
        d = self.selected
        busy = "com compromissos" if d in self.busy else "sem compromissos"
        self.setAccessibleName(f"Calendário: {d.day} de {MONTHS[d.month - 1]} de {d.year}, {busy}")

    # --- geometria ----------------------------------------------------------

    def _grid_top(self) -> int:
        return PAGES.cal_header_height + PAGES.cal_weekday_height

    def _cell(self, index: int) -> QRectF:
        row, col = divmod(index, 7)
        w, h = PAGES.cal_cell_width, PAGES.cal_cell_height
        return QRectF(col * w, self._grid_top() + row * h, w, h)

    # --- entrada ------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802
        pos = event.position()
        if pos.y() < self._grid_top():
            return super().mousePressEvent(event)
        col = int(pos.x() // PAGES.cal_cell_width)
        row = int((pos.y() - self._grid_top()) // PAGES.cal_cell_height)
        days = month_grid(self.selected.year, self.selected.month, self.week_start)
        index = row * 7 + col
        if 0 <= col < 7 and 0 <= index < len(days):
            self.select(days[index])

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        moves = {
            Qt.Key.Key_Left: -1,
            Qt.Key.Key_Right: 1,
            Qt.Key.Key_Up: -7,
            Qt.Key.Key_Down: 7,
        }
        if key in moves:
            self.select(self.selected + timedelta(days=moves[key]))
        elif key == Qt.Key.Key_PageUp:
            self.select(add_months(self.selected, -1))
        elif key == Qt.Key.Key_PageDown:
            self.select(add_months(self.selected, 1))
        elif key == Qt.Key.Key_Home:
            self.select(self.today)
        else:
            super().keyPressEvent(event)

    # --- desenho ------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        theme = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        month = self.selected
        painter.setFont(self._title_font)
        painter.setPen(qcolor(theme.accent_text))
        header = QRectF(0, 0, self.width() - 2 * PAGES.cal_nav, PAGES.cal_header_height)
        title = f"{MONTHS[month.month - 1].upper()} {month.year}"
        painter.drawText(header, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)

        painter.setFont(self._weekday_font)
        painter.setPen(qcolor(self._theme.notch.subtle_text))
        for col, label in enumerate(weekday_labels(self.week_start)):
            rect = QRectF(
                col * PAGES.cal_cell_width,
                PAGES.cal_header_height,
                PAGES.cal_cell_width,
                PAGES.cal_weekday_height,
            )
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        days = month_grid(month.year, month.month, self.week_start)
        diameter = min(PAGES.cal_cell_width, PAGES.cal_cell_height) - 2
        for index, day in enumerate(days):
            cell = self._cell(index)
            circle = QRectF(
                cell.center().x() - diameter / 2, cell.center().y() - diameter / 2,
                diameter, diameter,
            )  # fmt: skip
            in_month = day.month == month.month
            if day == self.today:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(qcolor(theme.accent))
                painter.drawEllipse(circle)
                fg, font = theme.on_accent, self._today_font
            else:
                fg = self._theme.notch.text if in_month else self._theme.notch.subtle_text
                font = self._day_font
            if day == self.selected and day != self.today:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(qcolor(theme.accent), 1.5))
                painter.drawEllipse(circle)
            painter.setFont(font)
            painter.setPen(qcolor(fg))
            painter.drawText(
                cell.adjusted(0, -2, 0, -2), Qt.AlignmentFlag.AlignCenter, str(day.day)
            )
            if day in self.busy:
                dot = PAGES.cal_dot
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(qcolor(theme.on_accent if day == self.today else theme.accent))
                painter.drawEllipse(
                    QRectF(cell.center().x() - dot / 2, circle.bottom() - dot - 1, dot, dot)
                )
        if self.hasFocus():
            index = days.index(self.selected) if self.selected in days else -1
            if index >= 0:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(qcolor(theme.accent), NOTCH.focus_ring_width))
                ring = self._cell(index).adjusted(1, 1, -1, -1)
                painter.drawRoundedRect(
                    ring, NOTCH.focus_ring_radius / 2, NOTCH.focus_ring_radius / 2
                )


class AgendaRow(QWidget):
    """Horário (ou "Dia todo"), título e marca do tipo (Tarefa, Evento ou agenda ICS)."""

    def __init__(self, page: CalendarPage, item: AgendaItem) -> None:
        super().__init__()
        self.page = page
        self.item = item
        self.setFixedHeight(PAGES.agenda_row_height)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        when = "Dia todo" if item.all_day else f"{item.start.hour:02d}:{item.start.minute:02d}"
        self.time_text = when
        self.setAccessibleName(f"{when}, {item.title}, {item.tag}")
        self._time_font = make_font(TYPOGRAPHY.family_body, PAGES.task_time_size, 600, tabular=True)
        self._title_font = make_font(TYPOGRAPHY.family_body, PAGES.agenda_title_size)
        self._title_font.setStrikeOut(item.done)
        self._tag_font = make_font(TYPOGRAPHY.family_body, PAGES.agenda_tag_size, 600)
        self._editor: InlineEdit | None = None

    def _tag_rect(self) -> QRectF:
        fm = QFontMetricsF(self._tag_font)
        dot = PAGES.cal_dot + 4 if self.item.color else 0
        w = fm.horizontalAdvance(self.item.tag) + 2 * PAGES.agenda_tag_padding_x + dot
        h = PAGES.agenda_tag_height
        return QRectF(self.width() - w, (self.height() - h) / 2, w, h)

    def paintEvent(self, event) -> None:  # noqa: N802
        theme = self.page.theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        painter.setFont(self._time_font)
        painter.setPen(qcolor(self.page.theme.notch.text_muted))
        painter.drawText(
            QRectF(0, 0, PAGES.agenda_time_width, h), Qt.AlignmentFlag.AlignVCenter, self.time_text
        )
        tag = self._tag_rect()
        x = PAGES.agenda_time_width
        width = max(0.0, tag.x() - PAGES.task_spacing - x)
        if self._editor is None:
            painter.setFont(self._title_font)
            painter.setPen(
                qcolor(
                    self.page.theme.notch.subtle_text
                    if self.item.done
                    else self.page.theme.notch.text
                )
            )
            title = QFontMetricsF(self._title_font).elidedText(
                self.item.title, Qt.TextElideMode.ElideRight, width
            )
            painter.drawText(QRectF(x, 0, width, h), Qt.AlignmentFlag.AlignVCenter, title)
        # Marca do tipo: contorno discreto; agendas ICS com o ponto da cor delas.
        painter.setPen(QPen(qcolor(theme.notch.border), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            tag.adjusted(0.5, 0.5, -0.5, -0.5), tag.height() / 2, tag.height() / 2
        )
        text_x = tag.x() + PAGES.agenda_tag_padding_x
        if self.item.color:
            dot = PAGES.cal_dot + 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(self.item.color))
            painter.drawEllipse(QRectF(text_x, tag.center().y() - dot / 2, dot, dot))
            text_x += dot + 2
        painter.setFont(self._tag_font)
        painter.setPen(qcolor(self.page.theme.notch.text_muted))
        painter.drawText(
            QRectF(text_x, tag.y(), tag.right() - text_x, tag.height()),
            Qt.AlignmentFlag.AlignVCenter,
            self.item.tag,
        )
        if self.hasFocus():
            painter.setPen(QPen(qcolor(theme.accent), NOTCH.focus_ring_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                QRectF(self.rect()).adjusted(1, 1, -1, -1),
                NOTCH.focus_ring_radius,
                NOTCH.focus_ring_radius,
            )

    # --- edição (só eventos locais) -----------------------------------------

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if self.item.editable:
            self.page.show_menu(self, event.globalPos())

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self.item.editable:
            self.edit_title()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self.item.editable and event.key() == Qt.Key.Key_Delete:
            self.page.events.delete_local(self.item.ref_id)
            return
        if self.item.editable and event.key() == Qt.Key.Key_F2:
            self.edit_title()
            return
        super().keyPressEvent(event)

    def edit_title(self) -> None:
        if self._editor is not None:
            return
        self.page.keyboard_requested.emit()
        editor = InlineEdit(self.item.title, self)
        editor.setStyleSheet(line_edit_style(self.page.theme))
        editor.setFont(self._title_font)
        x = PAGES.agenda_time_width
        editor.setGeometry(x, 0, max(60, int(self._tag_rect().x()) - x - 4), self.height())
        editor.setAccessibleName("Editar título do evento")
        editor.committed.connect(self._commit)
        editor.cancelled.connect(self._close)
        self._editor = editor
        editor.show()
        editor.setFocus()
        editor.selectAll()
        self.update()

    def _commit(self, text: str) -> None:
        if text.strip() and text.strip() != self.item.title:
            self.page.events.update_local(self.item.ref_id, title=text.strip())
        self._close()

    def _close(self) -> None:
        if self._editor is not None:
            editor, self._editor = self._editor, None
            editor.deleteLater()
            self.update()


class CalendarPage(QWidget):
    keyboard_requested = Signal()
    popup_closed = Signal()

    def __init__(
        self,
        tasks: TaskService,
        events: EventService,
        sync: CalendarSync,
        theme: Theme,
        *,
        week_start: Callable[[], str] = lambda: "sunday",
        now_local: Callable[[], datetime] = _local_now,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page-calendar")
        self.setAccessibleName("Calendário")
        self.tasks = tasks
        self.events = events
        self.sync = sync
        self.theme = theme
        self._week_start = week_start
        self.now_local = now_local
        self.rows: list[AgendaRow] = []

        self.month = MonthView(theme, self)
        self.month.day_selected.connect(lambda _day: self.refresh())

        self.day_label = _Label(theme, self)
        self._list = QWidget()
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(0, 0, PAGES.scrollbar_width + 2, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch(1)
        self.scroll = HoverScrollArea(theme, self)
        self.scroll.setWidget(self._list)

        self.title_input = QLineEdit(self)
        self.title_input.setPlaceholderText("Novo evento")
        self.title_input.setAccessibleName("Título do novo evento")
        self.start_input = QLineEdit(self)
        self.start_input.setPlaceholderText("Início")
        self.start_input.setAccessibleName("Início do novo evento (HH:MM)")
        self.end_input = QLineEdit(self)
        self.end_input.setPlaceholderText("Fim")
        self.end_input.setAccessibleName("Fim do novo evento (HH:MM, opcional)")
        for field in (self.title_input, self.start_input, self.end_input):
            field.setFixedHeight(PAGES.task_input_height)
            field.setFont(make_font(TYPOGRAPHY.family_body, PAGES.task_title_size))
            field.returnPressed.connect(self.add_from_inputs)
            field.installEventFilter(self)
        for field in (self.start_input, self.end_input):
            field.setFixedWidth(PAGES.task_time_input_width)
        self.add_button = ActionButton("Adicionar", theme, primary=True, parent=self)
        self.add_button.setAccessibleName("Adicionar evento")
        self.add_button.clicked.connect(self.add_from_inputs)

        new_row = QHBoxLayout()
        new_row.setSpacing(PAGES.button_gap)
        new_row.addWidget(self.title_input, 1)
        new_row.addWidget(self.start_input)
        new_row.addWidget(self.end_input)
        new_row.addWidget(self.add_button)

        agenda = QVBoxLayout()
        agenda.setSpacing(PAGES.button_gap)
        agenda.addWidget(self.day_label)
        agenda.addWidget(self.scroll, 1)
        agenda.addLayout(new_row)

        row = QHBoxLayout(self)
        row.setContentsMargins(
            PAGES.cal_padding_x, PAGES.cal_padding_y, PAGES.cal_padding_x, PAGES.cal_padding_y
        )
        row.setSpacing(PAGES.cal_column_gap)
        row.addWidget(self.month, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(agenda, 1)

        for signal in (tasks.changed, events.changed, sync.events_changed, sync.sources_changed):
            signal.connect(self.refresh)
        theme.changed.connect(self._apply_theme)
        self._apply_theme()
        today = self.now_local().date()
        self.month.selected = today
        self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802
        self.refresh()  # pode ter virado o dia

    # --- dados --------------------------------------------------------------

    def select_day(self, day: date) -> None:
        self.month.select(day)
        self.refresh()

    def refresh(self) -> None:
        now = self.now_local()
        tz = now.tzinfo
        selected = self.month.selected
        # Busca o mês visível com folga (a grade mostra dias dos meses vizinhos).
        first = datetime(selected.year, selected.month, 1, tzinfo=tz) - timedelta(days=14)
        last = first + timedelta(days=60)
        events = self.events.between(first.astimezone(tz) - timedelta(days=1), last)
        tasks = self.tasks.list_tasks()
        self.month.set_data(now.date(), busy_days(tasks, events, tz), self._week_start())
        sources = {s.id: (s.name, s.color) for s in self.sync.sources()}
        items = agenda_for_day(selected, tasks, events, sources, tz)
        self.day_label.set_text(day_title(selected, now.date()))
        for row in self.rows:
            self._list_layout.removeWidget(row)
            row.deleteLater()
        self.rows = [AgendaRow(self, item) for item in items]
        for i, row in enumerate(self.rows):
            self._list_layout.insertWidget(i, row)
        self.day_label.setAccessibleName(
            f"{day_title(selected, now.date())}: {len(items)} compromissos"
        )
        self.day_label.empty = not items

    def add_from_inputs(self) -> None:
        title = self.title_input.text().strip()
        if not title:
            self.title_input.setFocus()
            return
        try:
            start = parse_hhmm(self.start_input.text())
            end = parse_hhmm(self.end_input.text())
        except ValueError:
            self._mark_error()
            return
        if start is None or (end is not None and end <= start):
            self._mark_error()
            return
        tz = self.now_local().tzinfo
        day = self.month.selected
        begin = datetime.combine(day, start, tzinfo=tz)
        finish = datetime.combine(day, end, tzinfo=tz) if end else None
        self.events.add_local(title, begin, finish)
        for field in (self.title_input, self.start_input, self.end_input):
            field.clear()
        self._apply_theme()
        self.title_input.setFocus()

    def _mark_error(self) -> None:
        for field in (self.start_input, self.end_input):
            field.setStyleSheet(line_edit_style(self.theme, error=True))
        self.start_input.setFocus()

    # --- menu e teclado -----------------------------------------------------

    def show_menu(self, row: AgendaRow, pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(menu_style(self.theme))
        menu.addAction("Editar título", row.edit_title)
        menu.addSeparator()
        menu.addAction("Excluir", lambda: self.events.delete_local(row.item.ref_id))
        menu.aboutToHide.connect(self.popup_closed)
        menu.exec(pos)
        menu.deleteLater()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.FocusIn):
            self.keyboard_requested.emit()
        return False

    def _apply_theme(self) -> None:
        for field in (self.title_input, self.start_input, self.end_input):
            field.setStyleSheet(line_edit_style(self.theme))


class _Label(QWidget):
    """Título da agenda do dia ("Hoje · qui, 29 out") e "Nada marcado" quando vazio."""

    def __init__(self, theme: Theme, parent: QWidget) -> None:
        super().__init__(parent)
        self._theme = theme
        theme.changed.connect(self.update)
        self.text = ""
        self.empty = False
        self._font = make_font(
            TYPOGRAPHY.family_title,
            TYPOGRAPHY.title_size_sm,
            600,
            letter_spacing_em=TYPOGRAPHY.title_letter_spacing_em,
        )
        self._empty_font = make_font(TYPOGRAPHY.family_body, PAGES.task_time_size)
        self.setFixedHeight(round(QFontMetricsF(self._font).height()) + 2)

    def set_text(self, text: str) -> None:
        self.text = text
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setFont(self._font)
        painter.setPen(qcolor(self._theme.notch.text_muted))
        align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        painter.drawText(self.rect(), align, self.text.upper())
        if self.empty:
            painter.setFont(self._empty_font)
            painter.setPen(qcolor(self._theme.notch.subtle_text))
            right = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
            painter.drawText(self.rect(), right, "Nada marcado")
