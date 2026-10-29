from aureum_island.services.storage.settings import Settings
from aureum_island.theme.fonts import register_fonts
from aureum_island.theme.theme import Theme, qcolor


def test_fonts_register(qapp):
    families = register_fonts()
    assert "Inter" in families
    assert "Cinzel" in families


def test_theme_from_settings(qapp):
    theme = Theme.from_settings(Settings(accent="#8B5CF6", notch_bg="marrom"))
    assert theme.accent == "#8B5CF6"
    assert theme.notch_bg == "#1A120C"
    assert theme.on_accent == "#0A0908"
    assert theme.border_notch == "#8B5CF633"


def test_theme_emits_changed_only_on_real_change(qtbot):
    theme = Theme()
    with qtbot.waitSignal(theme.changed):
        theme.set_accent("#3fbf7f")
    assert theme.accent == "#3FBF7F"
    assert theme.border_button == "#3FBF7F4C"

    with qtbot.assertNotEmitted(theme.changed):
        theme.set_accent("#3FBF7F")
        theme.set_notch_bg("preto")

    with qtbot.waitSignal(theme.changed):
        theme.set_notch_bg("grafite")
    assert theme.notch_bg == "#1C1915"


def test_qcolor_with_alpha(qapp):
    c = qcolor("#E8B53133")
    assert (c.red(), c.green(), c.blue(), c.alpha()) == (0xE8, 0xB5, 0x31, 0x33)
