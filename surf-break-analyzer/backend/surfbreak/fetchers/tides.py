"""NOAA CO-OPS tide predictions.

Santa Cruz (9413745) is a subordinate station, so NOAA publishes hi/lo times only.
Hourly heights are interpolated with the standard cosine (half-wave) method,
which is accurate to a few tenths of a foot between extremes.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from .. import config
from . import FetchError
from .http import get_json

URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


def parse_hilo(payload: dict) -> list[dict]:
    if "error" in payload:
        raise FetchError(f"tides: {payload['error'].get('message', payload['error'])}")
    out = []
    for p in payload.get("predictions", []):
        t = datetime.strptime(p["t"], "%Y-%m-%d %H:%M").replace(tzinfo=config.TZ)
        out.append({"time": t.isoformat(), "height_ft": round(float(p["v"]), 2), "type": "high" if p["type"] == "H" else "low"})
    return out


def interpolate(extremes: list[dict], when: datetime) -> float | None:
    """Cosine interpolation between the surrounding hi/lo."""
    pts = [(datetime.fromisoformat(e["time"]), e["height_ft"]) for e in extremes]
    for (t0, h0), (t1, h1) in zip(pts, pts[1:]):
        if t0 <= when <= t1:
            frac = (when - t0) / (t1 - t0)
            return round(h0 + (h1 - h0) * (1 - math.cos(math.pi * frac)) / 2, 2)
    return None


def tide_state(extremes: list[dict], when: datetime) -> str | None:
    pts = [(datetime.fromisoformat(e["time"]), e) for e in extremes]
    for (t0, e0), (t1, e1) in zip(pts, pts[1:]):
        if t0 <= when <= t1:
            return "rising" if e1["height_ft"] > e0["height_ft"] else "falling"
    return None


def fetch_day(day: date) -> dict:
    """Hi/lo extremes from the day before to the day after (so any hour can be interpolated)."""
    payload = get_json(URL, {
        "station": config.TIDE_STATION,
        "product": "predictions", "datum": "MLLW", "units": "english",
        "time_zone": "lst_ldt", "interval": "hilo", "format": "json",
        "begin_date": (day - timedelta(days=1)).strftime("%Y%m%d"),
        "end_date": (day + timedelta(days=1)).strftime("%Y%m%d"),
        "application": "surf-break-analyzer",
    })
    extremes = parse_hilo(payload)
    hourly = []
    start = datetime(day.year, day.month, day.day, tzinfo=config.TZ)
    for h in range(24):
        t = start + timedelta(hours=h)
        hourly.append({"time": t.isoformat(), "height_ft": interpolate(extremes, t), "state": tide_state(extremes, t)})
    same_day = [e for e in extremes if datetime.fromisoformat(e["time"]).date() == day]
    return {"station": config.TIDE_STATION, "extremes": same_day, "hourly": hourly, "_all_extremes": extremes}
