from datetime import UTC, datetime, time, timedelta, timezone

import pytest
from PySide6.QtCore import Qt

from aureum_island.pages.tasks import TaskRow, TasksPage, UndoRow
from aureum_island.pages.tasks_model import (
    next_pending,
    parse_hhmm,
    resolve_due,
    time_label,
    visible_tasks,
)
from aureum_island.services.storage import db
from aureum_island.services.storage.tasks import Task, TaskRepo
from aureum_island.services.tasks import TaskService
from aureum_island.theme.theme import Theme

BRT = timezone(timedelta(hours=-3))
NOW = datetime(2026, 10, 29, 15, 0, tzinfo=BRT)


def task(id, due=None, done=None, created=None):
    return Task(id, f"T{id}", due, None, done, created or NOW - timedelta(days=3))


def test_parse_hhmm():
    assert parse_hhmm("14:30") == time(14, 30)
    assert parse_hhmm("9:05") == time(9, 5)
    assert parse_hhmm("14h30") == time(14, 30)
    assert parse_hhmm("  ") is None
    for bad in ("25:00", "14:60", "abc", "1430"):
        with pytest.raises(ValueError):
            parse_hhmm(bad)


def test_past_time_becomes_tomorrow():
    due, tomorrow = resolve_due(time(16, 0), NOW)
    assert not tomorrow
    assert due == datetime(2026, 10, 29, 19, 0, tzinfo=UTC)
    due, tomorrow = resolve_due(time(9, 0), NOW)
    assert tomorrow
    assert due == datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
    assert resolve_due(time(15, 0), NOW)[1]  # agora mesmo também vira amanhã


def test_time_label_tomorrow():
    t = task(1, due=datetime(2026, 10, 30, 8, 0, tzinfo=BRT))
    assert time_label(t, NOW) == "amanhã 08:00"
    assert time_label(task(2, due=NOW + timedelta(hours=1)), NOW) == "16:00"


def test_list_filter():
    yesterday = NOW - timedelta(days=1)
    shown = visible_tasks(
        [
            task(1, due=NOW + timedelta(hours=1)),  # hoje
            task(2),  # sem horário
            task(3, due=yesterday),  # atrasada, pendente
            task(4, due=yesterday, done=yesterday),  # concluída ontem: some
            task(5, done=yesterday),  # sem horário concluída ontem: some
            task(6, due=NOW - timedelta(hours=1), done=NOW),  # concluída hoje: fica
            task(7, due=NOW + timedelta(days=1)),  # amanhã
            task(8, due=NOW + timedelta(days=3)),  # depois de amanhã: fora
        ],
        NOW,
    )
    assert [t.id for t in shown] == [3, 6, 1, 7, 2]


def test_next_pending():
    tasks = [
        task(1, due=NOW - timedelta(hours=1)),
        task(2, due=NOW + timedelta(hours=2)),
        task(3, due=NOW + timedelta(hours=1), done=NOW),
    ]
    assert next_pending(tasks, NOW).id == 2


@pytest.fixture
def page(qtbot, tmp_path):
    conn = db.connect(tmp_path / "data.db")
    service = TaskService(TaskRepo(conn), global_offset=lambda: 10)
    p = TasksPage(service, Theme(), global_offset=lambda: 10, now_local=lambda: NOW)
    qtbot.addWidget(p)
    p.resize(620, 178)
    p.show()
    yield p
    conn.close()


def test_add_with_enter_and_tomorrow(qtbot, page):
    page.title_input.setText("Comprar pão")
    page.time_input.setText("08:00")
    qtbot.keyClick(page.title_input, Qt.Key.Key_Return)
    rows = page.task_rows()
    assert [r.task.title for r in rows] == ["Comprar pão"]
    assert rows[0].time_text == "amanhã 08:00"
    assert rows[0].is_next
    assert page.title_input.text() == ""


def test_invalid_time_does_not_add(page):
    page.title_input.setText("X")
    page.time_input.setText("99:99")
    page.add_from_inputs()
    assert page.task_rows() == []
    assert page.title_input.text() == "X"


def test_delete_and_undo(qtbot, page):
    page.service.add("Ligar", None)
    row = page.task_rows()[0]
    row.setFocus()
    qtbot.keyClick(row, Qt.Key.Key_Delete)
    assert page.task_rows() == []
    assert isinstance(page.rows[0], UndoRow)
    assert page.service.list_tasks() == []
    page.rows[0].undo.click()
    assert [r.task.title for r in page.task_rows()] == ["Ligar"]
    assert len(page.service.list_tasks()) == 1


def test_undo_expires(qtbot, page, monkeypatch):
    page.service.add("Ligar", None)
    page.delete(page.task_rows()[0].task)
    task_id = next(iter(page._deleted))
    page._deleted[task_id][1].timeout.emit()
    assert page.rows == []


def test_check_marks_done(qtbot, page):
    page.service.add("Ler", None)
    row = page.task_rows()[0]
    qtbot.mouseClick(row.check, Qt.MouseButton.LeftButton)
    row = page.task_rows()[0]
    assert row.task.done
    assert row.check.accessibleName() == "Concluir Ler"


def test_rows_are_accessible(page):
    page.service.add("Ler", NOW.astimezone(UTC) + timedelta(hours=1))
    row = page.task_rows()[0]
    assert isinstance(row, TaskRow)
    assert row.accessibleName() == "Ler, 16:00"
    assert page.title_input.accessibleName() == "Nova tarefa"
    assert page.add_button.accessibleName() == "Adicionar"
