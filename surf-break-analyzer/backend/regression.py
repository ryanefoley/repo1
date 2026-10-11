#!/usr/bin/env python3
"""Regression check: rerun every past prediction you've logged sessions against,
using the *current* prompt and spots.yaml, and compare accuracy with the original calls.

Run this after editing spots.yaml or the system prompt:

  python regression.py            # shows what it would run and the rough cost
  python regression.py --yes      # actually calls the model
"""
from __future__ import annotations

import argparse
import sys

from surfbreak import analyze, scorecard, store


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="make the API calls")
    ap.add_argument("--limit", type=int, default=20, help="max predictions to rerun")
    args = ap.parse_args(argv)

    sessions = store.list_sessions()
    predictions = store.list_predictions()
    before = scorecard.match(sessions, predictions)
    if not before:
        print("No logged sessions matched to predictions yet; nothing to regress against.")
        return 0

    used = list(dict.fromkeys(p["prediction_id"] for p in before))[: args.limit]
    by_id = {p["prediction_id"]: p for p in predictions}
    est = sum(by_id[i].get("usage", {}).get("cost_usd", 0.15) for i in used)
    print(f"{len(before)} session reports across {len(used)} saved predictions; rerunning costs about ${est:.2f}.")
    if not args.yes:
        print("Add --yes to run.")
        return 0

    rerun = []
    for i, pid in enumerate(used, 1):
        print(f"  [{i}/{len(used)}] {pid}", flush=True)
        try:
            rerun.append(analyze.rerun_saved(by_id[pid]))
        except analyze.AnalysisError as e:
            print(f"    failed: {e}")

    after = scorecard.match(sessions, rerun)
    old, new = scorecard.score([p for p in before if p["prediction_id"] in {r["prediction_id"] for r in rerun}]), scorecard.score(after)

    def row(label, o, n):
        def fmt(m):
            size = f"{m['size_mae_ft']} ft" if m["size_mae_ft"] is not None else "-"
            return f"yes/no {m['breaking_yes_no_acc']:.0%}, exact {m['breaking_exact_acc']:.0%}, size {size}"
        print(f"  {label:<28} before: {fmt(o)}  |  now: {fmt(n)}")

    print("\nOverall")
    row("all", old["overall"], new["overall"])
    print("\nBy spot")
    for k in sorted(set(old["by_spot"]) | set(new["by_spot"])):
        if k in old["by_spot"] and k in new["by_spot"]:
            row(k, old["by_spot"][k], new["by_spot"][k])
    if new["misses"]:
        print("\nStill wrong")
        for m in new["misses"]:
            print(f"  {m['date']} {m['spot_id']}: predicted {m['predicted']}, saw {m['observed']} [{m['primary']}] {m['notes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
