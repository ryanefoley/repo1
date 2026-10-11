"""Unit conversions and compass helpers."""
from __future__ import annotations

M_TO_FT = 3.28084
MS_TO_KT = 1.943844

COMPASS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def m_to_ft(v: float | None) -> float | None:
    return None if v is None else round(v * M_TO_FT, 1)


def ms_to_kt(v: float | None) -> float | None:
    return None if v is None else round(v * MS_TO_KT, 1)


def compass_to_deg(c: str | None) -> float | None:
    if not c:
        return None
    c = c.strip().upper()
    if c not in COMPASS:
        return None
    return COMPASS.index(c) * 22.5


def deg_to_compass(d: float | None) -> str | None:
    if d is None:
        return None
    return COMPASS[int(((d % 360) + 11.25) // 22.5) % 16]


def angle_diff(a: float, b: float) -> float:
    """Smallest absolute difference between two bearings, 0..180."""
    d = abs((a - b) % 360)
    return 360 - d if d > 180 else d


def in_range(deg: float, lo: float, hi: float) -> bool:
    """Is bearing `deg` inside the clockwise arc lo -> hi (handles wrap past 360)?"""
    deg, lo, hi = deg % 360, lo % 360, hi % 360
    if lo <= hi:
        return lo <= deg <= hi
    return deg >= lo or deg <= hi


def distance_outside(deg: float, lo: float, hi: float) -> float:
    """Degrees outside the arc lo -> hi (0 if inside)."""
    if in_range(deg, lo, hi):
        return 0.0
    return min(angle_diff(deg, lo), angle_diff(deg, hi))
