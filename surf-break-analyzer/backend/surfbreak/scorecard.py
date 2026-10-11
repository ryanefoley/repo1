"""Compare logged sessions with the predictions made for them."""
from __future__ import annotations

from collections import defaultdict

from .units import deg_to_compass

COMPASS8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _compass8(deg: float | None) -> str:
    if deg is None:
        return "?"
    return COMPASS8[int(((deg % 360) + 22.5) // 45) % 8]


def _period_band(p: float | None) -> str:
    if p is None:
        return "?"
    return "<10s" if p < 10 else "10-13s" if p < 14 else "14s+"


def _overlaps(pred_req: dict, sess: dict) -> bool:
    if sess.get("start_hour") is None or sess.get("end_hour") is None:
        return True
    return pred_req["start_hour"] < sess["end_hour"] and sess["start_hour"] < pred_req["end_hour"]


def match(sessions: list[dict], predictions: list[dict]) -> list[dict]:
    """Pair each session report with the prediction that covered it."""
    by_id = {p["prediction_id"]: p for p in predictions if "prediction_id" in p}
    pairs = []
    for s in sessions:
        pred = by_id.get(s.get("prediction_id") or "")
        if pred is None:
            candidates = [
                p for p in predictions
                if p["request"]["date"] == s["date"]
                and s["spot_id"] in p["request"]["spot_ids"]
                and _overlaps(p["request"], s)
            ]
            pred = max(candidates, key=lambda p: p.get("saved_at", ""), default=None)
        if pred is None:
            continue
        call = next((c for c in pred["analysis"]["spots"] if c["id"] == s["spot_id"]), None)
        feat = next((f for f in pred["features"] if f["id"] == s["spot_id"]), {})
        if call is None:
            continue
        parts = feat.get("observed_partitions") or feat.get("forecast_partitions") or []
        primary = max(parts, key=lambda p: p["height_ft"], default={})
        pairs.append({"session": s, "prediction_id": pred["prediction_id"], "call": call,
                      "primary": primary})
    return pairs


def score(pairs: list[dict]) -> dict:
    def blank():
        return {"n": 0, "breaking_exact": 0, "breaking_binary": 0, "size_n": 0, "size_abs_err": 0.0}

    overall = blank()
    by_spot: dict = defaultdict(blank)
    by_bucket: dict = defaultdict(blank)
    misses = []
    for pr in pairs:
        s, c, prim = pr["session"], pr["call"], pr["primary"]
        bucket = f"{_compass8(prim.get('dir_deg'))} {_period_band(prim.get('period_s'))}"
        exact = s["breaking"] == c["breaking"]
        binary = (s["breaking"] == "no") == (c["breaking"] == "no")
        for agg in (overall, by_spot[s["spot_id"]], by_bucket[bucket]):
            agg["n"] += 1
            agg["breaking_exact"] += exact
            agg["breaking_binary"] += binary
            if s.get("size_ft") is not None:
                mid = (c["size_ft_low"] + c["size_ft_high"]) / 2
                agg["size_n"] += 1
                agg["size_abs_err"] += abs(s["size_ft"] - mid)
        if not exact:
            misses.append({
                "date": s["date"], "spot_id": s["spot_id"], "observed": s["breaking"],
                "predicted": c["breaking"], "bucket": bucket,
                "primary": f"{prim.get('height_ft')}ft {prim.get('period_s')}s {deg_to_compass(prim.get('dir_deg'))}" if prim else None,
                "notes": s.get("notes", ""), "prediction_id": pr["prediction_id"],
            })

    def finish(a):
        n = a["n"] or 1
        return {
            "n": a["n"],
            "breaking_exact_acc": round(a["breaking_exact"] / n, 3),
            "breaking_yes_no_acc": round(a["breaking_binary"] / n, 3),
            "size_mae_ft": round(a["size_abs_err"] / a["size_n"], 2) if a["size_n"] else None,
        }

    return {
        "overall": finish(overall),
        "by_spot": {k: finish(v) for k, v in sorted(by_spot.items())},
        "by_swell_bucket": {k: finish(v) for k, v in sorted(by_bucket.items())},
        "misses": misses,
    }
