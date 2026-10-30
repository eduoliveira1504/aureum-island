"""Bloco 6: janela de Configurações, tema da janela, atalho, início automático e instância
única."""

import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLabel

from aureum_island.pages.focus_model import FocusConfig, FocusModel, Phase, Status
from aureum_island.services import hotkey as hk
from aureum_island.services.autostart import VALUE_NAME, Autostart, command
from aureum_island.services.calendar_sync import CalendarSync
from aureum_island.services.events import EventRepo
from aureum_island.services.hotkey import HotkeyStatus, parse_hotkey
from aureum_island.services.single_instance import SingleInstance
from aureum_island.services.storage import db, settings
from aureum_island.settings.store import SettingsStore
from aureum_island.theme.theme import Theme

# --- store --------------------------------------------------------------------


def test_store_emits_changed_keys_and_saves(qtbot, tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    with qtbot.waitSignal(store.changed) as blocker:
        store.update(mode="minimal", hide_on_fullscreen=True)  # o segundo já era True
    assert blocker.args == [frozenset({"mode"})]
    assert settings.load(path).mode == "minimal"
    with qtbot.assertNotEmitted(store.changed):
        store.update(mode="minimal")
    with pytest.raises(ValueError):
        store.update(window_theme="roxo")
    assert store.value.window_theme == "system"


# --- atalho -------------------------------------------------------------------


def test_custom_hotkey_taken_keeps_previous(settings_deps):
    d = settings_deps
    assert d.hotkey.status is HotkeyStatus.REGISTERED
    d.backend.taken.add(parse_hotkey("Ctrl+Alt+N"))
    reason = d.hotkey.change("Ctrl+Alt+N")
    assert reason == "Ctrl+Alt+N está em uso por outro app."
    assert d.hotkey.active == "Ctrl+Alt+I"
    assert d.backend.active == parse_hotkey("Ctrl+Alt+I")


def test_altgr_rule_blocks_choice(settings_deps):
    d = settings_deps
    reason = d.hotkey.change("Ctrl+Alt+E")
    assert reason.startswith("Bloqueado pela regra do AltGr")
    assert "AltGr+E" in reason
    assert d.hotkey.active == "Ctrl+Alt+I"
    assert hk.validate("Shift+A") == "Use Ctrl, Alt ou Win na combinação."
    assert hk.validate("Ctrl+Shift+N") is None


def test_no_hotkey_option(settings_deps):
    d = settings_deps
    assert d.hotkey.change("") is None
    assert d.hotkey.status is HotkeyStatus.INACTIVE
    assert d.hotkey.active is None and d.backend.active is None


def test_fallbacks_only_for_default(settings_deps):
    d = settings_deps
    d.backend.taken.add(parse_hotkey("Ctrl+Alt+I"))
    d.hotkey.register("Ctrl+Alt+I")
    assert d.hotkey.status is HotkeyStatus.FALLBACK
    assert d.hotkey.active == "Ctrl+Alt+K"
    d.backend.taken.add(parse_hotkey("Ctrl+Alt+N"))
    d.hotkey.register("Ctrl+Alt+N")  # escolhido pelo usuário: sem fallback
    assert d.hotkey.status is HotkeyStatus.FAILED
    assert d.hotkey.active is None


def test_format_hotkey_from_capture():
    mods = hk.MOD_CONTROL | hk.MOD_ALT
    assert hk.format_hotkey(mods, 0x49) == "Ctrl+Alt+I"
    assert hk.format_hotkey(hk.MOD_CONTROL | hk.MOD_SHIFT, 0x20) == "Ctrl+Shift+Space"
    assert hk.format_hotkey(mods, 0x75) == "Ctrl+Alt+F6"
    assert hk.format_hotkey(mods, 0xFF) is None
    assert hk.display("Ctrl+Alt+Space") == "Ctrl+Alt+Espaço"


# --- início automático --------------------------------------------------------


def test_autostart_command_uses_pythonw(tmp_path):
    exe = tmp_path / "python.exe"
    exe.touch()
    (tmp_path / "pythonw.exe").touch()
    assert command(str(exe)) == f'"{tmp_path / "pythonw.exe"}" -m aureum_island'


def test_autostart_enable_disable_and_repair(settings_deps):
    reg, auto = settings_deps.registry, settings_deps.autostart
    assert auto.set_enabled(True)
    assert reg.values[VALUE_NAME] == '"C:\\app\\pythonw.exe" -m aureum_island'
    assert auto.repair() is False  # já certo
    reg.values[VALUE_NAME] = '"D:\\pasta-antiga\\pythonw.exe" -m aureum_island'
    assert auto.repair() is True
    assert reg.values[VALUE_NAME] == '"C:\\app\\pythonw.exe" -m aureum_island'
    assert auto.set_enabled(False)
    assert VALUE_NAME not in reg.values
    reg.fail = True
    assert Autostart(reg, cmd="x").set_enabled(True) is False


# --- instância única ----------------------------------------------------------


_CLIENT = """
import sys, pathlib
from PySide6.QtCore import QCoreApplication
app = QCoreApplication([])
from aureum_island.services.single_instance import SingleInstance
second = SingleInstance(pathlib.Path(sys.argv[1]), sys.argv[2])
sys.exit(0 if not second.acquire() and second.notify() else 1)
"""


def test_second_instance_notifies_first(qtbot, tmp_path):
    lock = tmp_path / "instance.lock"
    name = f"aureum-island-test-{uuid.uuid4().hex}"
    first = SingleInstance(lock, name)
    try:
        assert first.acquire()
        with qtbot.waitSignal(first.activated, timeout=10_000):
            proc = subprocess.Popen([sys.executable, "-c", _CLIENT, str(lock), name])
        assert proc.wait(timeout=10) == 0  # a segunda viu a primeira e saiu
    finally:
        first.release()
    third = SingleInstance(lock, name)
    assert third.acquire()  # depois que a primeira sai, a próxima vira a primeira
    third.release()


# --- foco ---------------------------------------------------------------------

T0 = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


def test_focus_config_waits_for_next_phase():
    model = FocusModel(FocusConfig(25, 5, 15, 4))
    model.start(T0)
    model.set_config(FocusConfig(50, 10, 20, 4))
    assert model.total() == timedelta(minutes=25)  # a fase atual segue com 25
    assert model.state.end_at == T0 + timedelta(minutes=25)
    model.settle(T0 + timedelta(minutes=25))
    assert model.state.phase is Phase.SHORT_BREAK
    assert model.total() == timedelta(minutes=10)
    assert model.pending_config is None


def test_focus_config_applies_now_when_stopped():
    model = FocusModel(FocusConfig(25, 5, 15, 4))
    model.set_config(FocusConfig(40, 5, 15, 2))
    assert model.state.status is Status.STOPPED
    assert model.total() == timedelta(minutes=40)


# --- janela -------------------------------------------------------------------


@pytest.fixture
def window(qtbot, tmp_path, settings_deps):
    from aureum_island.settings.window import SettingsWindow

    conn = db.connect(tmp_path / "data.db")
    sync = CalendarSync(conn, EventRepo(conn), global_offset=lambda: 10,
                        get_url=lambda _i: None, set_url=lambda _i, _u: None,
                        delete_url=lambda _i: None)  # fmt: skip
    d = settings_deps
    theme = Theme.from_settings(d.store.value, system_dark=True)
    d.store.changed.connect(lambda keys: _apply(theme, d.store, keys))
    w = SettingsWindow(theme, sync, store=d.store, hotkey=d.hotkey, autostart=d.autostart,
                       sound=d.sound)  # fmt: skip
    qtbot.addWidget(w)
    w.deps, w.theme = d, theme
    return w


def _apply(theme, store, keys):
    s = store.value
    if "window_theme" in keys:
        theme.set_window_theme(s.window_theme)
    if "accent" in keys:
        theme.set_accent(s.accent)


def test_window_opens_on_general_with_all_sections(window):
    assert window.nav.currentRow() == 0
    assert set(window.sections) == {"general", "calendar", "notices", "focus_water", "appearance"}
    labels = window.findChildren(QLabel)
    assert not any("Disponível em breve" in label.text() for label in labels)
    assert not any("AUREUM ISLAND" in label.text() for label in labels)
    from aureum_island.island.widgets import Logo

    assert window.findChild(Logo).accessibleName() == "Aureum Island"


def test_general_controls_write_settings(window):
    g, store = window.sections["general"], window.deps.store
    g.mode.chips[1].click()
    assert store.value.mode == "minimal"
    g.fullscreen_switch.click()
    assert store.value.hide_on_fullscreen is False
    g.week.chips[1].click()
    assert store.value.week_start == "monday"
    g.autostart_switch.click()
    assert store.value.autostart is True
    assert VALUE_NAME in window.deps.registry.values


def test_autostart_failure_reverts_switch(window):
    g = window.sections["general"]
    window.deps.registry.fail = True
    g.autostart_switch.click()
    assert g.autostart_switch.isChecked() is False
    assert window.deps.store.value.autostart is False
    assert "registro do Windows" in g.autostart_error.text()


def _key(widget, key, vk, mods=Qt.KeyboardModifier.NoModifier):
    event = QKeyEvent(QEvent.Type.KeyPress, key, mods, 0, vk, 0, "")
    QApplication.sendEvent(widget, event)


def test_hotkey_capture_and_refusal(window):
    g, d = window.sections["general"], window.deps
    ctrl_alt = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
    g.hotkey_field.click()
    assert g.hotkey_field.recording
    assert d.backend.active is None  # solto enquanto grava
    _key(g.hotkey_field, Qt.Key.Key_N, 0x4E, ctrl_alt)
    assert d.store.value.hotkey == "Ctrl+Alt+N"
    assert d.hotkey.active == "Ctrl+Alt+N"
    assert "Ativo: Ctrl+Alt+N" in g.hotkey_status.text()

    g.hotkey_field.click()
    _key(g.hotkey_field, Qt.Key.Key_E, 0x45, ctrl_alt)
    assert d.store.value.hotkey == "Ctrl+Alt+N"
    assert d.hotkey.active == "Ctrl+Alt+N"
    assert "AltGr" in g.hotkey_error.text()

    g.hotkey_field.click()
    _key(g.hotkey_field, Qt.Key.Key_Escape, 0x1B)
    assert not g.hotkey_field.recording
    assert d.hotkey.active == "Ctrl+Alt+N"  # Esc devolve o atalho

    g.none_button.click()
    assert d.store.value.hotkey == ""
    assert g.hotkey_field.text() == "Sem atalho"
    g.default_button.click()
    assert d.store.value.hotkey == "Ctrl+Alt+I"


def test_notices_controls(window):
    n, store = window.sections["notices"], window.deps.store
    n.offset.chips[0].click()
    assert store.value.reminder_offset_min == 0
    n.sound_switch.click()
    assert store.value.sound_enabled is False
    n.volume.setValue(30)
    assert store.value.sound_volume == pytest.approx(0.3)
    n.native_switch.click()
    assert store.value.native_notifications is True


def test_focus_water_controls(window):
    f, store = window.sections["focus_water"], window.deps.store
    f.focus_fields["focus_minutes"].setValue(50)
    assert store.value.focus_minutes == 50
    f.every.setValue(3)
    assert store.value.long_break_every == 3
    f.cup.chips[0].click()
    assert store.value.water_cup_ml == 150
    f.cup_other.setValue(420)
    assert store.value.water_cup_ml == 420
    assert f.cup.value() is None  # 420 não é um chip
    f.end.set_text_quiet("07:00")
    f._save_window()
    assert "antes do fim" in f.window_error.text()
    assert store.value.water_end == "22:00"


def test_chip_group_arrow_keys(window, qtbot):
    f = window.sections["focus_water"]
    window.show()
    window.show_section("focus_water")
    chip = f.interval.chips[2]  # 60 min
    chip.setFocus()
    qtbot.keyClick(chip, Qt.Key.Key_Right)
    assert window.deps.store.value.water_interval_min == 90
    assert f.interval.focusWidget() is f.interval.chips[3]


def test_appearance_theme_and_accent(window):
    a, store, theme = window.sections["appearance"], window.deps.store, window.theme
    a.window_theme.chips[1].click()  # Claro
    assert store.value.window_theme == "light"
    assert theme.window.name == "light"
    assert not a.system_hint.isVisibleTo(a)
    a.window_theme.chips[2].click()
    assert a.system_hint.isVisibleTo(a)
    assert a.system_hint.text() == "Segue o modo claro/escuro do Windows."
    assert [c.accessibleName() for c in a.window_theme.chips] == [
        "Tema: Escuro",
        "Tema: Claro",
        "Tema: Sistema",
    ]

    a.presets[1].click()  # Ametista
    assert store.value.accent == "#8B5CF6"
    assert a.presets[1].selected and not a.other.selected
    assert [s.text() for s in a.presets] == ["Dourado", "Ametista", "Esmeralda", "Brasa", "Safira"]


def test_appearance_hex_field(window):
    a, store = window.sections["appearance"], window.deps.store
    a.hex.setText("#12ab9")
    a._on_hex_edited("#12ab9")
    assert store.value.accent == "#E8B531"  # incompleto: nada muda
    a.hex.setText("#12ab9c")
    a._on_hex_edited("#12ab9c")
    assert a.hex.text() == "#12AB9C"  # maiúsculas
    assert store.value.accent == "#12AB9C"
    assert a.other.selected  # cor que não é preset: "Outra" preenchida
    a.hex.setText("verde")
    a._reset_hex()  # perdeu o foco: volta ao valor atual
    assert a.hex.text() == "#12AB9C"
    assert a.hex.maxLength() == 7


def test_color_dialog_previews_then_saves_or_reverts(window, qtbot):
    from PySide6.QtGui import QColor

    a, store, theme = window.sections["appearance"], window.deps.store, window.theme
    rail = theme.notch.rail
    a.open_picker()
    dialog = a.dialog
    assert dialog.testOption(dialog.ColorDialogOption.DontUseNativeDialog)
    for name in ("#112233", "#445566", "#8B5CF6"):  # arrastando: vários por frame
        dialog.setCurrentColor(QColor(name))
    assert theme.accent == "#E8B531"  # ainda não: junta num frame
    qtbot.waitUntil(lambda: theme.accent == "#8B5CF6", timeout=500)
    assert store.value.accent == "#E8B531"  # prévia não salva
    assert theme.notch.rail == rail  # nem re-tinge
    dialog.reject()
    assert theme.accent == "#E8B531"  # cancelou: volta

    a.open_picker()
    a.dialog.setCurrentColor(QColor("#4F8CC9"))
    a.dialog.accept()
    assert store.value.accent == "#4F8CC9"
    assert theme.notch.rail != rail  # salvou e re-tingiu
