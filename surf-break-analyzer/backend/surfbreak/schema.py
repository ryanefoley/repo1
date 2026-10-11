"""Output schema: sent to the API as a structured-output JSON schema and used to validate."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SpotCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    breaking: Literal["yes", "marginal", "no"]
    size_ft_low: float
    size_ft_high: float
    quality: int  # 1-5
    best_time: str
    why: str
    key_inputs: list[str]
    confidence: Literal["low", "medium", "high"]


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    swell_read: str
    wind_tide_read: str
    best_call: str
    spots: list[SpotCall]
    caveats: list[str]


# Hand-written so it stays inside the structured-output subset
# (no min/max, additionalProperties false everywhere).
JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "swell_read", "wind_tide_read", "best_call", "spots", "caveats"],
    "properties": {
        "summary": {"type": "string", "description": "One or two sentences: the day in a nutshell."},
        "swell_read": {"type": "string", "description": "What's actually in the water: each swell partition, which ones matter, any buried component."},
        "wind_tide_read": {"type": "string", "description": "Wind and tide through the window and how they shift things."},
        "best_call": {"type": "string", "description": "Where to paddle out in the window and why, in one or two sentences."},
        "spots": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "breaking", "size_ft_low", "size_ft_high", "quality", "best_time", "why", "key_inputs", "confidence"],
                "properties": {
                    "id": {"type": "string", "description": "Spot id exactly as given."},
                    "breaking": {"type": "string", "enum": ["yes", "marginal", "no"]},
                    "size_ft_low": {"type": "number", "description": "Face height, feet. 0 if flat."},
                    "size_ft_high": {"type": "number", "description": "Face height on sets, feet."},
                    "quality": {"type": "integer", "description": "1 = poor/flat, 2 = fair, 3 = good, 4 = very good, 5 = epic."},
                    "best_time": {"type": "string", "description": "Best part of the requested window, e.g. '16:00-17:00', or 'none'."},
                    "why": {"type": "string", "description": "2-4 sentences explaining the call from swell angle/period, refraction, wind and tide."},
                    "key_inputs": {"type": "array", "items": {"type": "string"}, "description": "The 2-4 numbers that drove the call."},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                },
            },
        },
        "caveats": {"type": "array", "items": {"type": "string"}},
    },
}
