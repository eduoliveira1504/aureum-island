import logging
from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from PySide6.QtCore import Qt

from aureum_island.pages.calendar import CalendarPage
from aureum_island.pages.calendar_model import (
    add_months,
    agenda_for_day,
    busy_days,
    day_title,
    month_grid,
    weekday_labels,
)
from aureum_island.services.calendar_sync import (
    SYNC_EVERY,
    CalendarSync,
    FetchResult,
    status_text,
)
from aureum_island.services.events import EventRepo, EventService
from aureum_island.services.ics import InvalidLink, domain, normalize_url, parse_ics
from aureum_island.services.reminders import ReminderEngine
from aureum_island.services.storage import db
from aureum_island.services.storage.tasks import TaskRepo
from aureum_island.services.tasks import TaskService
from aureum_island.theme.theme import Theme

BRT = timezone(timedelta(hours=-3))
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)  # 09:00 em Brasília
SECRET = "https://calendar.google.com/calendar/ical/eu%40gmail.com/private-segredo123/basic.ics"

ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//teste//pt
BEGIN:VTIMEZONE
TZID:America/Sao_Paulo
BEGIN:STANDARD
DTSTART:19700101T000000
TZOFFSETFROM:-0300
TZOFFSETTO:-0300
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:daily
DTSTART;TZID=America/Sao_Paulo:20261026T090000
DTEND;TZID=America/Sao_Paulo:20261026T093000
RRULE:FREQ=DAILY;COUNT=6
EXDATE;TZID=America/Sao_Paulo:20261028T090000
SUMMARY:{daily}
LOCATION:Sala 2
END:VEVENT
BEGIN:VEVENT
UID:daily
RECURRENCE-ID;TZID=America/Sao_Paulo:20261030T090000
DTSTART;TZID=America/Sao_Paulo:20261030T110000
DTEND;TZID=America/Sao_Paulo:20261030T113000
SUMMARY:Daily (movida)
END:VEVENT
BEGIN:VEVENT
UID:feriado
DTSTART;VALUE=DATE:20261102
DTEND;VALUE=DATE:20261104
SUMMARY:Feriado prolongado
END:VEVENT
BEGIN:VEVENT
UID:longe
DTSTART:20270601T120000Z
SUMMARY:Fora da janela
END:VEVENT
{extra}END:VCALENDAR
"""


def ics(daily="Daily", extra=""):
    return ICS.replace("{daily}", daily).replace("{extra}", extra).encode()


# --- links -----------------------------------------------------------------------


def test_normalize_url():
    assert normalize_url("  https://a.com/x.ics ") == "https://a.com/x.ics"
    assert normalize_url("webcal://a.com/x.ics") == "https://a.com/x.ics"
    assert normalize_url("WEBCAL://a.com/x.ics") == "https://a.com/x.ics"
    for bad in ("http://a.com/x.ics", "ftp://a.com", "a.com/x.ics", "https://"):
        with pytest.raises(InvalidLink) as info:
            normalize_url(bad)
        assert "a.com" not in str(info.value)


def test_domain_only():
    assert domain(SECRET) == "calendar.google.com"


# --- leitura de ICS ----------------------------------------------------------------


def test_parse_recurrence_exdate_exception_tz_and_all_day():
    events = parse_ics(ics(), NOW)
    daily = sorted(e.start for e in events if e.uid == "daily")
    assert daily == [
        datetime(2026, 10, 26, 12, 0, tzinfo=UTC),
        datetime(2026, 10, 27, 12, 0, tzinfo=UTC),
        # 28 removido por EXDATE
        datetime(2026, 10, 29, 12, 0, tzinfo=UTC),
        datetime(2026, 10, 30, 14, 0, tzinfo=UTC),  # RECURRENCE-ID: movida para 11h
        datetime(2026, 10, 31, 12, 0, tzinfo=UTC),
    ]
    holiday = next(e for e in events if e.uid == "feriado")
    assert holiday.all_day
    assert holiday.start == datetime(2026, 11, 2, tzinfo=UTC)
    assert holiday.end == datetime(2026, 11, 4, tzinfo=UTC)
    assert not any(e.uid == "longe" for e in events)  # além de 90 dias
    assert next(e for e in events if e.uid == "daily").location == "Sala 2"


def test_invalid_ics_raises():
    with pytest.raises(ValueError):
        parse_ics(b"isto nao e ics", NOW)


# --- sincronização ---------------------------------------------------------------


class FakeFetcher:
    def __init__(self):
        self.result = FetchResult(200, ics(), etag='"v1"', last_modified="Wed, 28 Oct 2026")
        self.calls = []

    def fetch(self, url, etag, last_modified, callback):
        self.calls.append((url, etag, last_modified))
        callback(self.result)


class Vault(dict):
    def get_url(self, source_id):
        return self.get(source_id)

    def set_url(self, source_id, url):
        self[source_id] = url

    def delete_url(self, source_id):
        self.pop(source_id, None)


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


@pytest.fixture
def env(qapp, tmp_path):
    conn = db.connect(tmp_path / "data.db")
    clock = Clock()
    vault, fetcher = Vault(), FakeFetcher()
    repo = EventRepo(conn)
    events = EventService(repo, global_offset=lambda: 10, now=clock)
    sync = CalendarSync(
        conn, repo, global_offset=lambda: 10, fetcher=fetcher, now=clock,
        get_url=vault.get_url, set_url=vault.set_url, delete_url=vault.delete_url,
    )  # fmt: skip
    sync.events_changed.connect(events.changed)
    yield type("E", (), dict(conn=conn, clock=clock, vault=vault, fetcher=fetcher, repo=repo,
                             events=events, sync=sync))  # fmt: skip
    conn.close()


def all_events(env):
    return env.repo.between(NOW - timedelta(days=60), NOW + timedelta(days=120))


def test_add_source_keeps_link_only_in_vault(env, caplog):
    caplog.set_level(logging.DEBUG)
    source_id = env.sync.add_source("Trabalho", "#8B5CF6", "webcal://" + SECRET[8:])
    assert env.vault[source_id] == SECRET
    dump = "\n".join(env.conn.iterdump())
    assert "segredo123" not in dump
    assert "segredo123" not in caplog.text
    assert env.sync.domain_of(source_id) == "calendar.google.com"
    assert len(all_events(env)) == 6  # 5 da daily + feriado (o de 2027 fica fora)
    source = env.sync.sources()[0]
    assert source.last_status == "ok"
    assert status_text(source, False).startswith("Última atualização: ")


def test_http_link_is_rejected(env):
    with pytest.raises(InvalidLink):
        env.sync.add_source("X", "#8B5CF6", "http://exemplo.com/a.ics")
    assert env.sync.sources() == []
    assert env.vault == {}


def test_304_does_not_reprocess(env):
    sid = env.sync.add_source("T", "#8B5CF6", SECRET)
    before = {e.id: e.title for e in all_events(env)}
    env.fetcher.result = FetchResult(304)
    env.clock.now += timedelta(minutes=30)
    env.sync.sync(sid)
    assert env.fetcher.calls[-1][1:] == ('"v1"', "Wed, 28 Oct 2026")
    assert {e.id: e.title for e in all_events(env)} == before
    assert env.sync.sources()[0].last_status == "ok"


def test_conditional_headers_dropped_after_24h(env):
    sid = env.sync.add_source("T", "#8B5CF6", SECRET)
    env.clock.now += timedelta(hours=25)
    env.sync.sync(sid)
    assert env.fetcher.calls[-1][1:] == (None, None)


@pytest.mark.parametrize("result", [FetchResult(None), FetchResult(404), FetchResult(200, b"lixo")])
def test_errors_keep_old_events(env, result, caplog):
    caplog.set_level(logging.DEBUG)
    sid = env.sync.add_source("T", "#8B5CF6", SECRET)
    before = len(all_events(env))
    env.fetcher.result = result
    env.sync.sync(sid)
    assert len(all_events(env)) == before
    source = env.sync.sources()[0]
    assert source.last_status == "failed"
    assert status_text(source, False).endswith(" · falhou")
    assert "segredo123" not in caplog.text


def test_changed_event_keeps_id_and_removed_disappears(env):
    sid = env.sync.add_source("T", "#8B5CF6", SECRET)
    ids = {(e.uid, e.start_at): e.id for e in all_events(env)}
    env.fetcher.result = FetchResult(200, ics(daily="Daily renomeada").replace(
        b"BEGIN:VEVENT\r\nUID:feriado", b"BEGIN:VEVENT\r\nUID:feriado"))  # fmt: skip
    env.sync.sync(sid)
    after = all_events(env)
    assert {(e.uid, e.start_at): e.id for e in after} == ids
    assert {e.title for e in after if e.uid == "daily" and e.start_at.hour == 12} == {
        "Daily renomeada"
    }
    # O feriado sumiu do Google: some daqui.
    env.fetcher.result = FetchResult(200, ics().replace(b"UID:feriado", b"UID:feriado-x"))
    env.sync.sync(sid)
    assert not any(e.uid == "feriado" for e in all_events(env))


def test_sync_scheduled_every_30_min(env):
    env.sync.add_source("T", "#8B5CF6", SECRET)
    env.sync.sync_all()
    assert abs(env.sync.next_sync_ms - SYNC_EVERY.total_seconds() * 1000) < 1000


def test_remove_source_deletes_events_and_secret(env):
    sid = env.sync.add_source("T", "#8B5CF6", SECRET)
    env.sync.remove_source(sid)
    assert all_events(env) == []
    assert env.vault == {}


# --- avisos ------------------------------------------------------------------------


def test_event_reminders(env):
    engine = ReminderEngine(env.conn, now=env.clock)
    engine.register(env.events)
    fired = []
    engine.fired.connect(fired.append)
    engine.missed.connect(fired.append)
    sid = env.sync.add_source("T", "#8B5CF6", SECRET)
    # Agenda nova às 09:00 local: a daily de hoje (09:00) já passou e não vira aviso.
    engine.catch_up()
    assert fired == []
    # Próximo: daily de amanhã (30/10 movida para 11:00 local = 14:00 UTC) - 10 min.
    assert engine.next_fire_at == datetime(2026, 10, 30, 13, 50, tzinfo=UTC)
    env.clock.now = engine.next_fire_at
    engine.check()
    assert [d.payload["title"] for d in fired[0]] == ["Daily (movida)"]
    # Renomear no Google não faz disparar de novo para o mesmo horário.
    env.fetcher.result = FetchResult(200, ics(daily="Outro nome"))
    env.sync.sync(sid)
    engine.check()
    assert len(fired) == 1


def test_all_day_has_no_reminder(env):
    env.sync.add_source("T", "#8B5CF6", SECRET)
    titles = {d.payload["title"] for d in env.events.upcoming(NOW - timedelta(days=1))}
    assert "Feriado prolongado" not in titles


# --- modelo da página --------------------------------------------------------------


def test_month_grid_week_start():
    sunday = month_grid(2026, 10, "sunday")
    assert sunday[0] == date(2026, 9, 27) and sunday[0].weekday() == 6
    monday = month_grid(2026, 10, "monday")
    assert monday[0] == date(2026, 9, 28)
    assert len(sunday) == 42
    assert weekday_labels("sunday") == ["D", "S", "T", "Q", "Q", "S", "S"]
    assert weekday_labels("monday")[0] == "S"


def test_add_months_clamps_day():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)
    assert add_months(date(2026, 1, 15), -1) == date(2025, 12, 15)


def test_agenda_mixes_tasks_and_events(env, tmp_path):
    env.sync.add_source("Trabalho", "#8B5CF6", SECRET)
    tasks = TaskRepo(env.conn)
    tasks.add("Pagar conta", datetime(2026, 10, 29, 13, 30, tzinfo=UTC))
    sources = {s.id: (s.name, s.color) for s in env.sync.sources()}
    items = agenda_for_day(date(2026, 10, 29), tasks.list_tasks(), all_events(env), sources, BRT)
    assert [(i.kind, i.title, i.tag) for i in items] == [
        ("event", "Daily", "Trabalho"),
        ("task", "Pagar conta", "Tarefa"),
    ]
    holiday_days = busy_days([], all_events(env), BRT)
    assert {date(2026, 11, 2), date(2026, 11, 3)} <= holiday_days
    assert date(2026, 11, 4) not in holiday_days
    all_day = agenda_for_day(date(2026, 11, 3), [], all_events(env), sources, BRT)
    assert all_day[0].all_day


def test_day_title():
    today = date(2026, 10, 29)
    assert day_title(today, today) == "Hoje · qui, 29 out"
    assert day_title(date(2026, 10, 30), today) == "Amanhã · sex, 30 out"


# --- página ----------------------------------------------------------------------


@pytest.fixture
def page(qtbot, env):
    tasks = TaskService(TaskRepo(env.conn), global_offset=lambda: 10)
    p = CalendarPage(tasks, env.events, env.sync, Theme(),
                     now_local=lambda: env.clock.now.astimezone(BRT))  # fmt: skip
    qtbot.addWidget(p)
    p.resize(620, 178)
    p.show()
    return p


def test_month_keyboard(qtbot, page):
    page.month.setFocus()
    assert page.month.selected == date(2026, 10, 29)
    qtbot.keyClick(page.month, Qt.Key.Key_Right)
    assert page.month.selected == date(2026, 10, 30)
    qtbot.keyClick(page.month, Qt.Key.Key_PageDown)
    assert page.month.selected == date(2026, 11, 30)
    qtbot.keyClick(page.month, Qt.Key.Key_Home)
    assert page.month.selected == date(2026, 10, 29)
    assert page.month.accessibleName().startswith("Calendário: 29 de outubro de 2026")
    assert page.month.prev.accessibleName() == "Mês anterior"


def test_add_local_event(qtbot, page, env):
    page.title_input.setText("Dentista")
    page.start_input.setText("15:00")
    page.end_input.setText("16:00")
    qtbot.keyClick(page.title_input, Qt.Key.Key_Return)
    titles = [r.item.title for r in page.rows]
    assert titles == ["Dentista"]
    assert page.rows[0].accessibleName() == "15:00, Dentista, Evento"
    event = env.events.get(page.rows[0].item.ref_id)
    assert event.start_at == datetime(2026, 10, 29, 18, 0, tzinfo=UTC)


def test_invalid_event_time(page):
    page.title_input.setText("X")
    page.start_input.setText("16:00")
    page.end_input.setText("15:00")
    page.add_from_inputs()
    assert page.rows == []
    assert page.title_input.text() == "X"


def test_settings_window_calendar_section(qtbot, env, settings_deps):
    from aureum_island.settings.window import SECTIONS, SettingsWindow

    d = settings_deps
    window = SettingsWindow(
        Theme(), env.sync, store=d.store, hotkey=d.hotkey, autostart=d.autostart, sound=d.sound
    )
    qtbot.addWidget(window)
    assert window.size().toTuple() == (1000, 620)
    assert [window.nav.item(i).text() for i in range(window.nav.count())] == [
        t for _, t in SECTIONS
    ]
    section = window.sections["calendar"]
    section.name_input.setText("Pessoal")
    section.link_input.setText("http://inseguro.com/a.ics")
    section.add()
    assert "https://" in section.error.text()
    assert env.sync.sources() == []
    section.link_input.setText(SECRET)
    section.add()
    row = section.rows[0]
    assert row.info.startswith("calendar.google.com · Última atualização")
    assert "segredo123" not in row.info
    assert section.link_input.text() == ""
    row.remove_button.click()
    assert env.sync.sources()  # primeiro clique só pede confirmação
    section.rows[0].remove_button.click()
    assert env.sync.sources() == []


def test_local_event_already_started_has_no_reminder(env):
    engine = ReminderEngine(env.conn, now=env.clock)
    engine.register(env.events)
    fired = []
    engine.fired.connect(fired.append)
    env.events.add_local("Já começou", NOW - timedelta(minutes=30))
    soon = env.events.add_local("Daqui a 5 min", NOW + timedelta(minutes=5))
    engine.check()
    assert [[d.item_id for d in batch] for batch in fired] == [[soon.id]]
