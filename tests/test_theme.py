import pytest

from aureum_island.services.storage.settings import Settings
from aureum_island.theme.color import contrast, retint
from aureum_island.theme.fonts import register_fonts
from aureum_island.theme.theme import Theme, build_scheme, qcolor
from aureum_island.theme.tokens import (
    ACCENT_PRESETS,
    DARK,
    LIGHT,
    MIN_TEXT_CONTRAST,
    RETINT_REFERENCE,
)

PRESETS = [hex_ for _, hex_ in ACCENT_PRESETS.values()]
KNOWN_LOW_ON_ACCENT = ACCENT_PRESETS["ametista"][1]


def test_fonts_register(qapp):
    families = register_fonts()
    assert "Figtree" in families
    assert "Sora" in families
    assert "Inter" not in families and "Cinzel" not in families


# --- contraste: presets × temas × pares ----------------------------------------


@pytest.mark.parametrize("name", ["dark", "light"])
@pytest.mark.parametrize("accent", PRESETS)
def test_every_text_pair_reaches_minimum_contrast(name, accent):
    """Todo texto/superfície e accent-text/superfície, nos dois temas e com todos os
    presets: ≥ 4.5:1. fg-subtle, success e danger contam pelas versões *_text, que são as
    usadas como texto (decisão 0009); os preenchimentos ficam com os valores do Voice."""
    s = build_scheme(name, accent)
    texts = {
        "text": s.text,
        "text_muted": s.text_muted,
        "subtle_text": s.subtle_text,
        "success_text": s.success_text,
        "danger_text": s.danger_text,
        "accent_text": s.accent_text,
    }
    for label, fg in texts.items():
        for bg in s.surfaces:
            assert contrast(fg, bg) >= MIN_TEXT_CONTRAST, (name, accent, label, fg, bg)
    # on-accent é a melhor das duas tintas do Voice (#1A1406 ou #FFFFFF). No Ametista
    # nenhuma chega a 4.5 (4.33): exceção conhecida, em aberto na decisão 0009.
    best = max(contrast(ink, s.accent) for ink in ("#1A1406", "#FFFFFF"))
    assert contrast(s.on_accent, s.accent) == best
    if accent != KNOWN_LOW_ON_ACCENT:
        assert best >= MIN_TEXT_CONTRAST
    assert contrast(s.on_danger, s.danger) >= MIN_TEXT_CONTRAST


@pytest.mark.parametrize("accent", PRESETS)
def test_scheme_keeps_voice_fills(accent):
    s = build_scheme("light", accent)
    assert (s.success, s.danger) == (LIGHT.success, LIGHT.danger)  # sem re-tint
    assert s.main == retint(LIGHT.bg_main, accent, RETINT_REFERENCE)


def test_gold_reproduces_voice_palette_exactly():
    s = build_scheme("dark", RETINT_REFERENCE)
    assert (s.rail, s.panel, s.main, s.elevated, s.border, s.text, s.text_muted) == (
        DARK.bg_rail,
        DARK.bg_panel,
        DARK.bg_main,
        DARK.bg_elevated,
        DARK.border,
        DARK.text,
        DARK.text_muted,
    )
    assert s.subtle == "#7B7568"  # color-mix(in oklab, text-muted 72%, bg-main)
    assert s.on_accent == "#1A1406"


# --- Theme ----------------------------------------------------------------------


def test_notch_is_always_dark_retinted(qapp):
    theme = Theme("#8B5CF6", window_theme="light")
    assert theme.notch.name == "dark"
    assert theme.notch_bg == retint(DARK.bg_rail, "#8B5CF6", RETINT_REFERENCE)
    assert theme.window.name == "light"
    assert theme.border_notch == "#8B5CF633"  # contorno do notch segue o accent


def test_theme_from_settings(qapp):
    theme = Theme.from_settings(Settings(accent="#4F8CC9", window_theme="dark"))
    assert theme.accent == "#4F8CC9"
    assert theme.window is theme.notch


def test_theme_emits_changed_only_on_real_change(qtbot):
    theme = Theme()
    with qtbot.waitSignal(theme.changed):
        theme.set_accent("#3fbf7f")
    assert theme.accent == "#3FBF7F"
    with qtbot.assertNotEmitted(theme.changed):
        theme.set_accent("#3FBF7F")
        theme.set_window_theme("dark")


def test_system_theme_follows_windows(qtbot):
    theme = Theme(window_theme="system", system_dark=True)
    assert theme.window.name == "dark"
    with qtbot.waitSignal(theme.changed):
        theme.set_system_dark(False)
    assert theme.window.name == "light"
    theme.set_window_theme("dark")
    with qtbot.assertNotEmitted(theme.changed):
        theme.set_system_dark(True)


def test_preview_changes_only_accent_colors(qtbot):
    theme = Theme("#E8B531", window_theme="light")
    rail, main = theme.notch.rail, theme.window.main
    with qtbot.waitSignal(theme.changed):
        theme.preview_accent("#8B5CF6")
    assert theme.accent == "#8B5CF6"
    assert theme.window.accent_text != build_scheme("light", "#E8B531").accent_text
    assert (theme.notch.rail, theme.window.main) == (rail, main)  # sem re-tint na prévia
    with qtbot.waitSignal(theme.changed):
        theme.end_preview()
    assert theme.accent == "#E8B531"
    with qtbot.assertNotEmitted(theme.changed):
        theme.end_preview()  # nada a desfazer


def test_qcolor_with_alpha(qapp):
    c = qcolor("#E8B53133")
    assert (c.red(), c.green(), c.blue(), c.alpha()) == (0xE8, 0xB5, 0x31, 0x33)
