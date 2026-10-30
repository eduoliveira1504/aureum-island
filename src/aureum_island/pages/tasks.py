"""Página Tarefas: lista do dia, nova tarefa, edição inline e desfazer exclusão."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QEvent, QObject, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from aureum_island.island import icons
from aureum_island.island.widgets import ActionButton, line_edit_style, menu_style, scrollbar_style
from aureum_island.pages.tasks_model import (
    is_overdue,
    next_pending,
    parse_hhmm,
    resolve_due,
    time_label,
    visible_tasks,
)
from aureum_island.services.storage.settings import REMINDER_OFFSETS
from aureum_island.services.storage.tasks import Task
from aureum_island.services.tasks import TaskService
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import MOTION, NOTCH, PAGES, TYPOGRAPHY


def _local_now() -> datetime:
    return datetime.now().astimezone()


class TaskCheck(QCheckBox):
    """Checkbox de 20 px desenhado pelo tema."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setFixedSize(PAGES.task_checkbox, PAGES.task_checkbox)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def hitButton(self, pos) -> bool:  # noqa: N802
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:  # noqa: N802
        theme = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        size = PAGES.task_checkbox
        rect = QRectF(1, 1, size - 2, size - 2)
        radius = size / 4
        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(theme.accent))
            painter.drawRoundedRect(rect, radius, radius)
            glyph = size - 6
            pm = icons.pixmap("check", theme.on_accent, glyph, self.devicePixelRatioF())
            painter.drawPixmap(3, 3, pm)
        else:
            border = self._theme.notch.text if self.underMouse() else self._theme.notch.text_muted
            painter.setPen(QPen(qcolor(border), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, radius, radius)
        if self.hasFocus():
            painter.setPen(QPen(qcolor(theme.accent), NOTCH.focus_ring_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, radius, radius)


class InlineEdit(QLineEdit):
    """Edição inline: Enter confirma, Esc cancela (sem fechar o notch)."""

    committed = Signal(str)
    cancelled = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.committed.emit(self.text())
            return
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self.cancelled.emit()


class TaskRow(QWidget):
    """Uma tarefa: checkbox, título e horário à direita (pill para a próxima)."""

    def __init__(self, page: TasksPage, task: Task, *, is_next: bool, now: datetime) -> None:
        super().__init__()
        self.setObjectName(f"task-{task.id}")
        self.page = page
        self.task = task
        self.is_next = is_next
        self.overdue = is_overdue(task, now)
        self.time_text = time_label(task, now)
        self._editor: InlineEdit | None = None
        self._editing = ""
        theme = page.theme
        self.setFixedHeight(PAGES.task_row_height)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        name = task.title + (f", {self.time_text}" if self.time_text else "")
        self.setAccessibleName(name + (", concluída" if task.done else ""))

        self.check = TaskCheck(theme, self)
        self.check.setChecked(task.done)
        self.check.setAccessibleName(f"Concluir {task.title}")
        self.check.setToolTip("Concluir" if not task.done else "Marcar como pendente")
        self.check.toggled.connect(lambda done: page.service.set_done(task.id, done))
        self.check.move(0, (PAGES.task_row_height - PAGES.task_checkbox) // 2)

        self._title_font = make_font(TYPOGRAPHY.family_body, PAGES.task_title_size)
        self._title_font.setStrikeOut(task.done)
        self._time_font = make_font(TYPOGRAPHY.family_body, PAGES.task_time_size, 600, tabular=True)

    # --- geometria ----------------------------------------------------------

    def _title_x(self) -> int:
        return PAGES.task_checkbox + PAGES.task_spacing

    def _pill_rect(self) -> QRectF:
        if not self.time_text:
            return QRectF(self.width(), 0, 0, 0)
        w = QFontMetricsF(self._time_font).horizontalAdvance(self.time_text)
        w += 2 * PAGES.task_pill_padding_x
        h = PAGES.task_pill_height
        return QRectF(self.width() - w, (self.height() - h) / 2, w, h)

    # --- desenho ------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        theme = self.page.theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pill = self._pill_rect()
        if self._editing != "title":
            x = self._title_x()
            width = max(0.0, pill.x() - PAGES.task_spacing - x)
            fm = QFontMetricsF(self._title_font)
            painter.setFont(self._title_font)
            painter.setPen(
                qcolor(
                    self.page.theme.notch.subtle_text
                    if self.task.done
                    else self.page.theme.notch.text
                )
            )
            text = fm.elidedText(self.task.title, Qt.TextElideMode.ElideRight, width)
            painter.drawText(
                QRectF(x, 0, width, self.height()), Qt.AlignmentFlag.AlignVCenter, text
            )
        if self.time_text and self._editing != "time":
            painter.setFont(self._time_font)
            radius = pill.height() / 2
            if self.task.done:
                fg, bg = self.page.theme.notch.subtle_text, None
            elif self.overdue:
                fg, bg = self.page.theme.notch.on_danger, self.page.theme.notch.danger
            elif self.is_next:
                fg, bg = theme.on_accent, theme.accent
            else:
                fg, bg = self.page.theme.notch.text_muted, None
            if bg is not None:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(qcolor(bg))
                painter.drawRoundedRect(pill, radius, radius)
            painter.setPen(qcolor(fg))
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, self.time_text)
        if self.hasFocus():
            painter.setPen(QPen(qcolor(theme.accent), NOTCH.focus_ring_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            ring = QRectF(self.rect()).adjusted(1, 1, -1, -1)
            painter.drawRoundedRect(ring, NOTCH.focus_ring_radius, NOTCH.focus_ring_radius)

    # --- interação ----------------------------------------------------------

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.position().x() < self._pill_rect().x():
            self.edit_title()
        else:
            self.edit_time()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Delete:
            self.page.delete(self.task)
            return
        if event.key() == Qt.Key.Key_F2:
            self.edit_title()
            return
        if event.key() == Qt.Key.Key_Space:
            self.check.toggle()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        self.page.show_menu(self, event.globalPos())

    def edit_title(self) -> None:
        self._open_editor("title", self.task.title, self._commit_title)

    def edit_time(self) -> None:
        current = ""
        if self.task.due_at is not None:
            local = self.task.due_at.astimezone()
            current = f"{local.hour:02d}:{local.minute:02d}"
        self._open_editor("time", current, self._commit_time)

    def _open_editor(self, kind: str, text: str, commit: Callable[[str], None]) -> None:
        if self._editor is not None:
            return
        self.page.request_keyboard()
        editor = InlineEdit(text, self)
        editor.setStyleSheet(line_edit_style(self.page.theme))
        editor.setFont(make_font(TYPOGRAPHY.family_body, PAGES.task_title_size))
        if kind == "title":
            x = self._title_x()
            editor.setGeometry(x, 0, max(60, int(self._pill_rect().x()) - x - 4), self.height())
            editor.setAccessibleName("Editar título")
        else:
            w = PAGES.task_time_input_width
            editor.setGeometry(self.width() - w, 0, w, self.height())
            editor.setPlaceholderText("HH:MM")
            editor.setAccessibleName("Editar horário")
        editor.committed.connect(commit)
        editor.cancelled.connect(self._close_editor)
        self._editor, self._editing = editor, kind
        editor.show()
        editor.setFocus()
        editor.selectAll()
        self.update()

    def _close_editor(self) -> None:
        if self._editor is not None:
            editor, self._editor = self._editor, None
            self._editing = ""
            editor.deleteLater()
            self.update()

    def _commit_title(self, text: str) -> None:
        if text.strip() and text.strip() != self.task.title:
            self.page.service.rename(self.task.id, text)
        self._close_editor()

    def _commit_time(self, text: str) -> None:
        try:
            at = parse_hhmm(text)
        except ValueError:
            self._editor.setStyleSheet(line_edit_style(self.page.theme, error=True))
            return
        due = resolve_due(at, self.page.now_local())[0] if at is not None else None
        self._close_editor()
        self.page.service.set_due(self.task.id, due)


class UndoRow(QWidget):
    """Linha de uma tarefa excluída: "Desfazer" por 5 s."""

    def __init__(self, page: TasksPage, task: Task) -> None:
        super().__init__()
        self.task = task
        self._theme = page.theme
        page.theme.changed.connect(self.update)
        self.setFixedHeight(PAGES.task_row_height)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(PAGES.task_checkbox + PAGES.task_spacing, 0, 0, 0)
        self.undo = ActionButton("Desfazer", page.theme, parent=self)
        self.undo.setAccessibleName(f"Desfazer exclusão de {task.title}")
        self.undo.clicked.connect(lambda: page.undo(task.id))
        layout.addStretch(1)
        layout.addWidget(self.undo)
        self._text = f"“{task.title}” excluída"
        self._font = make_font(TYPOGRAPHY.family_body, PAGES.task_title_size)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setFont(self._font)
        painter.setPen(qcolor(self._theme.notch.subtle_text))
        x = PAGES.task_checkbox + PAGES.task_spacing
        width = max(0, self.undo.x() - PAGES.task_spacing - x)
        text = QFontMetricsF(self._font).elidedText(self._text, Qt.TextElideMode.ElideRight, width)
        painter.drawText(QRectF(x, 0, width, self.height()), Qt.AlignmentFlag.AlignVCenter, text)


class HoverScrollArea(QScrollArea):
    """Rolagem sem barra visível até o mouse passar por cima."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._apply_theme()
        theme.changed.connect(self._apply_theme)
        self.viewport().setAutoFillBackground(False)

    def _apply_theme(self) -> None:
        self.setStyleSheet(scrollbar_style(self._theme))

    def enterEvent(self, event) -> None:  # noqa: N802
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


class TasksPage(QWidget):
    keyboard_requested = Signal()
    popup_closed = Signal()

    def __init__(
        self,
        service: TaskService,
        theme: Theme,
        *,
        global_offset: Callable[[], int],
        now_local: Callable[[], datetime] = _local_now,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page-tasks")
        self.setAccessibleName("Tarefas")
        self.service = service
        self.theme = theme
        self.now_local = now_local
        self._global_offset = global_offset
        self.rows: list[QWidget] = []
        self._deleted: dict[int, tuple[Task, QTimer]] = {}

        self._list = QWidget()
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(0, 0, PAGES.scrollbar_width + 2, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch(1)
        self.scroll = HoverScrollArea(theme, self)
        self.scroll.setWidget(self._list)

        self.title_input = QLineEdit(self)
        self.title_input.setPlaceholderText("Nova tarefa")
        self.title_input.setAccessibleName("Nova tarefa")
        self.time_input = QLineEdit(self)
        self.time_input.setPlaceholderText("HH:MM")
        self.time_input.setAccessibleName("Horário da nova tarefa (opcional)")
        self.time_input.setToolTip("Opcional. Se o horário já passou, vira amanhã.")
        self.time_input.setFixedWidth(PAGES.task_time_input_width + 2 * PAGES.button_padding_x)
        for field in (self.title_input, self.time_input):
            field.setFixedHeight(PAGES.task_input_height)
            field.setFont(make_font(TYPOGRAPHY.family_body, PAGES.task_title_size))
            field.returnPressed.connect(self.add_from_inputs)
            field.installEventFilter(self)
        self.add_button = ActionButton("Adicionar", theme, primary=True, parent=self)
        self.add_button.clicked.connect(self.add_from_inputs)

        new_row = QHBoxLayout()
        new_row.setSpacing(PAGES.task_spacing)
        new_row.addWidget(self.title_input, 1)
        new_row.addWidget(self.time_input)
        new_row.addWidget(self.add_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PAGES.tasks_padding_x,
            PAGES.tasks_padding_top,
            PAGES.tasks_padding_x,
            PAGES.task_spacing,
        )
        layout.setSpacing(PAGES.task_spacing)
        layout.addWidget(self.scroll, 1)
        layout.addLayout(new_row)

        service.changed.connect(self.refresh)
        theme.changed.connect(self._apply_theme)
        self._apply_theme()
        self.refresh()

    # --- dados --------------------------------------------------------------

    def refresh(self) -> None:
        now_local = now = self.now_local()
        tasks = self.service.list_tasks()
        deleted = {task_id: task for task_id, (task, _) in self._deleted.items()}
        shown = visible_tasks([*tasks, *deleted.values()], now_local)
        nxt = next_pending(tasks, now)
        for row in self.rows:
            self._list_layout.removeWidget(row)
            row.deleteLater()
        self.rows = []
        for task in shown:
            if task.id in deleted:
                row = UndoRow(self, task)
            else:
                row = TaskRow(self, task, is_next=nxt is not None and task.id == nxt.id, now=now)
            self._list_layout.insertWidget(len(self.rows), row)
            self.rows.append(row)

    def task_rows(self) -> list[TaskRow]:
        return [r for r in self.rows if isinstance(r, TaskRow)]

    def add_from_inputs(self) -> None:
        title = self.title_input.text().strip()
        if not title:
            self.title_input.setFocus()
            return
        try:
            at = parse_hhmm(self.time_input.text())
        except ValueError:
            self.time_input.setStyleSheet(line_edit_style(self.theme, error=True))
            self.time_input.setFocus()
            return
        due = resolve_due(at, self.now_local())[0] if at is not None else None
        self.service.add(title, due)
        self.title_input.clear()
        self.time_input.clear()
        self.time_input.setStyleSheet(line_edit_style(self.theme))
        self.title_input.setFocus()

    def delete(self, task: Task) -> None:
        """Exclui na hora e mostra "Desfazer" na linha por 5 s."""
        removed = self.service.delete(task.id)
        if removed is None:
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._expire(task.id))
        self._deleted[task.id] = (removed, timer)
        timer.start(MOTION.undo_ms)
        self.refresh()

    def undo(self, task_id: int) -> None:
        entry = self._deleted.pop(task_id, None)
        if entry is None:
            return
        task, timer = entry
        timer.stop()
        timer.deleteLater()
        self.service.restore(task)  # emite changed -> refresh

    def _expire(self, task_id: int) -> None:
        entry = self._deleted.pop(task_id, None)
        if entry is not None:
            entry[1].deleteLater()
            self.refresh()

    # --- menu ---------------------------------------------------------------

    def show_menu(self, row: TaskRow, pos) -> None:
        task = row.task
        menu = QMenu(self)
        menu.setStyleSheet(menu_style(self.theme))
        menu.addAction("Editar título", row.edit_title)
        menu.addAction("Editar horário", row.edit_time)
        offsets = menu.addMenu("Antecedência")
        offsets.setStyleSheet(menu_style(self.theme))
        group = QActionGroup(offsets)
        default = QAction(f"Padrão ({self._global_offset()} min)", offsets, checkable=True)
        default.setChecked(task.remind_offset_min is None)
        default.triggered.connect(lambda: self.service.set_remind_offset(task.id, None))
        group.addAction(default)
        offsets.addAction(default)
        for minutes in REMINDER_OFFSETS:
            label = "Na hora" if minutes == 0 else f"{minutes} min antes"
            action = QAction(label, offsets, checkable=True)
            action.setChecked(task.remind_offset_min == minutes)
            action.triggered.connect(
                lambda _=False, m=minutes: self.service.set_remind_offset(task.id, m)
            )
            group.addAction(action)
            offsets.addAction(action)
        offsets.setEnabled(task.due_at is not None)
        menu.addSeparator()
        menu.addAction("Excluir", lambda: self.delete(task))
        menu.aboutToHide.connect(self.popup_closed)
        menu.exec(pos)
        menu.deleteLater()

    # --- teclado ------------------------------------------------------------

    def request_keyboard(self) -> None:
        self.keyboard_requested.emit()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.FocusIn):
            self.keyboard_requested.emit()
        return False

    def _apply_theme(self) -> None:
        for field in (self.title_input, self.time_input):
            field.setStyleSheet(line_edit_style(self.theme))
