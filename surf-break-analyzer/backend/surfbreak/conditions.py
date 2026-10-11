"""Assemble all inputs for one date + time window into a single conditions dict.

Every source is optional: a failed fetch is recorded in `sources` and the rest
of the run continues with less data.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from . import config
from .fetchers import FetchError, ndbc, openmeteo, tides


def window_bounds(day: date, start_hour: int, end_hour: int) -> tuple[datetime, datetime]:
    if not (0 <= start_hour <= 23 and 1 <= end_hour <= 24 and start_hour < end_hour):
        raise ValueError("window must satisfy 0 <= start < end <= 24")
    start = datetime.combine(day, time(start_hour), tzinfo=config.TZ)
    return start, start + timedelta(hours=end_hour - start_hour)


def validate_day(day: date, today: date) -> None:
    if day < today - timedelta(days=1):
        raise ValueError("only today, yesterday, or up to 7 days ahead are supported")
    if day > today + timedelta(days=7):
        raise ValueError("forecasts only reach 7 days ahead")


def _in_window(rows: list[dict], start: datetime, end: datetime) -> list[dict]:
    out = []
    for r in rows:
        t = datetime.fromisoformat(r["time"])
        if t.tzinfo is None:
            t = t.replace(tzinfo=config.TZ)
        if start <= t <= end:
            out.append(r)
    return out


def _every(rows: list[dict], hours: int) -> list[dict]:
    return [r for i, r in enumerate(rows) if i % hours == 0]


def gather(day: date, start_hour: int, end_hour: int, points: list[str], now: datetime | None = None) -> dict:
    now = now or datetime.now(config.TZ)
    today = now.date()
    validate_day(day, today)
    start, end = window_bounds(day, start_hour, end_hour)
    sources: list[dict] = []
    cond: dict = {
        "date": day.isoformat(),
        "weekday": day.strftime("%A"),
        "window": {"start": start.strftime("%H:%M"), "end": end.strftime("%H:%M") if end_hour < 24 else "24:00"},
        "generated_at": now.isoformat(timespec="minutes"),
        "is_today": day == today,
        "hours_until_window": round((start - now).total_seconds() / 3600, 1),
        "buoys": {},
        "forecast": {},
        "tide": None,
        "sources": sources,
    }

    # Buoys: only meaningful for today (observations of what's in the water now).
    if day == today:
        for sid, meta in config.BUOYS.items():
            try:
                cond["buoys"][sid] = {"name": meta["name"], **ndbc.fetch_station(sid, meta["spec"])}
                sources.append({"name": f"NDBC {sid} ({meta['name']})", "status": "ok"})
            except FetchError as e:
                sources.append({"name": f"NDBC {sid} ({meta['name']})", "status": "error", "detail": str(e)})
    else:
        sources.append({"name": "NDBC buoys", "status": "skipped", "detail": "not today; forecast only"})

    for pid in points:
        p = config.FORECAST_POINTS[pid]
        entry: dict = {"name": p["name"], "lat": p["lat"], "lon": p["lon"]}
        try:
            marine = openmeteo.fetch_marine(p["lat"], p["lon"], day)
            entry["window_hours"] = _in_window(marine, start, end)
            entry["day_every_3h"] = _every(marine, 3)
            sources.append({"name": f"Open-Meteo marine: {p['name']}", "status": "ok"})
        except FetchError as e:
            sources.append({"name": f"Open-Meteo marine: {p['name']}", "status": "error", "detail": str(e)})
        try:
            wind = openmeteo.fetch_wind(p["lat"], p["lon"], day)
            entry["wind_window_hours"] = _in_window(wind, start, end)
            entry["wind_day_every_3h"] = _every(wind, 3)
            sources.append({"name": f"Open-Meteo wind: {p['name']}", "status": "ok"})
        except FetchError as e:
            sources.append({"name": f"Open-Meteo wind: {p['name']}", "status": "error", "detail": str(e)})
        cond["forecast"][pid] = entry

    try:
        t = tides.fetch_day(day)
        cond["tide"] = {
            "station": t["station"],
            "extremes": t["extremes"],
            "window_hours": _in_window(t["hourly"], start, end),
        }
        sources.append({"name": f"NOAA tides {config.TIDE_STATION} (Santa Cruz)", "status": "ok"})
    except FetchError as e:
        sources.append({"name": f"NOAA tides {config.TIDE_STATION} (Santa Cruz)", "status": "error", "detail": str(e)})

    cond["data_timestamp"] = _data_timestamp(cond)
    return cond


def _data_timestamp(cond: dict) -> str:
    """Changes when the underlying data changes; used in the result cache key."""
    stamps = []
    for b in cond["buoys"].values():
        if b.get("latest"):
            stamps.append(b["latest"]["time"])
    # Forecast models update ~hourly; bucket by hour.
    stamps.append(cond["generated_at"][:13])
    return "|".join(stamps)


def usable(cond: dict) -> bool:
    """Need at least one swell source to say anything."""
    has_forecast = any(v.get("window_hours") for v in cond["forecast"].values())
    has_buoy = any(b.get("latest") for b in cond["buoys"].values())
    return has_forecast or has_buoy
