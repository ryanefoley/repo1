"""Prompt assembly + the Opus call + validation + result caching."""
from __future__ import annotations

import json
import time
from datetime import date

from pydantic import ValidationError

from . import conditions as conditions_mod
from . import config, features, spots as spots_mod
from .schema import JSON_SCHEMA, Analysis

SYSTEM_PROMPT = """\
You are an experienced Santa Cruz surf forecaster explaining to a strong local surfer \
what will actually be breaking at specific spots during a specific time window, and why.

The surfer knows these breaks. What they want is the reasoning: which swell partition \
reaches which spot, and why other spots stay flat or close out. Explain it the way a \
local would, e.g. "11 s from 315° doesn't bend far enough to reach the bight, so the \
Point takes it all and the Slot's second peak never forms."

## How to reason

1. Read the swell first, partition by partition. The combined wave height and mean \
direction can hide a small long-period S swell under a big short-period NW windswell. \
Use the buoy spectral split (observed, today only) and the forecast partitions. If they \
disagree, say so and trust the buoy for "right now" and the forecast for later hours.
2. For each spot, judge each partition against that spot's swell window:
   - Direction inside the best arc → direct exposure.
   - Inside the ok arc but outside best → it has to refract/wrap. Wrapping costs size, \
and short-period swell barely wraps at all. Compare the period with the spot's \
wrap_min_period_s.
   - Outside the window → effectively blocked (headland, Monterey Peninsula shadow, \
facing the wrong way).
   - Longer period = feels the bottom sooner, refracts more, carries more energy; on \
reefs it also breaks bigger than the offshore height suggests.
   - Monterey Bay geometry: the North Coast faces SW/W and takes NW head-on. Town and \
Eastside spots sit in the lee of Lighthouse Point and Pleasure Point and face S, so \
NW must wrap and S swell comes straight in. South County beaches face W into the bay \
mouth and take W/NW, but S is shadowed by the Monterey Peninsula. The Monterey Canyon \
head focuses W/NW energy near Moss Landing.
3. Wind: use the relation to each break (offshore, cross-offshore, cross-shore, \
cross-onshore, onshore) and the speed. NW wind is side-offshore at the Lane and the \
Eastside, cross/onshore on the North Coast and South County, and typically builds \
through the afternoon.
4. Tide: compare the window's tide band with the spot's preference, and note whether \
it's rising or falling.
5. Sub-peaks: for spots with a parent (e.g. Steamer Lane sections), explain how energy \
is split between sections. A section can be flat while its neighbor is pumping.

## Inputs you'll get

- `conditions`: buoys (today only), forecast swell partitions and wind per forecast \
point (for the window's hours and the whole day every 3 h), and tides. Heights are \
offshore significant heights in feet, not face heights. Periods are in seconds. \
Directions are degrees true that swell/wind come FROM.
- `features`: a deterministic pre-pass per spot: each partition's position in the \
spot's window, whether it wraps, wind relative to the break, and tide band. \
`naive_face_ft_*` is a crude heuristic, so use it as a sanity check, not an answer.
- The spot knowledge base below. Each entry has a `confidence`. `local_notes` from the \
surfer (Ryan) are first-hand observations and outrank general knowledge. When an entry \
is low-confidence and the physics clearly disagrees, say so in `why`.

## Output rules

- Return exactly one entry per requested spot id, in the order given.
- Sizes are face heights in feet. Use 0 and 0 when flat.
- `why` is 2-4 sentences of plain-language physics for that spot. Don't list \
step-by-step reasoning.
- `key_inputs` are the 2-4 specific numbers behind the call (e.g. "primary 11 s @ 315°", \
"wind NW 12 kt, side-offshore", "tide 3.1 ft rising").
- Be honest about uncertainty: missing data, stale buoy spectra, forecasts more than \
two days out, sand-dependent spots. Put these in `caveats` and lower `confidence`.
- Don't invent data you weren't given.
"""


def _spot_kb_text() -> str:
    with open(config.SPOTS_FILE) as f:
        return f.read()


def build_system() -> list[dict]:
    # One stable prefix for every request (both scopes), so prompt caching hits.
    return [
        {"type": "text", "text": SYSTEM_PROMPT},
        {
            "type": "text",
            "text": "## Spot knowledge base (spots.yaml)\n\n" + _spot_kb_text(),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _trim_conditions(cond: dict) -> dict:
    """Drop bookkeeping fields the model doesn't need."""
    c = json.loads(json.dumps(cond))
    for b in c.get("buoys", {}).values():
        b.pop("latest_wind", None)
    return c


def build_user_message(cond: dict, feats: list[dict], spot_list: list[dict]) -> str:
    payload = {
        "request": {
            "date": cond["date"],
            "weekday": cond["weekday"],
            "window": cond["window"],
            "is_today": cond["is_today"],
            "hours_until_window": cond["hours_until_window"],
            "spot_ids_in_order": [s["id"] for s in spot_list],
        },
        "conditions": _trim_conditions(cond),
        "features": feats,
    }
    return (
        "Analyze what will be breaking at each requested spot during the window.\n\n"
        + json.dumps(payload, indent=1, default=str)
    )


def cost_usd(usage: dict) -> float:
    p = config.PRICES
    return round(
        (
            usage.get("input_tokens", 0) * p["input"]
            + usage.get("output_tokens", 0) * p["output"]
            + usage.get("cache_creation_input_tokens", 0) * p["cache_write_5m"]
            + usage.get("cache_read_input_tokens", 0) * p["cache_read"]
        ) / 1_000_000,
        4,
    )


class AnalysisError(Exception):
    pass


def call_model(system: list[dict], user: str, client=None) -> tuple[Analysis, dict]:
    if client is None:
        import os

        import anthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise AnalysisError("ANTHROPIC_API_KEY isn't set. Add it to surf-break-analyzer/.env and restart.")

        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    t0 = time.time()
    # Stream: high effort with adaptive thinking can run for minutes.
    with client.messages.stream(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={
            "effort": config.EFFORT,
            "format": {"type": "json_schema", "schema": JSON_SCHEMA},
        },
    ) as stream:
        msg = stream.get_final_message()
    elapsed = round(time.time() - t0, 1)

    if msg.stop_reason == "refusal":
        raise AnalysisError("model refused the request")
    if msg.stop_reason == "max_tokens":
        raise AnalysisError("ran out of tokens; raise SURFBREAK_MAX_TOKENS")
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    try:
        analysis = Analysis.model_validate(json.loads(text))
    except (ValueError, ValidationError) as e:
        raise AnalysisError(f"model output didn't match the schema: {e}") from e

    u = msg.usage
    usage = {
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
    }
    usage["cost_usd"] = cost_usd(usage)
    usage["seconds"] = elapsed
    usage["model"] = config.MODEL
    usage["effort"] = config.EFFORT
    return analysis, usage


def _reconcile(analysis: Analysis, spot_list: list[dict]) -> list[str]:
    """Make sure every requested spot is present and in order; return warnings."""
    wanted = [s["id"] for s in spot_list]
    got = {c.id: c for c in analysis.spots}
    warnings = []
    extra = set(got) - set(wanted)
    if extra:
        warnings.append(f"model returned unknown spot ids, dropped: {sorted(extra)}")
    missing = [i for i in wanted if i not in got]
    if missing:
        warnings.append(f"model skipped: {missing}")
    analysis.spots = [got[i] for i in wanted if i in got]
    return warnings


def rerun_saved(prediction: dict, client=None) -> dict:
    """Re-analyze a saved prediction's inputs with the *current* prompt and spots.yaml.

    Used by the regression check: same data in, did the calls get better?
    """
    spot_list = spots_mod.select(ids=prediction["request"]["spot_ids"])
    cond = prediction["conditions"]
    feats = features.build(spot_list, cond)
    analysis, usage = call_model(build_system(), build_user_message(cond, feats, spot_list), client=client)
    warnings = _reconcile(analysis, spot_list)
    return {**{k: prediction[k] for k in ("request", "conditions", "prediction_id")},
            "features": feats, "analysis": analysis.model_dump(), "usage": usage, "warnings": warnings}


_result_cache: dict[tuple, tuple[float, dict]] = {}


def run(day: date, start_hour: int, end_hour: int, scope: str = "lane", ids: list[str] | None = None,
        dry_run: bool = False, client=None, use_cache: bool = True, now=None) -> dict:
    spot_list = spots_mod.select(scope, ids)
    cond = conditions_mod.gather(day, start_hour, end_hour, spots_mod.forecast_points(spot_list), now=now)
    feats = features.build(spot_list, cond)
    system = build_system()
    user = build_user_message(cond, feats, spot_list)

    base = {
        "request": {"date": day.isoformat(), "start_hour": start_hour, "end_hour": end_hour,
                    "scope": "custom" if ids else scope, "spot_ids": [s["id"] for s in spot_list]},
        "spots_meta": [
            {"id": s["id"], "name": s["name"], "region": s["region"], "parent": s.get("parent"),
             "kb_confidence": s["confidence"], "faces_deg": s["faces_deg"],
             "swell_window": s["swell_window"], "size_range_ft": s["size_range_ft"]}
            for s in spot_list
        ],
        "conditions": cond,
        "features": feats,
    }
    if dry_run:
        return {**base, "dry_run": True, "prompt": {"system": system, "user": user}}

    if not conditions_mod.usable(cond):
        raise AnalysisError("no swell data available (all buoy and forecast fetches failed)")

    key = (day.isoformat(), start_hour, end_hour, tuple(s["id"] for s in spot_list), cond["data_timestamp"])
    hit = _result_cache.get(key)
    if use_cache and hit and time.time() - hit[0] < config.RESULT_TTL_SECONDS:
        return {**hit[1], "cached": True}

    analysis, usage = call_model(system, user, client=client)
    warnings = _reconcile(analysis, spot_list)
    result = {**base, "analysis": analysis.model_dump(), "usage": usage, "warnings": warnings, "cached": False}
    _result_cache[key] = (time.time(), result)

    from . import store

    result["prediction_id"] = store.save_prediction(result)
    return result
