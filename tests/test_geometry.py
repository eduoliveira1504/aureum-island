import pytest

from aureum_island.island.geometry import (
    Rect,
    Shape,
    lerp_shape,
    notch_rect,
    shadow_rect,
    shape_for,
)
from aureum_island.island.state import State


def logical(width, height, scale, x=0, y=0):
    """Geometria lógica que o Qt reporta para um monitor físico com escala."""
    return Rect(round(x / scale), round(y / scale), round(width / scale), round(height / scale))


@pytest.mark.parametrize(
    ("screen", "state", "expected"),
    [
        (Rect(0, 0, 1920, 1080), State.CLOSED, Rect(865, 0, 190, 34)),
        (Rect(0, 0, 1920, 1080), State.OPEN, Rect(650, 0, 620, 224)),
        (Rect(0, 0, 1920, 1080), State.MINIMAL, Rect(885, 0, 150, 6)),
        (Rect(0, 0, 1920, 1080), State.NOTICE, Rect(780, 0, 360, 64)),
        # 125% em 1920x1080 -> 1536x864 lógicos
        (logical(1920, 1080, 1.25), State.OPEN, Rect(458, 0, 620, 224)),
        # 150% em 1920x1080 -> 1280x720 lógicos
        (logical(1920, 1080, 1.5), State.CLOSED, Rect(545, 0, 190, 34)),
        # 150% em 1366x768 -> 911x512 lógicos: ainda cabe aberto
        (logical(1366, 768, 1.5), State.OPEN, Rect(145, 0, 620, 224)),
        # monitor principal à direita de outro e mais abaixo
        (Rect(2560, 120, 1920, 1080), State.CLOSED, Rect(3425, 120, 190, 34)),
        # monitor à esquerda (coordenadas negativas)
        (Rect(-1920, 0, 1920, 1080), State.OPEN, Rect(-1270, 0, 620, 224)),
    ],
)
def test_notch_rect(screen, state, expected):
    assert notch_rect(screen, shape_for(state)) == expected


def test_notch_never_wider_than_screen():
    narrow = logical(800, 600, 1.5)  # 533 lógicos
    rect = notch_rect(narrow, shape_for(State.OPEN))
    assert rect.width == narrow.width
    assert rect.x == narrow.x


def test_notch_stays_centered_during_animation():
    screen = Rect(0, 0, 1920, 1080)
    a, b = shape_for(State.CLOSED), shape_for(State.OPEN)
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        rect = notch_rect(screen, lerp_shape(a, b, t))
        center = rect.x + rect.width / 2
        assert abs(center - 960) <= 0.5


def test_lerp_shape_interpolates_radius():
    a, b = Shape(190, 34, 18), Shape(620, 224, 30)
    assert lerp_shape(a, b, 0) == a
    assert lerp_shape(a, b, 1) == b
    assert lerp_shape(a, b, 0.5) == Shape(405, 129, 24)


def test_shadow_rect_wraps_sides_and_bottom_only():
    notch = Rect(650, 0, 620, 224)
    assert shadow_rect(notch, 24) == Rect(626, 0, 668, 248)
