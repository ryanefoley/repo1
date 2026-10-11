# What's Breaking

Spot-by-spot surf calls for Santa Cruz County, with the reasoning: which swell reaches which break, and why the others stay flat. It pulls buoy, forecast, wind and tide data, runs a quick deterministic pre-pass against a hand-written spot knowledge base, then asks Claude Opus 5.5 (high effort) to make the call.

The default view is Steamer Lane section by section (Indicators, Middle Peak, the Point, the Slot and its second peak, Cowell's). Flip to **Whole county** for about 25 breaks from Waddell to Moss Landing.

See [PLAN.md](PLAN.md) for the design.

## Setup

You need Python 3.11+, Node 18+, and an Anthropic API key.

```bash
cd surf-break-analyzer
cp .env.example .env           # then put your key in .env

# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# frontend
cd ../frontend
npm install
```

## Run it

**Command line** (fastest way to try it and to tune the spot notes):

```bash
cd backend
python cli.py                                   # today, next two hours, Lane sections
python cli.py --date today --window 16-17       # today 4-5pm
python cli.py --date sat --window dawn --scope county
python cli.py --spots lane-point,pleasure-point --window 7-9
python cli.py --dry-run                         # data + pre-pass only, no API call, free
python cli.py spots                             # list spot ids
```

**Web app:**

```bash
# terminal 1
cd backend && uvicorn surfbreak.main:app --reload
# terminal 2
cd frontend && npm run dev
```

Open the URL Vite prints. It listens on your network too, so your phone on the same wifi can use the "Network" URL.

To serve everything from one process instead, run `npm run build` once in `frontend/`, then just `uvicorn surfbreak.main:app --host 0.0.0.0` from `backend/` and open port 8000.

## What a run costs

One request covers all the spots you asked for, so the model can compare them. The system prompt and spot notes are prompt-cached. Expect roughly 10-30k tokens in and 5-15k out (thinking included), about $0.10-0.40 per Lane run on Opus 5.5 at high effort; county runs are larger. An identical request (same day, window, spots and data) within 45 minutes reuses the saved answer for free. Every run prints its token count and cost.

High effort takes a while: usually one to three minutes. The web app shows the data and dials right away and fills in the calls when the model finishes.

## Teaching it your breaks

`backend/spots.yaml` is where most of the accuracy comes from. Each spot has a swell window (best arc, wrap-only arc, the minimum period needed to wrap), size range, tide and wind preferences, and free-text `local_notes`. Your notes outrank general knowledge in the prompt.

Most entries start at `confidence: low` because they're from general knowledge. When you've checked one in the water, fix it and raise the confidence. Two open questions are already marked `TBD — Ryan` (the Slot's tide behavior).

Use `python cli.py --dry-run` after editing to see how the pre-pass reads each spot without paying for a model call.

## Checking its accuracy

After a session, log what actually broke, either in the app (open a spot, then **Log what you saw here**) or from the command line:

```bash
python cli.py log --spot lane-slot-second-peak --breaking no --size 0 --window 16-18 --notes "all on the main peak"
python cli.py scorecard
```

The scorecard pairs each report with the prediction that covered it and shows accuracy by spot and by swell type (direction plus period band), so you can see things like "Slot second-peak calls are wrong on 13-15 s SW".

After changing `spots.yaml` or the prompt, rerun all the past days you have ground truth for and compare:

```bash
python regression.py          # shows how many and the rough cost
python regression.py --yes
```

Predictions and session logs live in `data/`, which is gitignored.

## Data sources

All free, no keys:

| What | Source |
|---|---|
| Swell in the water now (today only) | NDBC 46042 Monterey, with the swell / wind-wave split from its `.spec` file; NDBC 46236 Monterey Canyon Outer; NDBC 46012 Half Moon Bay |
| Swell partitions by hour (any day up to 7 out) | Open-Meteo Marine (primary, secondary, tertiary swell and wind waves) |
| Wind by hour | Open-Meteo, at three points: North Coast, Santa Cruz, South County |
| Tides | NOAA CO-OPS 9413745 Santa Cruz (hi/lo, interpolated hourly) |

If a source is down, the run continues with what it has and says which source failed.

## Tests

```bash
cd backend && python -m pytest
```

The tests run against recorded-style data for 11 Oct 2026 (13-15 ft @ 11 s NW, small S underneath) and a fake model, so they need no network or API key.
