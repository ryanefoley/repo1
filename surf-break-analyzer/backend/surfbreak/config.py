"""Central settings: locations, station IDs, model settings, prices."""
from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

try:  # load ../.env (ANTHROPIC_API_KEY etc.) if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

TZ = ZoneInfo("America/Los_Angeles")

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
SPOTS_FILE = BACKEND_DIR / "spots.yaml"
DATA_DIR = Path(os.environ.get("SURFBREAK_DATA_DIR", PROJECT_DIR / "data"))
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

# --- Buoys (NDBC) -----------------------------------------------------------
# 46042: Monterey, 27 nm WNW of Monterey (deep water, offshore swell).
#        Its .spec file splits swell vs wind-wave, which is how a small S swell
#        buried under NW windswell becomes visible.
# 46236: Monterey Canyon Outer (Scripps/CDIP Waverider, closer to the bay).
# 46012: Half Moon Bay (cross-check for the North Coast).
BUOYS = {
    "46042": {"name": "Monterey (offshore)", "spec": True},
    "46236": {"name": "Monterey Canyon Outer", "spec": False},
    "46012": {"name": "Half Moon Bay", "spec": True},
}

# --- Forecast points (Open-Meteo) -------------------------------------------
# Spots point at one of these; each gets its own swell + wind forecast.
FORECAST_POINTS = {
    "north_coast": {"name": "North Coast (off Davenport)", "lat": 37.00, "lon": -122.24},
    "santa_cruz": {"name": "Santa Cruz (off the Lane / Eastside)", "lat": 36.93, "lon": -122.02},
    "south_county": {"name": "South County (off Manresa)", "lat": 36.92, "lon": -121.88},
}

# --- Tides (NOAA CO-OPS) ----------------------------------------------------
# 9413745 = Santa Cruz, Monterey Bay (subordinate station; hi/lo predictions only).
TIDE_STATION = "9413745"

# --- Model ------------------------------------------------------------------
MODEL = os.environ.get("SURFBREAK_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("SURFBREAK_EFFORT", "high")
MAX_TOKENS = int(os.environ.get("SURFBREAK_MAX_TOKENS", "32000"))

# USD per million tokens, Claude Opus 5.5 (platform.claude.com pricing, Oct 2026).
PRICES = {
    "input": 4.00,
    "output": 20.00,
    "cache_write_5m": 5.00,
    "cache_read": 0.20,
}

# Results cache
RESULT_TTL_SECONDS = int(os.environ.get("SURFBREAK_RESULT_TTL", str(45 * 60)))
FETCH_TTL_SECONDS = int(os.environ.get("SURFBREAK_FETCH_TTL", str(30 * 60)))

HTTP_TIMEOUT = 20.0
USER_AGENT = "surf-break-analyzer/0.1 (personal project)"
