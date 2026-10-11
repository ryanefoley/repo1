"""Open-Meteo marine (swell partitions) and wind forecasts. Free, no key."""
from __future__ import annotations

from datetime import date

from . import FetchError
from .http import get_json

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WIND_URL = "https://api.open-meteo.com/v1/forecast"

MARINE_VARS = [
    "wave_height", "wave_direction", "wave_period",
    "wind_wave_height", "wind_wave_direction", "wind_wave_period",
    "swell_wave_height", "swell_wave_direction", "swell_wave_period", "swell_wave_peak_period",
    "secondary_swell_wave_height", "secondary_swell_wave_direction", "secondary_swell_wave_period",
]
TERTIARY_VARS = [
    "tertiary_swell_wave_height", "tertiary_swell_wave_direction", "tertiary_swell_wave_period",
]
WIND_VARS = ["wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"]

TZ_NAME = "America/Los_Angeles"


def _rows(payload: dict) -> list[dict]:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    keys = [k for k in hourly if k != "time"]
    return [{"time": t, **{k: hourly[k][i] for k in keys}} for i, t in enumerate(times)]


def parse_marine(payload: dict) -> list[dict]:
    out = []
    for r in _rows(payload):
        partitions = []
        for label, prefix in (
            ("primary_swell", "swell_wave"),
            ("secondary_swell", "secondary_swell_wave"),
            ("tertiary_swell", "tertiary_swell_wave"),
            ("wind_waves", "wind_wave"),
        ):
            h = r.get(f"{prefix}_height")
            d = r.get(f"{prefix}_direction")
            p = r.get(f"{prefix}_period")
            if h is None or d is None or p is None or h < 0.3:
                continue
            part = {"kind": label, "height_ft": round(h, 1), "period_s": round(p, 1), "dir_deg": round(d)}
            if label == "primary_swell" and r.get("swell_wave_peak_period") is not None:
                part["peak_period_s"] = round(r["swell_wave_peak_period"], 1)
            partitions.append(part)
        out.append({
            "time": r["time"],
            "total_height_ft": _r1(r.get("wave_height")),
            "total_dir_deg": _r0(r.get("wave_direction")),
            "total_period_s": _r1(r.get("wave_period")),
            "partitions": partitions,
        })
    return out


def parse_wind(payload: dict) -> list[dict]:
    return [
        {
            "time": r["time"],
            "wind_kt": _r1(r.get("wind_speed_10m")),
            "wind_dir_deg": _r0(r.get("wind_direction_10m")),
            "gust_kt": _r1(r.get("wind_gusts_10m")),
        }
        for r in _rows(payload)
    ]


def _r1(v):
    return None if v is None else round(v, 1)


def _r0(v):
    return None if v is None else round(v)


def fetch_marine(lat: float, lon: float, day: date) -> list[dict]:
    params = {
        "latitude": lat, "longitude": lon,
        "length_unit": "imperial", "timezone": TZ_NAME,
        "start_date": day.isoformat(), "end_date": day.isoformat(),
    }
    try:
        payload = get_json(MARINE_URL, {**params, "hourly": ",".join(MARINE_VARS + TERTIARY_VARS)})
    except FetchError:
        # Tertiary swell only exists for some wave models; retry without it.
        payload = get_json(MARINE_URL, {**params, "hourly": ",".join(MARINE_VARS)})
    if payload.get("error"):
        raise FetchError(f"open-meteo marine: {payload.get('reason')}")
    return parse_marine(payload)


def fetch_wind(lat: float, lon: float, day: date) -> list[dict]:
    payload = get_json(WIND_URL, {
        "latitude": lat, "longitude": lon,
        "hourly": ",".join(WIND_VARS), "wind_speed_unit": "kn", "timezone": TZ_NAME,
        "start_date": day.isoformat(), "end_date": day.isoformat(),
    })
    if payload.get("error"):
        raise FetchError(f"open-meteo wind: {payload.get('reason')}")
    return parse_wind(payload)
