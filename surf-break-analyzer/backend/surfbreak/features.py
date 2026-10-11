"""Deterministic pre-pass: per-spot numbers the model reasons over.

These are deliberately simple heuristics. They give the model consistent,
inspectable inputs (angle vs window, period vs wrap requirement, wind relative
to the break, tide band) — the model is told to use them as evidence, not to
copy the naive size estimate.
"""
from __future__ import annotations

import math

from .units import angle_diff, deg_to_compass, distance_outside, in_range

# Santa Cruz tide range is roughly -1.5 to 6.5 ft MLLW.
TIDE_BANDS = [("low", -99, 2.0), ("mid", 2.0, 4.0), ("high", 4.0, 99)]
TIDE_PREF = {
    "low": {"low"},
    "low-mid": {"low", "mid"},
    "mid": {"mid"},
    "mid-high": {"mid", "high"},
    "high": {"high"},
    "any": {"low", "mid", "high"},
}


def tide_band(h: float | None) -> str | None:
    if h is None:
        return None
    return next(name for name, lo, hi in TIDE_BANDS if lo <= h < hi)


def wind_relation(wind_from: float, faces: float) -> str:
    """How wind blowing FROM wind_from sits on a break that faces `faces`."""
    d = angle_diff(wind_from, faces)
    if d <= 45:
        return "onshore"
    if d <= 80:
        return "cross-onshore"
    if d <= 100:
        return "cross-shore"
    if d <= 135:
        return "cross-offshore"
    return "offshore"


def partition_exposure(part: dict, window: dict) -> dict:
    d, p = part["dir_deg"], part["period_s"]
    best, ok = window["best_dir_deg"], window["ok_dir_deg"]
    wrap_min = window.get("wrap_min_period_s", 12)
    outside_best = distance_outside(d, *best)
    if in_range(d, *best):
        position, factor = "best", 1.0
        wraps = True
    elif in_range(d, *ok):
        position = "ok"
        wraps = p >= wrap_min
        # The further it has to bend, the more energy it loses.
        bend_loss = max(0.25, 0.8 - 0.012 * outside_best)
        factor = bend_loss if wraps else 0.4 * bend_loss
    else:
        position, factor, wraps = "outside", 0.05, False
    # Short-period energy loses more on the way in; long period carries further.
    period_factor = min(max(p / 12.0, 0.6), 1.5)
    return {
        **part,
        "dir_compass": deg_to_compass(d),
        "window_position": position,
        "deg_outside_best": round(outside_best),
        "wraps_in": wraps,
        "needs_period_s": wrap_min if position == "ok" else None,
        "exposure_factor": round(factor, 2),
        "naive_face_ft": round(part["height_ft"] * factor * period_factor, 1),
    }


def _vector_mean_dir(rows: list[dict]) -> float | None:
    xs = [(r["wind_kt"] or 0) * math.sin(math.radians(r["wind_dir_deg"])) for r in rows if r.get("wind_dir_deg") is not None]
    ys = [(r["wind_kt"] or 0) * math.cos(math.radians(r["wind_dir_deg"])) for r in rows if r.get("wind_dir_deg") is not None]
    if not xs:
        return None
    return round(math.degrees(math.atan2(sum(xs), sum(ys))) % 360)


def _representative(rows: list[dict]) -> dict | None:
    """Middle hour of the window."""
    return rows[len(rows) // 2] if rows else None


def observed_partitions(cond: dict) -> list[dict]:
    """Swell + wind-wave split from the offshore buoy (today only)."""
    b = cond.get("buoys", {}).get("46042") or {}
    s = b.get("spectral_latest")
    if not s or b.get("spectral_warning"):
        return []
    parts = []
    if s.get("swell_height_ft") and s.get("swell_dir_deg") is not None and s.get("swell_period_s"):
        parts.append({"kind": "observed_swell", "height_ft": s["swell_height_ft"], "period_s": s["swell_period_s"], "dir_deg": s["swell_dir_deg"]})
    if s.get("windwave_height_ft") and s.get("windwave_dir_deg") is not None and s.get("windwave_period_s"):
        parts.append({"kind": "observed_wind_waves", "height_ft": s["windwave_height_ft"], "period_s": s["windwave_period_s"], "dir_deg": s["windwave_dir_deg"]})
    return parts


def spot_features(spot: dict, cond: dict) -> dict:
    fc = cond["forecast"].get(spot["forecast_point"], {})
    rep = _representative(fc.get("window_hours") or [])
    forecast_parts = [partition_exposure(p, spot["swell_window"]) for p in (rep or {}).get("partitions", [])]
    observed_parts = [partition_exposure(p, spot["swell_window"]) for p in observed_partitions(cond)]

    def combine(parts):
        return round(math.sqrt(sum(p["naive_face_ft"] ** 2 for p in parts)), 1) if parts else None

    out: dict = {
        "id": spot["id"],
        "name": spot["name"],
        "forecast_partitions": forecast_parts,
        "forecast_hour_used": rep["time"] if rep else None,
        "naive_face_ft_forecast": combine(forecast_parts),
    }
    if observed_parts:
        out["observed_partitions"] = observed_parts
        out["naive_face_ft_observed"] = combine(observed_parts)

    size_lo, size_hi = spot["size_range_ft"]
    est = out.get("naive_face_ft_observed") or out["naive_face_ft_forecast"]
    if est is not None:
        out["naive_vs_size_range"] = "below" if est < size_lo else "above" if est > size_hi else "within"

    winds = fc.get("wind_window_hours") or []
    speeds = [w["wind_kt"] for w in winds if w.get("wind_kt") is not None]
    wdir = _vector_mean_dir(winds)
    if speeds and wdir is not None:
        out["wind"] = {
            "avg_kt": round(sum(speeds) / len(speeds), 1),
            "max_gust_kt": max((w["gust_kt"] or 0) for w in winds),
            "from_deg": wdir,
            "from_compass": deg_to_compass(wdir),
            "relative_to_break": wind_relation(wdir, spot["faces_deg"]),
        }

    tide = cond.get("tide") or {}
    heights = [h["height_ft"] for h in tide.get("window_hours", []) if h.get("height_ft") is not None]
    if heights:
        bands = sorted({tide_band(h) for h in heights}, key=["low", "mid", "high"].index)
        pref = spot["tide"].get("best", "any")
        out["tide"] = {
            "range_ft": [min(heights), max(heights)],
            "bands": bands,
            "state": tide["window_hours"][0].get("state"),
            "spot_prefers": pref,
            "matches_preference": bool(set(bands) & TIDE_PREF.get(pref, TIDE_PREF["any"])),
        }
    return out


def build(spots: list[dict], cond: dict) -> list[dict]:
    return [spot_features(s, cond) for s in spots]
