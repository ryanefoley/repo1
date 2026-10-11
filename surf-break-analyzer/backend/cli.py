#!/usr/bin/env python3
"""Command line for the surf break analyzer.

  python cli.py                                   # today, next couple of hours, Lane sections
  python cli.py --date today --window 16-17       # today 4-5pm
  python cli.py --date sat --window dawn --scope county
  python cli.py --spots lane-point,pleasure-point --window 7-9
  python cli.py --dry-run                         # fetch + pre-pass + prompt, no API call
  python cli.py log --spot lane-slot-second-peak --breaking no --size 0 --notes "all on main peak"
  python cli.py scorecard
  python cli.py spots
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from datetime import datetime

from surfbreak import analyze, config, dates, scorecard, spots, store
from surfbreak.conditions import usable


def _default_window() -> str:
    h = datetime.now(config.TZ).hour
    h = min(max(h, 5), 21)
    return f"{h}-{h + 2}"


def _wrap(s: str, indent: str = "    ") -> str:
    return textwrap.fill(s, width=88, initial_indent=indent, subsequent_indent=indent)


def print_result(res: dict) -> None:
    req = res["request"]
    cond = res["conditions"]
    print(f"\n{cond['weekday']} {req['date']}  {cond['window']['start']}-{cond['window']['end']}  ({req['scope']})")
    for s in cond["sources"]:
        if s["status"] != "ok":
            print(f"  ! {s['name']}: {s['status']} {s.get('detail', '')}")
    if res.get("dry_run"):
        print("\nDry run — pre-pass features:\n")
        def pstr(parts):
            return "; ".join(
                f"{p['height_ft']}ft {p['period_s']:g}s {p['dir_compass']}({p['dir_deg']:g}) {p['window_position']}"
                f"{'' if p['wraps_in'] else ' no-wrap'}"
                for p in parts
            ) or "none"

        for f in res["features"]:
            wind = f.get("wind") or {}
            tide = f.get("tide") or {}
            print(f"  {f['name']}:")
            if f.get("observed_partitions"):
                print(f"      buoy now   naive {f['naive_face_ft_observed']} ft | {pstr(f['observed_partitions'])}")
            print(f"      forecast   naive {f['naive_face_ft_forecast']} ft | {pstr(f['forecast_partitions'])}")
            if wind:
                print(f"      wind       {wind['avg_kt']}kt {wind['from_compass']} ({wind['relative_to_break']})", end="")
            if tide:
                print(f" | tide {tide['range_ft']} {tide['state']} {tide['bands']} pref {tide['spot_prefers']}", end="")
            print()
        print(f"\nPrompt: system {sum(len(b['text']) for b in res['prompt']['system'])} chars, "
              f"user {len(res['prompt']['user'])} chars.")
        return

    a = res["analysis"]
    print("\n" + _wrap(a["summary"], ""))
    print("\nSwell:  " + a["swell_read"])
    print("Wind/tide:  " + a["wind_tide_read"])
    print("Best call:  " + a["best_call"] + "\n")
    names = {m["id"]: m["name"] for m in res["spots_meta"]}
    icon = {"yes": "●", "marginal": "◐", "no": "○"}
    for c in a["spots"]:
        size = "flat" if c["size_ft_high"] == 0 else f"{c['size_ft_low']:g}-{c['size_ft_high']:g} ft"
        print(f"{icon[c['breaking']]} {names.get(c['id'], c['id'])}: {c['breaking']}, {size}, "
              f"quality {c['quality']}/5, best {c['best_time']} ({c['confidence']} confidence)")
        print(_wrap(c["why"]))
        print(_wrap("inputs: " + "; ".join(c["key_inputs"])))
    if a["caveats"]:
        print("\nCaveats:")
        for cv in a["caveats"]:
            print(_wrap("- " + cv, "  "))
    for w in res.get("warnings", []):
        print(f"  ! {w}")
    u = res["usage"]
    tag = " (cached result)" if res.get("cached") else ""
    print(f"\n{u['model']} / {u['effort']}: {u['input_tokens']} in + {u['cache_read_input_tokens']} cached "
          f"+ {u['output_tokens']} out, {u['seconds']}s, ~${u['cost_usd']:.2f}{tag}")
    if res.get("prediction_id"):
        print(f"Saved as {res['prediction_id']}")


def cmd_analyze(args) -> int:
    day = dates.parse_date(args.date)
    start, end = dates.parse_window(args.window or _default_window())
    ids = [s.strip() for s in args.spots.split(",")] if args.spots else None
    try:
        res = analyze.run(day, start, end, scope=args.scope, ids=ids, dry_run=args.dry_run,
                          use_cache=not args.no_cache)
    except (ValueError, analyze.AnalysisError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.json:
        res = {k: v for k, v in res.items() if not (k == "prompt" and not args.dry_run)}
        print(json.dumps(res, indent=1, default=str))
    else:
        print_result(res)
        if args.dry_run and not usable(res["conditions"]):
            print("\n(no swell data could be fetched — the real run would stop here)")
    return 0


def cmd_log(args) -> int:
    day = dates.parse_date(args.date).isoformat()
    start = end = None
    if args.window:
        start, end = dates.parse_window(args.window)
    spots.select(ids=[args.spot])  # validates the id
    rec = store.log_session(date=day, spot_id=args.spot, breaking=args.breaking, size_ft=args.size,
                            start_hour=start, end_hour=end, notes=args.notes or "", prediction_id=args.prediction)
    print(f"logged {rec['id']}: {rec['spot_id']} {rec['breaking']} {rec['size_ft']} ft on {rec['date']}")
    return 0


def cmd_scorecard(args) -> int:
    pairs = scorecard.match(store.list_sessions(), store.list_predictions())
    if not pairs:
        print("No session reports matched to predictions yet. Log one with `python cli.py log ...`.")
        return 0
    sc = scorecard.score(pairs)
    if args.json:
        print(json.dumps(sc, indent=1))
        return 0

    def line(label, m):
        size = f"size MAE {m['size_mae_ft']} ft" if m["size_mae_ft"] is not None else "no sizes logged"
        print(f"  {label:<34} n={m['n']:<3} exact {m['breaking_exact_acc']:.0%}  yes/no {m['breaking_yes_no_acc']:.0%}  {size}")

    print("\nOverall")
    line("all", sc["overall"])
    print("\nBy spot")
    for k, m in sc["by_spot"].items():
        line(k, m)
    print("\nBy primary swell (direction, period)")
    for k, m in sc["by_swell_bucket"].items():
        line(k, m)
    if sc["misses"]:
        print("\nMisses")
        for m in sc["misses"]:
            print(f"  {m['date']} {m['spot_id']}: predicted {m['predicted']}, saw {m['observed']} [{m['primary']}] {m['notes']}")
    return 0


def cmd_spots(args) -> int:
    for s in spots.load():
        flag = "*" if s.get("default") else " "
        print(f" {flag} {s['id']:<24} {s['name']:<34} {s['region']:<13} confidence {s['confidence']}")
    print("\n * = in the default (Lane) view")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="What's breaking in Santa Cruz County, and why.")
    sub = p.add_subparsers(dest="cmd")

    def add_analyze_args(ap):
        ap.add_argument("--date", default="today", help="today, tomorrow, sat, or YYYY-MM-DD")
        ap.add_argument("--window", help="hours like 16-17, or dawn/morning/midday/afternoon/evening")
        ap.add_argument("--scope", default="lane", choices=["lane", "county"])
        ap.add_argument("--spots", help="comma-separated spot ids (overrides --scope)")
        ap.add_argument("--dry-run", action="store_true", help="fetch data and build the prompt; don't call the API")
        ap.add_argument("--no-cache", action="store_true")
        ap.add_argument("--json", action="store_true")

    add_analyze_args(p)
    add_analyze_args(sub.add_parser("analyze", help="run the analysis (default)"))

    lp = sub.add_parser("log", help="log what actually broke")
    lp.add_argument("--spot", required=True)
    lp.add_argument("--breaking", required=True, choices=list(store.BREAKING))
    lp.add_argument("--size", type=float, help="face height in feet")
    lp.add_argument("--date", default="today")
    lp.add_argument("--window", help="hours you surfed, e.g. 16-18")
    lp.add_argument("--notes")
    lp.add_argument("--prediction", help="prediction id to score against (default: best match)")

    sp = sub.add_parser("scorecard", help="accuracy of past predictions vs your session logs")
    sp.add_argument("--json", action="store_true")
    sub.add_parser("spots", help="list spot ids")

    args = p.parse_args(argv)
    return {"log": cmd_log, "scorecard": cmd_scorecard, "spots": cmd_spots}.get(args.cmd, cmd_analyze)(args)


if __name__ == "__main__":
    sys.exit(main())
