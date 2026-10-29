from datetime import UTC, datetime, timedelta

from aureum_island.pages.focus import FocusPage, format_clock
from aureum_island.pages.focus_model import FocusConfig, FocusModel, FocusState, Phase, Status
from aureum_island.services.focus import FocusService
from aureum_island.theme.theme import Theme

T0 = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
CONFIG = FocusConfig(focus_min=25, short_break_min=5, long_break_min=15, long_break_every=4)


def test_start_pause_resume_uses_end_at():
    m = FocusModel(CONFIG)
    assert m.state.mode == "parado"
    m.start(T0)
    assert m.state.mode == "foco"
    assert m.state.end_at == T0 + timedelta(minutes=25)
    m.pause(T0 + timedelta(minutes=10))
    assert m.state.mode == "pausado"
    assert m.remaining(T0 + timedelta(hours=5)) == timedelta(minutes=15)
    m.resume(T0 + timedelta(hours=1))
    assert m.state.end_at == T0 + timedelta(hours=1, minutes=15)
    assert m.progress(T0 + timedelta(hours=1)) == 0.4


def test_transitions_and_long_break_every_4():
    m = FocusModel(CONFIG)
    now = T0
    seen = []
    for _ in range(8):
        m.start(now)
        now = m.state.end_at
        ended = m.settle(now)
        seen.append((ended, m.state.phase, m.state.cycle))
    assert seen == [
        (Phase.FOCUS, Phase.SHORT_BREAK, 1),
        (Phase.SHORT_BREAK, Phase.FOCUS, 2),
        (Phase.FOCUS, Phase.SHORT_BREAK, 2),
        (Phase.SHORT_BREAK, Phase.FOCUS, 3),
        (Phase.FOCUS, Phase.SHORT_BREAK, 3),
        (Phase.SHORT_BREAK, Phase.FOCUS, 4),
        (Phase.FOCUS, Phase.LONG_BREAK, 4),
        (Phase.LONG_BREAK, Phase.FOCUS, 1),
    ]


def test_settle_only_after_end():
    m = FocusModel(CONFIG)
    m.start(T0)
    assert m.settle(T0 + timedelta(minutes=24, seconds=59)) is None
    assert m.state.status is Status.RUNNING


def test_skip_and_restart():
    m = FocusModel(CONFIG)
    m.start(T0)
    m.skip()
    assert (m.state.status, m.state.phase) == (Status.STOPPED, Phase.SHORT_BREAK)
    m.restart()
    assert m.state == FocusState()


def test_state_survives_reload():
    m = FocusModel(CONFIG)
    m.start(T0)
    saved = m.state.to_dict()
    reloaded = FocusModel(CONFIG, FocusState.from_dict(saved))
    assert reloaded.state == m.state
    # PC desligado durante o foco: ao voltar, a fase conclui pelo end_at.
    assert reloaded.settle(T0 + timedelta(hours=2)) is Phase.FOCUS
    assert reloaded.state.phase is Phase.SHORT_BREAK


def test_invalid_saved_state_falls_back():
    assert FocusState.from_dict({"status": "voando"}) == FocusState()
    assert FocusState.from_dict({"status": "running", "phase": "focus", "cycle": 1}) == FocusState()
    assert FocusState.from_dict(None) == FocusState()


def test_service_saves_on_change():
    saved = []
    clock = lambda: T0  # noqa: E731
    service = FocusService(CONFIG, save=saved.append, now=clock)
    service.toggle()
    assert saved[-1]["status"] == "running"
    service.toggle()
    assert saved[-1]["status"] == "paused"
    assert len(service.upcoming(T0 - timedelta(days=1))) == 0  # pausado: sem aviso


def test_format_clock():
    assert format_clock(25 * 60) == "25:00"
    assert format_clock(59.2) == "01:00"
    assert format_clock(0) == "00:00"


def test_page_timer_only_while_visible_and_running(qtbot):
    clock = lambda: T0  # noqa: E731
    service = FocusService(CONFIG, now=clock)
    page = FocusPage(service, Theme())
    qtbot.addWidget(page)
    assert not page.timer_active
    page.show()
    assert not page.timer_active  # parado
    service.start()
    assert page.timer_active
    assert page.primary.text() == "Pausar"
    assert page.primary.accessibleName() == "Pausar"
    page.hide()
    assert not page.timer_active
    page.show()
    assert page.timer_active
    service.pause()
    assert not page.timer_active
    assert page.label.text() == "FOCO · CICLO 1 DE 4"
