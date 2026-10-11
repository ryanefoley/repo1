"""NDBC realtime buoy data.

Two files per station:
  realtime2/<id>.txt   standard met + wave summary (WVHT, DPD, APD, MWD), metric, UTC
  realtime2/<id>.spec  spectral summary: swell vs wind-wave split (SwH/SwP/SwD, WWH/WWP/WWD)

The .spec split matters: a 13 ft NW day can still hide a 2 ft S swell, and the
combined WVHT/MWD numbers will never show it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..units import compass_to_deg, m_to_ft, ms_to_kt
from . import FetchError
from .http import get_text

BASE = "https://www.ndbc.noaa.gov/data/realtime2"


def _num(v: str) -> float | None:
    if v in ("MM", "N/A", ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_table(text: str) -> list[dict]:
    """Parse an NDBC realtime2 file into rows keyed by header name (newest first)."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines or not lines[0].startswith("#"):
        raise FetchError("unexpected NDBC format")
    header = lines[0].lstrip("#").split()
    rows = []
    for ln in lines:
        if ln.startswith("#"):
            continue
        parts = ln.split()
        if len(parts) < len(header):
            continue
        row = dict(zip(header, parts))
        try:
            ts = datetime(
                int(row["YY"]), int(row["MM"]), int(row["DD"]),
                int(row["hh"]), int(row["mm"]), tzinfo=timezone.utc,
            )
        except (KeyError, ValueError):
            continue
        row["_time"] = ts
        rows.append(row)
    return rows


def parse_txt(text: str) -> list[dict]:
    out = []
    for r in parse_table(text):
        out.append({
            "time": r["_time"].isoformat(),
            "wave_height_ft": m_to_ft(_num(r.get("WVHT", "MM"))),
            "dominant_period_s": _num(r.get("DPD", "MM")),
            "avg_period_s": _num(r.get("APD", "MM")),
            "mean_wave_dir_deg": _num(r.get("MWD", "MM")),
            "wind_dir_deg": _num(r.get("WDIR", "MM")),
            "wind_kt": ms_to_kt(_num(r.get("WSPD", "MM"))),
            "gust_kt": ms_to_kt(_num(r.get("GST", "MM"))),
            "water_temp_f": _c_to_f(_num(r.get("WTMP", "MM"))),
        })
    return out


def parse_spec(text: str) -> list[dict]:
    out = []
    for r in parse_table(text):
        swd = r.get("SwD")
        wwd = r.get("WWD")
        out.append({
            "time": r["_time"].isoformat(),
            "wave_height_ft": m_to_ft(_num(r.get("WVHT", "MM"))),
            "swell_height_ft": m_to_ft(_num(r.get("SwH", "MM"))),
            "swell_period_s": _num(r.get("SwP", "MM")),
            "swell_dir": swd if swd not in (None, "MM") else None,
            "swell_dir_deg": compass_to_deg(swd),
            "windwave_height_ft": m_to_ft(_num(r.get("WWH", "MM"))),
            "windwave_period_s": _num(r.get("WWP", "MM")),
            "windwave_dir": wwd if wwd not in (None, "MM") else None,
            "windwave_dir_deg": compass_to_deg(wwd),
            "steepness": r.get("STEEPNESS") if r.get("STEEPNESS") not in (None, "MM", "N/A") else None,
            "mean_wave_dir_deg": _num(r.get("MWD", "MM")),
        })
    return out


def _c_to_f(c: float | None) -> float | None:
    return None if c is None else round(c * 9 / 5 + 32, 1)


def _thin(rows: list[dict], hours: int = 24, every_min: int = 90) -> list[dict]:
    """Keep the last `hours` of rows that have wave data, one every ~`every_min` minutes."""
    with_waves = [r for r in rows if r.get("wave_height_ft") is not None]
    if not with_waves:
        return []
    newest = datetime.fromisoformat(with_waves[0]["time"])
    cutoff = newest - timedelta(hours=hours)
    kept, last = [], None
    for r in with_waves:
        t = datetime.fromisoformat(r["time"])
        if t < cutoff:
            break
        if last is None or (last - t) >= timedelta(minutes=every_min):
            kept.append(r)
            last = t
    return kept


def fetch_station(station: str, spec: bool) -> dict:
    """Latest reading + ~24h trend for one buoy. Spec failure is non-fatal."""
    txt_rows = parse_txt(get_text(f"{BASE}/{station}.txt"))
    result = {
        "station": station,
        "latest": next((r for r in txt_rows if r["wave_height_ft"] is not None), None),
        "latest_wind": next((r for r in txt_rows if r["wind_kt"] is not None), None),
        "trend_24h": _thin(txt_rows),
    }
    if spec:
        try:
            spec_rows = parse_spec(get_text(f"{BASE}/{station}.spec"))
            result["spectral_latest"] = spec_rows[0] if spec_rows else None
            result["spectral_trend_24h"] = _thin(spec_rows)
            # The .spec file is sometimes stale on NDBC's side; flag it.
            if spec_rows and result["latest"]:
                lag = datetime.fromisoformat(result["latest"]["time"]) - datetime.fromisoformat(spec_rows[0]["time"])
                if lag > timedelta(hours=3):
                    result["spectral_warning"] = f"spectral data is {lag} older than the standard data; treat as stale"
        except FetchError as e:
            result["spectral_error"] = str(e)
    return result
