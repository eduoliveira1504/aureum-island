import pytest
from PySide6.QtCore import Qt

from aureum_island.island.controller import IslandController
from aureum_island.island.notices import Notice, NoticeAction, NoticeCenter, collapse_missed
from aureum_island.island.state import State
from aureum_island.theme.theme import Theme


@pytest.fixture
def env(qtbot, dispose):
    ctrl = IslandController(Theme())
    qtbot.addWidget(ctrl.notch)
    qtbot.addWidget(ctrl.shadow)
    ctrl.show()
    sounds = []
    opened = []
    center = NoticeCenter(
        ctrl,
        play_sound=lambda: sounds.append(1),
        open_tasks=lambda: opened.append("tasks"),
        duration_ms=8000,
    )
    yield ctrl, center, sounds, opened
    dispose(ctrl, center)


def make(title, log=None):
    log = log if log is not None else []
    return Notice(
        title=title,
        subtitle="Às 14:30",
        icon="tasks",
        actions=[
            NoticeAction("+10 min", lambda: log.append(("snooze", title))),
            NoticeAction("Feito", lambda: log.append(("done", title)), primary=True),
        ],
    )


def wait_idle(qtbot, ctrl):
    qtbot.waitUntil(lambda: ctrl._anim is None, timeout=2000)


def test_queue_one_after_another(qtbot, env):
    ctrl, center, sounds, _ = env
    center.push(make("A"))
    center.push(make("B"))
    assert sounds == [1, 1]  # som na hora de cada aviso
    assert center.current.title == "A"
    assert ctrl.machine.state is State.NOTICE
    wait_idle(qtbot, ctrl)
    assert ctrl.notch.size().toTuple() == (360, 64)
    assert ctrl.shadow.isVisible()  # sombra também no aviso
    center.dismiss()
    qtbot.waitUntil(lambda: center.current is not None and center.current.title == "B")
    assert not center.queue


def test_hover_pauses_time(qtbot, env):
    ctrl, center, _, _ = env
    center.push(make("A"))
    ctrl.hover_changed.emit(True)
    paused = center.remaining_ms
    assert not center._timer.isActive()
    qtbot.wait(50)
    assert center.remaining_ms == paused
    ctrl.hover_changed.emit(False)
    assert center._timer.isActive()


def test_timeout_dismisses(qtbot, env):
    ctrl, center, _, _ = env
    center._duration = 50
    center.push(make("A"))
    qtbot.waitUntil(lambda: center.current is None, timeout=2000)
    assert ctrl.machine.state is State.CLOSED


def test_enter_runs_primary_and_esc_dismisses(qtbot, env):
    ctrl, center, _, _ = env
    log = []
    center.push(make("A", log))
    center.push(make("B", log))
    view = ctrl.notch.notice_view
    qtbot.keyClick(view, Qt.Key.Key_Return)
    assert log == [("done", "A")]
    qtbot.waitUntil(lambda: center.current is not None and center.current.title == "B")
    qtbot.keyClick(view, Qt.Key.Key_Escape)
    assert log == [("done", "A")]
    assert center.current is None


def test_buttons_have_accessible_names(env):
    ctrl, center, _, _ = env
    center.push(make("A"))
    view = ctrl.notch.notice_view
    assert [b.accessibleName() for b in view.buttons] == ["+10 min", "Feito"]
    assert [b.primary for b in view.buttons] == [False, True]
    assert view.accessibleName() == "A. Às 14:30"


def test_waits_while_open_but_plays_sound(qtbot, env):
    ctrl, center, sounds, _ = env
    ctrl.machine.open(focus=False)
    center.push(make("A"))
    assert sounds == [1]
    assert center.current is None
    ctrl.machine.close()
    qtbot.waitUntil(lambda: center.current is not None)
    assert sounds == [1]  # não toca de novo ao aparecer


def test_fullscreen_queues_silently_and_collapses(qtbot, env):
    ctrl, center, sounds, opened = env
    ctrl.set_suppressed(True)
    for t in "ABC":
        center.push(make(t))
    assert sounds == []
    assert center.current is None
    ctrl.set_suppressed(False)
    assert center.current.title == "3 avisos perdidos"
    assert sounds == [1]
    qtbot.keyClick(ctrl.notch.notice_view, Qt.Key.Key_Return)  # "Ver"
    assert opened == ["tasks"]


def test_fullscreen_single_notice_kept(qtbot, env):
    ctrl, center, sounds, _ = env
    ctrl.set_suppressed(True)
    center.push(make("A"))
    ctrl.set_suppressed(False)
    assert center.current.title == "A"
    assert sounds == [1]


def test_fullscreen_while_showing_requeues(qtbot, env):
    ctrl, center, _, _ = env
    center.push(make("A"))
    ctrl.set_suppressed(True)
    assert center.current is None
    assert [n.title for n in center.queue] == ["A"]


def test_hotkey_focuses_notice(qtbot, env):
    ctrl, center, _, _ = env
    focused = []
    ctrl.notice_focus_changed.connect(focused.append)
    center.push(make("A"))
    ctrl.toggle()
    assert ctrl.machine.state is State.NOTICE
    assert focused == [True]
    assert not center._timer.isActive()  # com foco, o tempo para


def test_collapse_missed():
    see = lambda: None  # noqa: E731
    assert collapse_missed([], "x", see) == []
    one = make("A")
    assert collapse_missed([one], "x", see) == [one]
    merged = collapse_missed([make("A"), make("B")], "Enquanto você estava fora", see)
    assert len(merged) == 1
    assert merged[0].title == "2 avisos perdidos"
    assert merged[0].actions[0].label == "Ver"
