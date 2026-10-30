from datetime import datetime

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QAbstractButton, QApplication

from aureum_island.island.clock import (
    ClockView,
    accessible_text,
    format_date,
    format_time,
    ms_until_next_minute,
)
from aureum_island.island.controller import IslandController
from aureum_island.island.page_bar import PageBar
from aureum_island.island.state import State
from aureum_island.pages import PAGES
from aureum_island.services.fullscreen import FullscreenWatcher, create_fullscreen_watcher
from aureum_island.services.hotkey import MOD_ALT, MOD_CONTROL, MOD_SHIFT, parse_hotkey
from aureum_island.theme.color import contrast
from aureum_island.theme.theme import Theme


@pytest.fixture
def theme(qapp):
    return Theme()


@pytest.fixture
def bar(qtbot, theme):
    widget = PageBar(PAGES, theme)
    qtbot.addWidget(widget)
    widget.show()
    return widget


# --- barra de páginas --------------------------------------------------------


def test_arrows_change_page(qtbot, bar):
    bar.focus_current()
    seen = []
    bar.page_changed.connect(seen.append)
    qtbot.keyClick(bar.buttons[0], Qt.Key.Key_Right)
    assert bar.current_index == 1
    qtbot.keyClick(bar.buttons[1], Qt.Key.Key_Right)
    qtbot.keyClick(bar.buttons[2], Qt.Key.Key_Left)
    assert bar.current_index == 1
    assert seen == [1, 2, 1]


def test_arrows_wrap_around(qtbot, bar):
    qtbot.keyClick(bar.buttons[0], Qt.Key.Key_Left)
    assert bar.current_index == len(PAGES) - 1
    qtbot.keyClick(bar.buttons[-1], Qt.Key.Key_Right)
    assert bar.current_index == 0


def test_wheel_changes_page(bar):
    def wheel(dy):
        event = QWheelEvent(
            QPointF(10, 10),
            QPointF(10, 10),
            QPoint(0, 0),
            QPoint(0, dy),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(bar, event)

    wheel(-120)
    assert bar.current_index == 1
    wheel(120)
    assert bar.current_index == 0
    for _ in range(3):  # touchpad: deltas pequenos acumulam
        wheel(-40)
    assert bar.current_index == 1


def test_click_changes_page(qtbot, bar):
    qtbot.mouseClick(bar.buttons[3], Qt.MouseButton.LeftButton)
    assert bar.current_index == 3


def test_every_button_has_accessible_name_and_tooltip(bar):
    buttons = bar.findChildren(QAbstractButton)
    assert len(buttons) == len(PAGES) + 1
    for button in buttons:
        assert button.accessibleName(), button.objectName()
        assert button.toolTip() == button.accessibleName()
    assert [b.accessibleName() for b in bar.buttons] == [p.label for p in PAGES]
    assert bar.settings_button.accessibleName() == "Configurações"


def test_tab_order(bar):
    chain = [*bar.buttons, bar.settings_button]
    for a, b in zip(chain, chain[1:], strict=False):
        assert a.nextInFocusChain() is b


def test_colors_used_in_bar_meet_contrast(theme):
    n = theme.notch
    for fg in (n.text, n.text_muted, theme.accent_text):
        assert contrast(fg, theme.notch_bg) >= 4.5


# --- relógio ----------------------------------------------------------------


def test_clock_format_pt_br():
    now = datetime(2026, 10, 29, 9, 5, 42, 250_000)
    assert format_time(now) == "09:05"
    assert format_date(now) == "qui, 29 out"
    assert accessible_text(now) == "09:05, quinta-feira, 29 de outubro"


def test_ms_until_next_minute():
    assert ms_until_next_minute(datetime(2026, 1, 1, 12, 0, 0)) == 60_030
    assert ms_until_next_minute(datetime(2026, 1, 1, 12, 0, 59, 900_000)) == 130


def test_clock_arms_single_timer(qtbot, theme):
    clock = ClockView(theme, now=lambda: datetime(2026, 10, 29, 14, 5, 30))
    qtbot.addWidget(clock)
    assert clock.text == ("14:05", "qui, 29 out")
    assert clock._timer.isSingleShot()
    assert clock._timer.isActive()
    assert 29_000 < clock._timer.remainingTime() <= 30_030
    assert clock.accessibleName() == "14:05, quinta-feira, 29 de outubro"


# --- controller (offscreen) -------------------------------------------------


@pytest.fixture
def controller(qtbot, theme, dispose):
    ctrl = IslandController(theme, last_page="water")
    qtbot.addWidget(ctrl.notch)
    qtbot.addWidget(ctrl.shadow)
    ctrl.show()
    yield ctrl
    dispose(ctrl)


def test_controller_opens_and_closes_with_animation(qtbot, controller):
    assert controller.notch.size().toTuple() == (190, 34)
    assert controller.notch.y() == controller.notch.screen().geometry().y()

    controller.machine.open(focus=True)
    qtbot.waitUntil(lambda: controller._anim is None, timeout=2000)
    assert controller.notch.size().toTuple() == (620, 224)
    assert controller.shadow.isVisible()
    assert controller.notch.open_view.isVisible()
    assert controller.notch.open_view.graphicsEffect() is None  # efeito só durante o fade

    controller.machine.escape()
    qtbot.waitUntil(lambda: controller._anim is None, timeout=2000)
    assert controller.notch.size().toTuple() == (190, 34)
    assert not controller.shadow.isVisible()
    assert controller.notch.clock.isVisible()


def test_controller_restores_last_page(controller):
    assert PAGES[controller.notch.open_view.bar.current_index].id == "water"
    assert controller.notch.open_view.stack.currentIndex() == 2


def test_controller_hides_on_fullscreen(qtbot, controller):
    controller.machine.open(focus=True)
    qtbot.waitUntil(lambda: controller._anim is None, timeout=2000)
    controller.set_suppressed(True)
    assert controller.machine.state is State.CLOSED
    assert controller.notch.isVisible()  # recolhendo, não some de uma vez
    qtbot.waitUntil(lambda: not controller.notch.isVisible(), timeout=2000)
    assert not controller.shadow.isVisible()
    controller.set_suppressed(False)
    assert controller.notch.isVisible()
    assert controller._shape.height < 34  # desce a partir de cima
    qtbot.waitUntil(lambda: controller._anim is None, timeout=2000)
    assert controller.notch.size().toTuple() == (190, 34)
    assert controller.notch.clock.isVisible()
    assert controller.notch.clock.graphicsEffect() is None


def test_animation_resizes_windows_only_at_start_and_end(qtbot, controller):
    sizes = []
    original = controller.notch.setGeometry

    def spy(*args):
        sizes.append(args)
        original(*args)

    controller.notch.setGeometry = spy
    controller.machine.open(focus=True)
    qtbot.waitUntil(lambda: controller._anim is None, timeout=2000)
    assert len(sizes) == 2  # tamanho da animação (com folga do quique) e o final
    assert controller.notch.size().toTuple() == (620, 224)


def test_hover_counts_only_inside_the_shape(qtbot, controller):
    from PySide6.QtCore import QEvent

    events = []
    controller.notch.hover_changed.connect(events.append)
    QApplication.sendEvent(controller.notch.content, QEvent(QEvent.Type.Enter))
    QApplication.sendEvent(controller.notch.content, QEvent(QEvent.Type.Leave))
    assert events == [True, False]


def test_minimal_mode_size(qtbot, theme, dispose):
    ctrl = IslandController(theme, minimal=True)
    qtbot.addWidget(ctrl.notch)
    qtbot.addWidget(ctrl.shadow)
    ctrl.show()
    assert ctrl.notch.size().toTuple() == (150, 6)
    dispose(ctrl)


# --- serviços ----------------------------------------------------------------


def test_parse_hotkey():
    hk = parse_hotkey("Ctrl+Alt+Space")  # parser aceita; só não é o padrão
    assert hk.modifiers == MOD_CONTROL | MOD_ALT
    assert hk.vk == 0x20
    assert parse_hotkey("ctrl + shift + f12").modifiers == MOD_CONTROL | MOD_SHIFT
    for bad in ("Space", "Ctrl+", "Hyper+A", "Ctrl+Alt+Banana", ""):
        with pytest.raises(ValueError):
            parse_hotkey(bad)


def test_fullscreen_watcher_is_noop_offscreen(qapp):
    watcher = create_fullscreen_watcher()
    assert type(watcher) is FullscreenWatcher
    watcher.start()
    assert not watcher.fullscreen
    watcher.stop()


def test_default_and_fallback_hotkeys_avoid_altgr_keys():
    from aureum_island.services.hotkey import (
        ALTGR_RESERVED,
        DEFAULT_HOTKEY,
        FALLBACK_HOTKEYS,
    )
    from aureum_island.services.storage.settings import Settings

    assert Settings().hotkey == DEFAULT_HOTKEY == "Ctrl+Alt+I"
    for text in (DEFAULT_HOTKEY, *FALLBACK_HOTKEYS):
        key = text.split("+")[-1].lower()
        assert key not in ALTGR_RESERVED, text
        parse_hotkey(text)


def test_hotkey_candidates_order_without_duplicates():
    from aureum_island.services.hotkey import candidates

    assert candidates("Ctrl+Alt+I") == ["Ctrl+Alt+I", "Ctrl+Alt+K", "Ctrl+Shift+Alt+I"]
    assert candidates("alt+ctrl+i") == ["alt+ctrl+i", "Ctrl+Alt+K", "Ctrl+Shift+Alt+I"]
    assert candidates("Ctrl+Alt+N")[0] == "Ctrl+Alt+N"
    assert len(candidates("Ctrl+Alt+N")) == 4


def test_bar_shows_official_logo(bar, theme):
    from PySide6.QtWidgets import QLabel

    from aureum_island.island.widgets import Logo

    logo = bar.findChild(Logo)
    assert logo is not None and logo.accessibleName() == "Aureum Island"
    assert not any("AUREUM" in label.text() for label in bar.findChildren(QLabel))


def test_page_change_slides_in_briefly(qtbot, controller):
    controller.machine.open(focus=True)
    qtbot.waitUntil(lambda: controller._anim is None, timeout=2000)
    view = controller.notch.open_view
    view.bar.set_current(view.bar.current_index + 1)
    page = view.stack.currentWidget()
    assert view.page_animating and page.graphicsEffect() is not None
    qtbot.waitUntil(lambda: not view.page_animating, timeout=1000)
    assert page.graphicsEffect() is None and page.pos().x() == 0
