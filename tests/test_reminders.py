from datetime import UTC, datetime, timedelta

import pytest

from aureum_island.pages.focus_model import FocusConfig
from aureum_island.services.focus import FocusService
from aureum_island.services.reminders import MAX_ARM, ReminderEngine
from aureum_island.services.storage import db
from aureum_island.services.storage.tasks import TaskRepo
from aureum_island.services.tasks import TaskService, fire_at_for

T0 = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += timedelta(**kw)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def setup(qapp, tmp_path, clock):
    conn = db.connect(tmp_path / "data.db")
    offset = {"min": 10}
    tasks = TaskService(TaskRepo(conn), global_offset=lambda: offset["min"], now=clock)
    engine = ReminderEngine(conn, now=clock)
    engine.register(tasks)
    fired, missed = [], []
    engine.fired.connect(lambda dues: fired.append(list(dues)))
    engine.missed.connect(lambda dues: missed.append(list(dues)))
    yield type(
        "S",
        (),
        dict(conn=conn, tasks=tasks, engine=engine, fired=fired, missed=missed, offset=offset),
    )
    conn.close()


def fired_rows(conn):
    return conn.execute("SELECT item_id, fire_at, fired_at FROM reminders_fired").fetchall()


def test_arms_next(setup, clock):
    setup.tasks.add("Reunião", T0 + timedelta(minutes=30))
    setup.tasks.add("Depois", T0 + timedelta(hours=2))
    assert setup.engine.next_fire_at == T0 + timedelta(minutes=20)
    assert setup.engine.armed_ms == 20 * 60 * 1000


def test_fires_once_without_duplicates(setup, clock):
    task = setup.tasks.add("Reunião", T0 + timedelta(minutes=30))
    clock.advance(minutes=20)
    setup.engine.check()
    assert [[d.item_id for d in batch] for batch in setup.fired] == [[task.id]]
    setup.engine.check()
    setup.engine.catch_up()
    assert len(setup.fired) == 1
    assert setup.missed == []
    assert len(fired_rows(setup.conn)) == 1
    assert setup.engine.next_fire_at is None
    assert setup.engine.armed_ms is None


def test_rearms_on_add_edit_done(setup, clock):
    task = setup.tasks.add("A", T0 + timedelta(hours=1))
    assert setup.engine.next_fire_at == T0 + timedelta(minutes=50)
    setup.tasks.set_due(task.id, T0 + timedelta(hours=3))
    assert setup.engine.next_fire_at == T0 + timedelta(hours=2, minutes=50)
    setup.tasks.set_done(task.id)
    assert setup.engine.next_fire_at is None
    assert setup.engine.armed_ms is None


def test_arming_capped_at_6h(setup, clock):
    setup.tasks.add("Longe", T0 + timedelta(hours=10))
    assert setup.engine.next_fire_at == T0 + timedelta(hours=9, minutes=50)
    assert setup.engine.armed_ms == int(MAX_ARM.total_seconds() * 1000)
    clock.advance(hours=6)
    setup.engine.check()  # nada vence ainda: só rearma
    assert setup.fired == []
    assert setup.engine.armed_ms == int(timedelta(hours=3, minutes=50).total_seconds() * 1000)


@pytest.mark.parametrize("count", [0, 1, 3])
def test_resume_with_missed(setup, clock, count):
    for i in range(count):
        setup.tasks.add(f"T{i}", T0 + timedelta(minutes=30 + i))
    clock.advance(hours=2)  # PC dormiu
    setup.engine.catch_up()
    assert setup.fired == []
    if count == 0:
        assert setup.missed == []
    else:
        assert len(setup.missed) == 1
        assert len(setup.missed[0]) == count


def test_missed_older_than_12h_are_suppressed(setup, clock):
    setup.tasks.add("Velha", T0 + timedelta(minutes=10))
    setup.tasks.add("Recente", T0 + timedelta(hours=10))
    clock.advance(hours=13)
    setup.engine.catch_up()
    assert [d.payload["title"] for d in setup.missed[0]] == ["Recente"]
    rows = {r["fired_at"] is None for r in fired_rows(setup.conn)}
    assert rows == {True, False}  # velha gravada sem mostrar (fired_at NULL)
    setup.engine.catch_up()
    assert len(setup.missed) == 1


def test_clock_moved_forward(setup, clock):
    setup.tasks.add("A", T0 + timedelta(minutes=30))
    setup.tasks.add("B", T0 + timedelta(hours=1))
    clock.advance(hours=3)  # usuário adiantou o relógio
    setup.engine.catch_up()
    assert len(setup.missed[0]) == 2


def test_clock_moved_backward_does_not_refire(setup, clock):
    setup.tasks.add("A", T0 + timedelta(minutes=30))
    clock.advance(minutes=20)
    setup.engine.check()
    assert len(setup.fired) == 1
    clock.advance(hours=-1)  # relógio voltou
    setup.engine.catch_up()
    assert setup.engine.next_fire_at is None
    clock.advance(hours=1)
    setup.engine.check()
    assert len(setup.fired) == 1


def test_global_offset_vs_item_offset(setup, clock):
    task = setup.tasks.add("A", T0 + timedelta(hours=1))
    assert fire_at_for(setup.tasks.get(task.id), 10) == T0 + timedelta(minutes=50)
    setup.tasks.set_remind_offset(task.id, 0)
    assert setup.engine.next_fire_at == T0 + timedelta(hours=1)
    setup.offset["min"] = 30
    setup.tasks.set_remind_offset(task.id, None)
    assert setup.engine.next_fire_at == T0 + timedelta(minutes=30)


def test_snooze_creates_new_fire(setup, clock):
    task = setup.tasks.add("A", T0 + timedelta(minutes=10))
    clock.advance(minutes=0)
    setup.engine.check()  # fire_at = T0 (due - 10)
    assert len(setup.fired) == 1
    setup.tasks.snooze(task.id)
    assert setup.engine.next_fire_at == T0 + timedelta(minutes=10)
    clock.advance(minutes=10)
    setup.engine.check()
    assert len(setup.fired) == 2
    assert len(fired_rows(setup.conn)) == 2


def test_editing_time_clears_snooze(setup, clock):
    task = setup.tasks.add("A", T0 + timedelta(minutes=10))
    setup.tasks.snooze(task.id)
    setup.tasks.set_due(task.id, T0 + timedelta(hours=2))
    assert setup.tasks.get(task.id).snoozed_until is None
    assert setup.engine.next_fire_at == T0 + timedelta(hours=1, minutes=50)


def test_focus_end_is_a_provider(setup, clock):
    focus = FocusService(FocusConfig(focus_min=1), now=clock)
    setup.engine.register(focus)
    focus.start()
    assert setup.engine.next_fire_at == T0 + timedelta(minutes=1)
    clock.advance(minutes=1)
    setup.engine.check()
    assert setup.fired[0][0].item_type == "focus"
