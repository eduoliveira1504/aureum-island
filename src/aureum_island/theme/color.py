"""Funções puras de cor: contraste WCAG 2.x, cor sobre o accent, alpha.

Sem Qt aqui, para poder testar e usar em qualquer camada.
"""

from __future__ import annotations

from collections.abc import Iterable

from aureum_island.theme.tokens import COLORS, MIN_TEXT_CONTRAST

Rgb = tuple[int, int, int]


def parse_hex(value: str) -> Rgb:
    """Converte '#RRGGBB' (ou 'RRGGBB') em (r, g, b). Levanta ValueError se inválido."""
    h = value.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"cor hex inválida: {value!r}")
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError as exc:
        raise ValueError(f"cor hex inválida: {value!r}") from exc


def is_hex_color(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parse_hex(value)
    except ValueError:
        return False
    return value.startswith("#")


def to_hex(rgb: Rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _channel(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def luminance(color: str) -> float:
    """Luminância relativa WCAG 2.x (0 = preto, 1 = branco)."""
    r, g, b = parse_hex(color)
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    """Razão de contraste WCAG entre duas cores (1 a 21)."""
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def on_accent(accent: str) -> str:
    """Cor de texto sobre o accent: a escura padrão ou branco, a que tiver mais contraste."""
    dark, light = COLORS.on_accent_dark, COLORS.on_accent_light
    return dark if contrast(accent, dark) >= contrast(accent, light) else light


def mix(a: str, b: str, t: float) -> str:
    """Mistura linear em sRGB: t=0 devolve a, t=1 devolve b."""
    ra, rb = parse_hex(a), parse_hex(b)
    return to_hex(tuple(round(x + (y - x) * t) for x, y in zip(ra, rb, strict=True)))


def accent_text(accent: str, surfaces: Iterable[str], toward: str = COLORS.on_accent_light) -> str:
    """Accent ajustado para ser lido como texto sobre todas as superfícies.

    Mistura o accent em direção a `toward` (branco nas superfícies escuras, preto nas
    claras; quem decide é o tema) em passos de 2% até atingir 4.5:1 contra todas as
    superfícies. Se já passa, devolve o accent sem mudança. Se nem `toward` passa,
    devolve `toward`.
    """
    surfaces = list(surfaces)
    toward = to_hex(parse_hex(toward))

    def ok(color: str) -> bool:
        return all(contrast(color, s) >= MIN_TEXT_CONTRAST for s in surfaces)

    for step in range(51):
        candidate = mix(accent, toward, step * 0.02) if step else to_hex(parse_hex(accent))
        if ok(candidate):
            return candidate
    return toward


def with_alpha(color: str, alpha: float) -> str:
    """Devolve '#RRGGBBAA' com alpha de 0 a 1 (ex.: 0.20 para a borda do notch)."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha fora de 0..1: {alpha}")
    return to_hex(parse_hex(color)) + f"{round(alpha * 255):02X}"
