"""Parse friendly dates and windows: 'today', 'tomorrow', 'sat', '2026-10-17', '16-17', 'dawn'."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from . import config

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
NAMED_WINDOWS = {"dawn": (6, 9), "morning": (7, 11), "midday": (11, 14), "afternoon": (14, 18), "evening": (16, 19)}


def parse_date(s: str, today: date | None = None) -> date:
    today = today or datetime.now(config.TZ).date()
    s = s.strip().lower()
    if s in ("today", ""):
        return today
    if s == "tomorrow":
        return today + timedelta(days=1)
    if s == "yesterday":
        return today - timedelta(days=1)
    if s[:3] in WEEKDAYS and s.isalpha():
        delta = (WEEKDAYS.index(s[:3]) - today.weekday()) % 7
        return today + timedelta(days=delta)
    return date.fromisoformat(s)


def parse_window(s: str) -> tuple[int, int]:
    s = s.strip().lower()
    if s in NAMED_WINDOWS:
        return NAMED_WINDOWS[s]
    lo, _, hi = s.partition("-")
    start, end = int(lo), int(hi) if hi else int(lo) + 1
    if not (0 <= start < end <= 24):
        raise ValueError("window must look like 16-17 (24h clock)")
    return start, end
