import json
from datetime import UTC, datetime, time, timedelta, timezone

import pytest

from aureum_island.island.notices import Notice, NoticeAction
from aureum_island.pages.water import WaterPage, format_ml
from aureum_island.pages.water_model import (
    WaterConfig,
    hourly_totals,
    reminder_slots,
    segments_filled,
)
from aureum_island.services.reminders import ReminderEngine
from aureum_island.services.storage import db, settings
from aureum_island.services.storage.settings import Settings
from aureum_island.services.water import WaterService
from aureum_island.theme.theme import Theme

BRT = timezone(timedelta(hours=-3))
CFG = WaterConfig()  # meta 2000, copo 250, a cada 60 min, 08:00-22:00


def at(hh, mm=0, day=29):
    return datetime(2026, 10, day, hh, mm, tzinfo=BRT)


# --- horários dos lembretes ----------------------------------------------------


def test_no_drink_today_starts_after_window_start():
    assert reminder_slots(CFG, at(7), None, 0) == (None, at(9))
    assert reminder_slots(CFG, at(9, 30), None, 0) == (at(9), at(10))


def test_drinking_restarts_interval():
    assert reminder_slots(CFG, at(10, 5), at(10), 250) == (None, at(11))


def test_ignored_reminder_repeats_after_interval():
    past, upcoming = reminder_slots(CFG, at(13, 10), at(10), 250)
    assert past == at(13)
    assert upcoming == at(14)


def test_after_window_moves_to_tomorrow():
    assert reminder_slots(CFG, at(21, 30), at(21, 15), 500)[1] == at(9, day=30)
    past, upcoming = reminder_slots(CFG, at(23), at(15), 500)
    assert past == at(22)
    assert upcoming == at(9, day=30)


def test_goal_reached_stops_until_tomorrow():
    assert reminder_slots(CFG, at(15), at(14), 2000) == (None, at(9, day=30))


def test_yesterday_drink_counts_from_window_start():
    assert reminder_slots(CFG, at(8, 30), at(21, day=28), 0) == (None, at(9))


def test_reminders_off():
    off = WaterConfig(reminders=False)
    assert reminder_slots(off, at(12), None, 0) == (None, None)


# --- totais --------------------------------------------------------------------


def test_hourly_totals_in_local_time():
    entries = [
        (at(8, 10).astimezone(UTC), 250),
        (at(8, 50).astimezone(UTC), 250),
        (at(14).astimezone(UTC), 500),
        (at(23, day=28).astimezone(UTC), 300),  # ontem: fora
    ]
    data = dict(hourly_totals(entries, at(15).date(), CFG, BRT))
    assert list(data) == list(range(8, 22))
    assert data[8] == 500
    assert data[14] == 500
    assert sum(data.values()) == 1000


def test_segments_are_eighths_of_goal_independent_of_cup():
    assert segments_filled(0, 2000, 8) == 0
    assert segments_filled(249, 2000, 8) == 0
    assert segments_filled(250, 2000, 8) == 1
    assert segments_filled(1000, 2000, 8) == 4
    assert segments_filled(5000, 2000, 8) == 8
    assert segments_filled(300, 2400, 8) == 1  # copo de 300, meta 2400


def test_format_ml():
    assert format_ml(2000) == "2.000"
    assert format_ml(750) == "750"


# --- serviço + motor ---------------------------------------------------------------


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def water(qapp, tmp_path):
    conn = db.connect(tmp_path / "data.db")
    clock = Clock(at(10).astimezone(UTC))
    cfg = {"value": CFG}
    service = WaterService(conn, config=lambda: cfg["value"], now=clock, tz=BRT)
    engine = ReminderEngine(conn, now=clock)
    engine.register(service)
    fired, missed = [], []
    engine.fired.connect(lambda d: fired.append(d))
    engine.missed.connect(lambda d: missed.append(d))
    yield type(
        "W",
        (),
        dict(
            conn=conn,
            clock=clock,
            service=service,
            engine=engine,
            fired=fired,
            missed=missed,
            cfg=cfg,
        ),
    )
    conn.close()


def test_add_undo_and_total(water):
    entry = water.service.add(250)
    water.service.add(500)
    assert water.service.total_today() == 750
    assert water.service.undo(entry)
    assert water.service.total_today() == 500


def test_drink_rearms_engine(water):
    water.engine.catch_up()  # início do app às 10:00: o lembrete das 10:00 é descartado
    assert water.engine.next_fire_at == at(11)
    water.clock.now = at(10, 20).astimezone(UTC)
    water.service.add(250)
    assert water.engine.next_fire_at == at(11, 20)


def test_reminder_fires_then_repeats_if_ignored(water):
    water.service.add(250)  # 10:00
    water.clock.now = at(11).astimezone(UTC)
    water.engine.check()
    assert len(water.fired) == 1
    assert water.fired[0][0].item_type == "water"
    assert water.engine.next_fire_at == at(12)


def test_stale_water_reminders_are_not_missed(water):
    water.service.add(250)  # 10:00
    water.clock.now = at(15, 30).astimezone(UTC)  # PC dormiu
    water.engine.catch_up()
    assert water.missed == []
    assert water.fired == []
    assert water.engine.next_fire_at == at(16)


# --- página --------------------------------------------------------------------


@pytest.fixture
def page(qtbot, water):
    p = WaterPage(water.service, Theme())
    qtbot.addWidget(p)
    p.show()
    return p


def test_page_buttons_follow_cup_size(page, water):
    assert page.cup.text() == "+250 ml"
    assert page.double.text() == "+500 ml"
    assert page.cup.primary and not page.double.primary
    water.cfg["value"] = WaterConfig(cup_ml=300)
    page.refresh()
    assert page.cup.text() == "+300 ml"
    assert page.double.text() == "+600 ml"
    assert page.cup.accessibleName() == "+300 ml"


def test_page_add_and_undo(page, water):
    page.double.click()
    assert water.service.total_today() == 500
    assert page.remaining.text() == "faltam 1.500 ml"
    assert page.segments.filled == 2
    assert page.undo_visible
    page.undo.click()
    assert water.service.total_today() == 0
    assert not page.undo_visible


def test_undo_disappears_after_timeout(page):
    page.cup.click()
    page._undo_timer.timeout.emit()
    assert not page.undo_visible


def test_goal_reached_text(page, water):
    water.service.add(2000)
    assert page.remaining.text() == "Meta do dia batida"
    assert page.segments.filled == 8


def test_chart_accessible_name(page, water):
    water.service.add(250)
    assert page.chart.accessibleName() == "Consumo por hora: 10h 250 ml"


# --- configurações e fila --------------------------------------------------------


def test_water_settings_defaults_and_validation(tmp_path):
    s = Settings()
    assert (s.water_goal_ml, s.water_cup_ml, s.water_interval_min) == (2000, 250, 60)
    assert (s.water_start, s.water_end) == ("08:00", "22:00")
    path = tmp_path / "settings.json"
    raw = {
        "water_cup_ml": 420,
        "water_interval_min": 50,
        "water_start": "23:00",
        "water_end": "07:00",
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    loaded = settings.load(path)
    assert loaded.water_cup_ml == 420  # valor livre entre 50 e 1000
    assert loaded.water_interval_min == 60  # fora das opções
    assert (loaded.water_start, loaded.water_end) == ("08:00", "22:00")  # início depois do fim
    path.write_text(json.dumps({"water_cup_ml": 1500}), encoding="utf-8")
    assert settings.load(path).water_cup_ml == 250


def test_fullscreen_keeps_water_out_of_missed_count(qtbot, dispose):
    from aureum_island.island.controller import IslandController
    from aureum_island.island.notices import NoticeCenter

    ctrl = IslandController(Theme())
    qtbot.addWidget(ctrl.notch)
    qtbot.addWidget(ctrl.shadow)
    ctrl.show()
    center = NoticeCenter(ctrl, play_sound=lambda: None)
    ctrl.set_suppressed(True)

    def task(title):
        return Notice(title, "Às 14:00", "tasks", [NoticeAction("Feito", lambda: None, True)])

    def drink():
        return Notice(
            "Hora de beber água",
            "Hoje: 0 de 2.000 ml",
            "water",
            [NoticeAction("+250 ml", lambda: None, True)],
            stale_ok=False,
        )

    for n in (task("A"), drink(), task("B"), drink()):
        center.push(n)
    ctrl.set_suppressed(False)
    assert center.current.title == "2 avisos perdidos"
    assert [n.title for n in center.queue] == ["Hora de beber água"]
    dispose(ctrl, center)


def test_cup_option_values():
    from aureum_island.services.storage.settings import WATER_CUP_OPTIONS, WATER_CUP_RANGE

    assert WATER_CUP_OPTIONS == (150, 200, 250, 300, 350, 500)
    assert WATER_CUP_RANGE == (50, 1000)
    assert time(8) < time(22)
