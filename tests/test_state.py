import pytest

from aureum_island.island.state import IslandStateMachine, State


class FakeScheduler:
    """Relógio falso: `advance(ms)` dispara o que venceu."""

    def __init__(self):
        self.now = 0
        self.pending: dict[str, tuple[int, object]] = {}

    def start(self, name, delay_ms, callback):
        self.pending[name] = (self.now + delay_ms, callback)

    def cancel(self, name):
        self.pending.pop(name, None)

    def advance(self, ms):
        self.now += ms
        for name, (due, callback) in sorted(self.pending.items(), key=lambda i: i[1][0]):
            if due <= self.now and self.pending.get(name, (None, None))[1] is callback:
                del self.pending[name]
                callback()


@pytest.fixture
def clock():
    return FakeScheduler()


@pytest.fixture
def machine(clock):
    m = IslandStateMachine(clock, open_delay_ms=120, close_delay_ms=300)
    m.changes = []
    m.add_listener(lambda old, new, reason: m.changes.append((old, new, reason)))
    return m


def test_starts_closed(machine):
    assert machine.state is State.CLOSED


def test_hover_opens_after_delay(machine, clock):
    machine.mouse_enter()
    clock.advance(119)
    assert machine.state is State.CLOSED
    clock.advance(1)
    assert machine.state is State.OPEN
    assert not machine.pinned
    assert machine.changes == [(State.CLOSED, State.OPEN, "hover")]


def test_short_hover_does_not_open(machine, clock):
    machine.mouse_enter()
    clock.advance(80)
    machine.mouse_leave()
    clock.advance(500)
    assert machine.state is State.CLOSED


def test_leaving_closes_after_delay(machine, clock):
    machine.mouse_enter()
    clock.advance(120)
    machine.mouse_leave()
    clock.advance(299)
    assert machine.state is State.OPEN
    clock.advance(1)
    assert machine.state is State.CLOSED


def test_coming_back_cancels_close(machine, clock):
    machine.mouse_enter()
    clock.advance(120)
    machine.mouse_leave()
    clock.advance(200)
    machine.mouse_enter()
    clock.advance(1000)
    assert machine.state is State.OPEN


def test_escape_closes(machine, clock):
    machine.open(focus=True, reason="hotkey")
    machine.escape()
    assert machine.state is State.CLOSED
    assert not machine.pinned


def test_focus_open_ignores_mouse_leave(machine, clock):
    machine.open(focus=True)
    machine.mouse_enter()
    machine.mouse_leave()
    clock.advance(5000)
    assert machine.state is State.OPEN


def test_focus_lost_closes_only_pinned(machine, clock):
    machine.mouse_enter()
    clock.advance(120)
    machine.focus_lost()
    assert machine.state is State.OPEN  # aberto por hover: a regra é a do mouse
    machine.open(focus=True)
    machine.focus_lost()
    assert machine.state is State.CLOSED


def test_hover_open_upgraded_to_focus_notifies(machine, clock):
    machine.mouse_enter()
    clock.advance(120)
    machine.open(focus=True, reason="click")
    assert machine.pinned
    assert machine.changes[-1] == (State.OPEN, State.OPEN, "click")
    machine.mouse_leave()
    clock.advance(1000)
    assert machine.state is State.OPEN


def test_unpin_falls_back_to_hover_rule(machine, clock):
    machine.open(focus=True)
    machine.unpin()
    clock.advance(300)
    assert machine.state is State.CLOSED


def test_toggle(machine):
    machine.toggle()
    assert machine.state is State.OPEN and machine.pinned
    machine.toggle()
    assert machine.state is State.CLOSED


def test_minimal_mode_replaces_closed(clock):
    m = IslandStateMachine(clock, minimal=True, open_delay_ms=120, close_delay_ms=300)
    assert m.state is State.MINIMAL
    m.mouse_enter()
    clock.advance(120)
    assert m.state is State.OPEN
    m.mouse_leave()
    clock.advance(300)
    assert m.state is State.MINIMAL
    m.open(focus=True)
    m.escape()
    assert m.state is State.MINIMAL


def test_switching_mode_at_rest(machine):
    machine.set_minimal(True)
    assert machine.state is State.MINIMAL
    assert machine.changes[-1] == (State.CLOSED, State.MINIMAL, "mode")
    machine.set_minimal(False)
    assert machine.state is State.CLOSED


def test_switching_mode_while_open_applies_on_close(machine):
    machine.open(focus=True)
    machine.set_minimal(True)
    assert machine.state is State.OPEN
    machine.close()
    assert machine.state is State.MINIMAL


def test_notice_only_from_rest(machine, clock):
    assert machine.show_notice()
    assert machine.state is State.NOTICE
    machine.dismiss_notice()
    assert machine.state is State.CLOSED
    machine.open(focus=True)
    assert not machine.show_notice()


def test_notice_cancels_pending_hover_open(machine, clock):
    machine.mouse_enter()
    machine.show_notice()
    clock.advance(500)
    assert machine.state is State.NOTICE
