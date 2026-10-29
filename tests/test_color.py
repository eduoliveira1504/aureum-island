import pytest

from aureum_island.theme.color import accent_text, contrast, on_accent, with_alpha
from aureum_island.theme.tokens import ACCENT_PRESETS, COLORS, NOTCH_BACKGROUNDS

SURFACES = [bg for _, bg in NOTCH_BACKGROUNDS.values()] + [
    COLORS.surface,
    COLORS.panel,
    COLORS.sidebar,
]


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("#000000", "#FFFFFF", 21.0),
        ("#FFFFFF", "#FFFFFF", 1.0),
        ("#777777", "#FFFFFF", 4.48),
        ("#F1E8D3", "#070605", 16.6),
        ("#A89F88", "#070605", 7.69),
    ],
)
def test_contrast_known_pairs(a, b, expected):
    assert contrast(a, b) == pytest.approx(expected, abs=0.01)
    assert contrast(b, a) == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize(
    ("preset", "expected"),
    [
        ("dourado", "#0A0908"),
        ("ametista", "#0A0908"),
        ("esmeralda", "#0A0908"),
        ("brasa", "#0A0908"),
        ("safira", "#0A0908"),
    ],
)
def test_on_accent_presets(preset, expected):
    accent = ACCENT_PRESETS[preset][1]
    assert on_accent(accent) == expected
    assert contrast(on_accent(accent), accent) >= 4.5


def test_on_accent_picks_white_for_dark_accent():
    assert on_accent("#202020") == "#FFFFFF"


@pytest.mark.parametrize("accent", [hex_ for _, hex_ in ACCENT_PRESETS.values()] + ["#202020"])
def test_accent_text_reaches_minimum(accent):
    result = accent_text(accent, SURFACES)
    assert all(contrast(result, s) >= 4.5 for s in SURFACES)


def test_accent_text_keeps_accent_that_already_passes():
    assert accent_text("#E8B531", SURFACES) == "#E8B531"


def test_accent_text_lightens_ametista_on_surface():
    # Ametista dá 4.44 contra surface: precisa clarear.
    result = accent_text("#8B5CF6", SURFACES)
    assert result != "#8B5CF6"


def test_accent_text_falls_back_to_white_on_light_surface():
    assert accent_text("#E8B531", ["#FFFFFF"]) == "#FFFFFF"


def test_with_alpha():
    assert with_alpha("#E8B531", 0.20) == "#E8B53133"
    assert with_alpha("#e8b531", 0.30) == "#E8B5314C"
    with pytest.raises(ValueError):
        with_alpha("#E8B531", 1.5)


def test_text_tokens_on_all_notch_backgrounds():
    for _, bg in NOTCH_BACKGROUNDS.values():
        for fg in (COLORS.text, COLORS.text_muted, COLORS.text_dim):
            assert contrast(fg, bg) >= 4.5, (fg, bg)
