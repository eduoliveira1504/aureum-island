"""theme/color.py contra o lib/color.ts do Aureum Voice.

tests/data/voice_color_ref.json foi gerado rodando o color.ts do Voice com o node
(tests/data/voice_color_ref.ts): os 5 presets e um cinza, nos temas escuro e claro.
"""

import json
from pathlib import Path

import pytest

from aureum_island.theme.color import (
    contrast,
    ink_on,
    is_hex_color,
    luminance,
    mix_oklab,
    readable_on,
    retint,
    with_alpha,
)
from aureum_island.theme.tokens import DARK, LIGHT, RETINT_REFERENCE

VOICE = json.loads((Path(__file__).parent / "data" / "voice_color_ref.json").read_text())
ACCENTS = list(VOICE)
FIELDS = {
    "rail": "bg_rail",
    "panel": "bg_panel",
    "main": "bg_main",
    "elevated": "bg_elevated",
    "border": "border",
    "text": "text",
    "muted": "text_muted",
}


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("#000000", "#FFFFFF", 21.0),
        ("#FFFFFF", "#FFFFFF", 1.0),
        ("#777777", "#FFFFFF", 4.48),
        ("#F4EFE4", "#0A0908", 17.35),
    ],
)
def test_contrast_known_pairs(a, b, expected):
    assert contrast(a, b) == pytest.approx(expected, abs=0.01)
    assert contrast(b, a) == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize("accent", ACCENTS)
def test_ink_on_matches_voice(accent):
    assert ink_on(accent) == VOICE[accent]["ink"]


def test_ink_on_dark_color_is_white():
    assert ink_on("#202020") == "#FFFFFF"


@pytest.mark.parametrize("accent", ACCENTS)
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_retint_matches_voice(accent, theme):
    palette = DARK if theme == "dark" else LIGHT
    for key, attr in FIELDS.items():
        got = retint(getattr(palette, attr), accent, RETINT_REFERENCE)
        assert got == VOICE[accent][theme][key], (accent, theme, key)


@pytest.mark.parametrize("accent", ACCENTS)
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_readable_on_matches_voice(accent, theme):
    tinted = VOICE[accent][theme]
    surfaces = [tinted[k] for k in ("rail", "panel", "main", "elevated")]
    assert readable_on(accent, surfaces) == VOICE[accent][f"{theme}_accent_text"]


def test_retint_with_reference_is_identity_and_gray_is_neutral():
    assert retint("#17150F", RETINT_REFERENCE, RETINT_REFERENCE) == "#17150F"
    r, g, b = (
        int(retint("#17150F", "#808080", RETINT_REFERENCE)[i : i + 2], 16) for i in (1, 3, 5)
    )
    assert r == g == b


def test_readable_on_direction_follows_background_luminance():
    # Fundo claro: mistura para o preto; fundo escuro: para o branco.
    on_light = readable_on("#E8B531", ["#FFFFFF"])
    assert luminance(on_light) < luminance("#E8B531") and contrast(on_light, "#FFFFFF") >= 4.5
    on_dark = readable_on("#2020A0", ["#0A0908"])
    assert luminance(on_dark) > luminance("#2020A0") and contrast(on_dark, "#0A0908") >= 4.5


def test_mix_oklab_endpoints_and_subtle():
    assert mix_oklab("#A8A090", "#17150F", 1.0) == "#A8A090"
    assert mix_oklab("#A8A090", "#17150F", 0.0) == "#17150F"
    assert mix_oklab("#A8A090", "#17150F", 0.72) == "#7B7568"  # fg-subtle do escuro


def test_hex_helpers():
    assert is_hex_color("#E8B531")
    assert not is_hex_color("E8B531")
    assert not is_hex_color("#E8B53")
    assert with_alpha("#E8B531", 0.20) == "#E8B53133"
