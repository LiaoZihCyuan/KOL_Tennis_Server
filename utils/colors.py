"""Coach representative colors: pick a new color as different as possible from
the ones already in use, measured in CIELAB (perceptual distance), so the
calendar stays readable however many coaches there are."""
import colorsys
import re
from typing import Iterable, List, Optional, Tuple

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# Candidate colors: hues every 5°, at a few saturation/lightness levels that
# keep white event text readable on the calendar.
_SL_LEVELS = [(0.70, 0.55), (0.65, 0.45), (0.75, 0.62)]


def is_valid_hex(value: Optional[str]) -> bool:
    return bool(value) and bool(HEX_RE.match(value))


def _hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(c * 255):02X}" for c in rgb)


def _rgb_to_lab(rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def color_distance(a: str, b: str) -> float:
    """CIE76 ΔE between two #RRGGBB colors."""
    la, lb = _rgb_to_lab(_hex_to_rgb(a)), _rgb_to_lab(_hex_to_rgb(b))
    return sum((p - q) ** 2 for p, q in zip(la, lb)) ** 0.5


def _candidates() -> List[str]:
    return [
        _rgb_to_hex(colorsys.hls_to_rgb(hue / 360, l, s))
        for s, l in _SL_LEVELS
        for hue in range(0, 360, 5)
    ]


def suggest_distinct_color(existing: Iterable[Optional[str]]) -> str:
    """The candidate color farthest from its nearest existing color."""
    used = [c for c in existing if is_valid_hex(c)]
    candidates = _candidates()
    if not used:
        return candidates[0]
    return max(candidates, key=lambda c: min(color_distance(c, u) for u in used))
