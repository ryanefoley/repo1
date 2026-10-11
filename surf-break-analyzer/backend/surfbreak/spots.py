"""Load and select spots from spots.yaml."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from . import config

REGION_ORDER = ["north_coast", "westside", "eastside", "south_county"]
REGION_NAMES = {
    "north_coast": "North Coast",
    "westside": "Westside / town",
    "eastside": "Eastside",
    "south_county": "South County",
}
REQUIRED = {"id", "name", "region", "forecast_point", "faces_deg", "swell_window", "size_range_ft", "tide", "wind", "confidence"}


@lru_cache(maxsize=4)
def load(path: Path = config.SPOTS_FILE) -> list[dict]:
    with open(path) as f:
        spots = yaml.safe_load(f)["spots"]
    seen = set()
    for s in spots:
        missing = REQUIRED - s.keys()
        if missing:
            raise ValueError(f"spot {s.get('id')} missing fields: {sorted(missing)}")
        if s["id"] in seen:
            raise ValueError(f"duplicate spot id {s['id']}")
        if s["region"] not in REGION_ORDER:
            raise ValueError(f"spot {s['id']} has unknown region {s['region']}")
        if s["forecast_point"] not in config.FORECAST_POINTS:
            raise ValueError(f"spot {s['id']} has unknown forecast_point {s['forecast_point']}")
        seen.add(s["id"])
    return spots


def select(scope: str = "lane", ids: list[str] | None = None) -> list[dict]:
    """scope: 'lane' (default set), 'county' (everything), or explicit ids."""
    spots = load()
    if ids:
        by_id = {s["id"]: s for s in spots}
        unknown = [i for i in ids if i not in by_id]
        if unknown:
            raise ValueError(f"unknown spot ids: {unknown}")
        chosen = [by_id[i] for i in ids]
    elif scope == "county":
        chosen = list(spots)
    elif scope == "lane":
        chosen = [s for s in spots if s.get("default")]
    else:
        raise ValueError("scope must be 'lane' or 'county'")
    return sorted(chosen, key=lambda s: (REGION_ORDER.index(s["region"]), spots.index(s)))


def forecast_points(spots: list[dict]) -> list[str]:
    return sorted({s["forecast_point"] for s in spots})
