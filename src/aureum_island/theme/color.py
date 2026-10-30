"""Funções puras de cor: contraste WCAG 2.x, tinta sobre uma cor, cor legível e re-tint.

Porte do `lib/color.ts` do Aureum Voice, com o mesmo comportamento (inclusive o
arredondamento do `Math.round` e os passos de 2% do `readableOn`). Sem Qt aqui, para
poder testar e usar em qualquer camada.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from aureum_island.theme.tokens import INK_DARK, INK_LIGHT, MIN_TEXT_CONTRAST

Rgb = tuple[float, float, float]
Lch = tuple[float, float, float]  # L 0..1, C >= 0, h em graus


def _js_round(x: float) -> int:
    """Math.round do JavaScript (meio arredonda para cima, não para o par)."""
    return math.floor(x + 0.5)


def parse_hex(value: str) -> tuple[int, int, int]:
    """'#RRGGBB' (ou 'RRGGBB') -> (r, g, b). Levanta ValueError se inválido."""
    h = value.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"cor hex inválida: {value!r}")
    try:
        n = int(h, 16)
    except ValueError as exc:
        raise ValueError(f"cor hex inválida: {value!r}") from exc
    return (n >> 16) & 255, (n >> 8) & 255, n & 255


def is_hex_color(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("#"):
        return False
    try:
        parse_hex(value)
    except ValueError:
        return False
    return True


def to_hex(rgb: Iterable[float]) -> str:
    return "#" + "".join(f"{_js_round(c):02X}" for c in rgb)


def _linear(c: float) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def _from_linear(c: float) -> float:
    s = c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return min(255.0, max(0.0, s * 255))


def _luminance(rgb: Rgb) -> float:
    r, g, b = (_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(a: Rgb, b: Rgb) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def luminance(color: str) -> float:
    """Luminância relativa WCAG 2.x (0 = preto, 1 = branco)."""
    return _luminance(parse_hex(color))


def contrast(a: str, b: str) -> float:
    """Razão de contraste WCAG entre duas cores (1 a 21)."""
    return _ratio(parse_hex(a), parse_hex(b))


def ink_on(background: str) -> str:
    """Tinta para conteúdo sobre `background`: #1A1406 ou #FFFFFF, a que contrastar mais."""
    return (
        INK_DARK if contrast(INK_DARK, background) >= contrast(INK_LIGHT, background) else INK_LIGHT
    )


# --- OKLab / OKLCH ------------------------------------------------------------


def _to_oklab(rgb: Rgb) -> tuple[float, float, float]:
    r, g, b = (_linear(c) for c in rgb)
    l_ = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (
        0.2104542553 * l_ + 0.793617785 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.428592205 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.808675766 * s_,
    )


def _from_oklab(lab: tuple[float, float, float]) -> Rgb:
    big_l, a, b = lab
    l_ = (big_l + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (big_l - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (big_l - 0.0894841775 * a - 1.291485548 * b) ** 3
    return (
        _from_linear(4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_),
        _from_linear(-1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_),
        _from_linear(-0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_),
    )


def _to_oklch(rgb: Rgb) -> Lch:
    big_l, a, b = _to_oklab(rgb)
    return big_l, math.hypot(a, b), (math.degrees(math.atan2(b, a)) + 360) % 360


def _from_oklch(lch: Lch) -> Rgb:
    big_l, c, h = lch
    return _from_oklab((big_l, c * math.cos(math.radians(h)), c * math.sin(math.radians(h))))


def retint(base: str, accent: str, reference: str) -> str:
    """Leva uma cor neutra da paleta (desenhada em volta de `reference`) para o matiz do
    `accent`: a luminosidade fica, o matiz gira o mesmo ângulo que separa o accent da
    referência, e o croma escala com o do accent (nunca acima do original). Com
    accent == reference devolve `base`; um accent cinza dá um cinza puro."""
    big_l, c, h = _to_oklch(parse_hex(base))
    _, accent_c, accent_h = _to_oklch(parse_hex(accent))
    _, ref_c, ref_h = _to_oklch(parse_hex(reference))
    scale = min(1.0, accent_c / ref_c) if ref_c > 0 else 0.0
    return to_hex(_from_oklch((big_l, c * scale, (h + accent_h - ref_h + 360) % 360)))


def mix_oklab(a: str, b: str, weight_a: float) -> str:
    """Como `color-mix(in oklab, a weight_a, b)` do CSS."""
    la, lb = _to_oklab(parse_hex(a)), _to_oklab(parse_hex(b))
    return to_hex(
        _from_oklab(tuple(x * weight_a + y * (1 - weight_a) for x, y in zip(la, lb, strict=True)))
    )


def readable_on(color: str, backgrounds: Iterable[str], minimum: float = MIN_TEXT_CONTRAST) -> str:
    """`color` ajustada para ser lida como texto sobre todos os `backgrounds`.

    Mistura em direção ao preto em fundos claros e ao branco em escuros (pela luminância
    média dos fundos), em passos de 2%, mantendo o matiz. Se já passa, volta como está.
    """
    start = parse_hex(color)
    bgs = [parse_hex(bg) for bg in backgrounds]
    if not bgs:
        return to_hex(start)

    def passes(c: Rgb) -> bool:
        return all(_ratio(c, bg) >= minimum for bg in bgs)

    if passes(start):
        return to_hex(start)
    avg = sum(_luminance(bg) for bg in bgs) / len(bgs)
    target = (0, 0, 0) if avg > 0.18 else (255, 255, 255)
    t = 0.02
    while t <= 1:  # mesma soma em ponto flutuante do laço do Voice
        mixed = tuple(c + (target[i] - c) * t for i, c in enumerate(start))
        if passes(mixed):
            return to_hex(mixed)
        t += 0.02
    return to_hex(target)


def with_alpha(color: str, alpha: float) -> str:
    """'#RRGGBBAA' com alpha de 0 a 1 (ex.: 0.20 para o contorno do notch)."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha fora de 0..1: {alpha}")
    return to_hex(parse_hex(color)) + f"{round(alpha * 255):02X}"
