"""Posição e tamanho do notch (funções puras, em pixels lógicos)."""

from __future__ import annotations

from dataclasses import dataclass

from aureum_island.island.state import State
from aureum_island.theme.tokens import NOTCH, NOTICE


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Shape:
    width: float
    height: float
    radius: float


SHAPES: dict[State, Shape] = {
    State.CLOSED: Shape(NOTCH.closed_width, NOTCH.closed_height, NOTCH.closed_radius),
    State.MINIMAL: Shape(NOTCH.minimal_width, NOTCH.minimal_height, NOTCH.minimal_radius),
    State.OPEN: Shape(
        NOTCH.open_width,
        NOTCH.open_content_height + NOTCH.open_bar_height,
        NOTCH.open_radius,
    ),
    State.NOTICE: Shape(NOTICE.width, NOTICE.height, NOTICE.radius),
}


def shape_for(state: State) -> Shape:
    return SHAPES[state]


def lerp_shape(a: Shape, b: Shape, t: float) -> Shape:
    return Shape(
        a.width + (b.width - a.width) * t,
        a.height + (b.height - a.height) * t,
        a.radius + (b.radius - a.radius) * t,
    )


def notch_rect(screen: Rect, shape: Shape) -> Rect:
    """Colado no topo do monitor (geometry, não availableGeometry), centralizado em x.
    Nunca maior que a tela."""
    width = min(round(shape.width), screen.width)
    height = min(round(shape.height), screen.height)
    x = screen.x + (screen.width - width) // 2
    return Rect(x, screen.y, width, height)


def shadow_rect(notch: Rect, margin: int) -> Rect:
    """Janela da sombra: o notch expandido para os lados e para baixo (o topo é a borda
    da tela)."""
    return Rect(notch.x - margin, notch.y, notch.width + 2 * margin, notch.height + margin)
