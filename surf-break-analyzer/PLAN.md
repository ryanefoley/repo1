# Surf Break Analyzer — Plan

Answers "what will actually be breaking, where, and why" for a given day and time window in Santa Cruz County. It pulls buoy, forecast, tide and wind data, pairs it with a hand-written knowledge base about each spot, and asks Claude Opus 5.5 (high effort) to reason through it the way a local would. Example: "11 s NW → wraps poorly into the bight → Point only, Slot's second peak won't form."

---

## 1. Goals

- **Default view: Steamer Lane, section by section.** Covers Indicators, Middle Peak, The Point, The Slot (main peak and the S-swell second peak) and Cowell's. For each section it says whether it is breaking, the likely size, the quality, and *why*.
- **County view (toggle).** Same analysis for every named break in the county, grouped North Coast / Westside / Eastside / South County.
- **Any date and time window.** "Today 4–5pm", "Saturday dawn", up to about 7 days out.
- **Explain the physics.** Swell angle versus each spot's window, period and refraction, tide, wind. The goal is to learn the patterns, not only get a rating.
- **Show the inputs.** Every verdict lists the numbers it was based on, so a wrong call can be traced back to a data problem or a reasoning problem.

### Non-goals (v1)
- No user accounts, no crowd reports, no cam scraping.
- No secret or unnamed spots. Only breaks that are already publicly named.

---

## 2. Spots

### Default set (Steamer Lane sections)
| Section | Notes to encode |
|---|---|
| Indicators | Westernmost section, outside toward Lighthouse Field; needs a decent W/NW swell; long right |
| Middle Peak | Needs size or W angle; A-frame-ish |
| The Point | Most exposed to W/NW wrap at the lighthouse; works on the biggest range of swells |
| The Slot — main peak | Inside of the Point |
| The Slot — second peak | **Needs real S/SW angle**; on NW or mid-period swell everything breaks on the main peak (Ryan's own observation). Tide dependence: TBD from Ryan |
| Cowell's | Needs S or big W wrap; beginner zone |

### County set (toggle on)
North Coast (exposed, most NW energy, worst in NW wind):
- Waddell Creek, Scott Creek, Davenport (Davenport Landing), Four Mile, Three Mile, Natural Bridges

Westside / town:
- Mitchell's Cove, It's Beach, Steamer Lane sections (above), Cowell's

Eastside:
- San Lorenzo Rivermouth, Harbor mouth, 26th Ave, Sewer Peak, Pleasure Point (First Peak / Second Peak), The Hook, Privates (38th–41st), Capitola

South County (beach breaks, more exposed to W/NW, sensitive to sandbars):
- Seacliff / Rio Del Mar, Manresa, Sunset State Beach, Moss Landing *(technically just over the line in Monterey County; included because Ryan asked)*

> Ryan to review this list: add or remove breaks, and mark which ones he never wants shown.
>
> Built list (v1): North Coast — Waddell Creek, Scott Creek, Davenport Landing, Four Mile, Three Mile;
> Westside — Natural Bridges, Mitchell's Cove, It's Beach, the Lane sections, Cowell's;
> Eastside — Rivermouth, Harbor Mouth, 26th Ave, Sewer Peak, Pleasure Point, The Hook, Privates, Capitola;
> South County — Seacliff/Rio Del Mar, Manresa, Sunset State Beach, Moss Landing.

### Spot knowledge base — `spots.yaml`
This is where most of the value lives. One entry per spot or section:

```yaml
- id: lane-slot-second-peak
  name: The Slot (second peak)
  region: westside
  parent: steamer-lane
  lat: 36.9510
  lon: -122.0260          # approximate; refine
  faces_deg: 160          # direction the break opens to
  swell_window:
    best_dir_deg: [180, 215]
    ok_dir_deg: [165, 230]
    min_period_s: 14      # below this, NW won't wrap in
  size_range_ft: [3, 8]
  tide: {best: "mid", notes: "TBD — Ryan"}
  wind: {offshore_deg: [0, 45], tolerates: "light NW"}
  bottom: reef
  local_notes: >
    Only shows on true S/SW. On NW/mid-period swell sets all break on the main Slot peak.
  confidence: low         # how sure we are about this entry
```

Start with v1 entries from general knowledge. Ryan then corrects them with local knowledge, and those corrections matter most. The `confidence` field tells the model which entries to trust.

---

## 3. Data sources (all free, no API keys)

| Need | Source | Notes |
|---|---|---|
| Observed offshore swell (today) | NDBC 46042 Monterey — `realtime2/46042.txt` and `46042.spec` | `.spec` gives the swell / wind-wave split (SwH, SwP, SwD, WWH, WWP, WWD). The `.txt` alone hides a small S swell under NW windswell. |
| Second offshore buoy | NDBC 46012 (Half Moon Bay) | Cross-check direction for the North Coast |
| Nearshore / directional spectra | CDIP Monterey Bay buoy(s) via THREDDS | **Verify station IDs during build.** Spectra are the best way to see a buried S component. |
| Forecast swell partitions (future days) | Open-Meteo Marine API | Hourly primary / secondary swell height, period, direction and wind waves |
| Wind forecast | Open-Meteo forecast and/or NWS `api.weather.gov` gridpoint | Hourly speed and direction at the spot, not offshore |
| Tides | NOAA CO-OPS predictions, Monterey (station 9413450 — verify) | Highs and lows plus hourly heights |

Fetchers are plain functions that return normalized JSON and are cached about 30 minutes. If a source fails, the app says so and continues with less data; it doesn't fail the whole run.

---

## 4. Analysis pipeline

```
date + time window + spot set
        │
        ▼
1. Fetch: buoys (if today), forecast partitions, wind, tide  ──► conditions.json
        │
        ▼
2. Deterministic pre-pass (per spot)
   - angle of each swell partition vs the spot's window → in-window / marginal / blocked
   - period vs min_period_s
   - wind relative to offshore_deg
   - tide height in the window vs the spot's preference
   ──► features.json  (gives the model numbers to reason over, not to copy)
        │
        ▼
3. One Opus 5.5 call (high effort)
   system prompt: role + physics primer + output schema
   user content: conditions.json + features.json + spots.yaml (selected spots) + time window
        │
        ▼
4. Validate the JSON against the schema → render
```

### LLM call
- Model `claude-opus-5-5`, `output_config={"effort": "high"}`. Opus 5.5 always uses adaptive thinking, and thinking can't be disabled, so set a generous `max_tokens` (start around 32k) and **stream** the response so long calls don't time out.
- **Prompt caching** on the system prompt and the spot knowledge base. These are stable and the largest part of the input, so repeat runs get cheaper.
- **One call for all selected spots**, not one per spot. The model compares spots against each other ("Point over Slot today because…"), and that comparison is half the value.
- Output is a strict JSON schema (use the API's structured-output support if available, otherwise schema-in-prompt with validation and a retry):

```json
{
  "summary": "Big mid-period NW — Point is the call; bight spots mostly asleep.",
  "swell_read": "Dominant 13-15ft @ 11s NW (315°). Any S component is minor ...",
  "spots": [
    {
      "id": "lane-point",
      "breaking": "yes | marginal | no",
      "size_ft": [6, 10],
      "quality": 1,
      "best_time": "16:00-17:30",
      "why": "Directly exposed to NW wrap at the lighthouse ...",
      "key_inputs": ["primary 315° 11s", "wind NW 12kt", "tide 3.1ft rising"]
    }
  ],
  "caveats": ["Wind forecast diverges after 3pm"]
}
```

`quality` is on a 1–5 scale.

- API key comes from the `ANTHROPIC_API_KEY` environment variable only. **This repo is public:** `.env` goes in `.gitignore`, and the key never goes in code, configs or the frontend.

### Cost guardrails
- Cache results per (date, window, spot set, data timestamp) for 30–60 minutes.
- Show the token usage and estimated cost of each run in the UI footer.
- County mode is roughly 4× the input of the default set, so it is an opt-in toggle, not the default.

---

## 5. App shape

Matches Ryan's existing stack (React + Vite, as in The Lane Report) with a thin Python backend that holds the API key:

```
surf-break-analyzer/
  PLAN.md, README.md, .env.example
  backend/
    spots.yaml                 spot knowledge base
    cli.py                     analyze / log / scorecard / spots
    regression.py              rerun past days with the current prompt + spots
    surfbreak/
      fetchers/                ndbc.py, openmeteo.py, tides.py (+ cached http)
      conditions.py            gather everything for a date + window
      features.py              deterministic pre-pass
      analyze.py               prompt, Opus call, validation, result cache
      schema.py                structured-output schema
      store.py, scorecard.py   predictions, session logs, accuracy
      main.py                  FastAPI: /api/analyze, /api/sessions, /api/scorecard
    tests/
  frontend/                    React + Vite
    src/components/            Controls, Dial, SpotRow, LogForm, InputsPanel, Scorecard
```

The CLI comes first. It is the fastest way to tune prompts and the knowledge base before any UI exists.

Mobile-first layout, since this gets checked from the phone before paddling out.

---

## 6. Evaluation loop

- **Session log:** after surfing, quick-log what actually broke at the sections Ryan saw (breaking yes/no, size, which peak). This is stored next to the prediction and the inputs it used.
- **Scorecard:** per-spot accuracy on breaking yes/no and size error, split by swell direction bucket and period. This shows where the knowledge base is wrong (for example, "Slot second-peak calls are wrong on 13–15 s SW").
- **Regression set:** saved past days (inputs plus Ryan's ground truth). Rerun them whenever the prompt or `spots.yaml` changes.
- Start with the Lane sections and Pleasure Point, where Ryan has the most ground truth.

---

## 7. Milestones

1. **Fetchers + `conditions.json`** for today and for forecast days; check the swell partitions against what's in the water.
2. **`spots.yaml` v1** for the default Lane set, reviewed by Ryan.
3. **Pre-pass + Opus call + CLI**; first test: does it reproduce today's call (2026-10-11, NW 11 s → Point only)?
4. **FastAPI + React UI** for the default set.
5. **County set** in `spots.yaml` plus the toggle.
6. **Session logging + scorecard.**
7. *(Optional)* Board pick from Ryan's quiver per spot and size, and a merge into The Lane Report.

---

## 8. Build status (2026-10-11)

Milestones 1–6 are built; see README.md to run it. Decisions taken while the
open questions below are pending:

- Default view is the Lane sections only (Pleasure Point is one toggle away in the county view).
- Local hosting (Vite dev server reachable from the phone on home wifi, or one uvicorn process after `npm run build`).
- Standalone app; board picks from the quiver are left for later.
- CDIP directional spectra aren't wired in yet. The NDBC `.spec` swell / wind-wave split and Open-Meteo's
  swell partitions cover the "buried S swell" case for now.
- Output schema uses `size_ft_low` / `size_ft_high` rather than a `[lo, hi]` array.

Not yet verified: live fetches from NDBC, Open-Meteo and NOAA, and a live Opus call. The build
environment had no route to those hosts and no API key, so everything was tested against
recorded-style data and a fake model. Run `python cli.py --dry-run` first to confirm the live data path.

## 9. Open questions for Ryan

1. Should the default set be the Lane sections only, or the Lane plus Pleasure Point?
2. Tide behavior of the Slot second peak: does it show better on lower or higher tide?
3. Hosting: local only, or deployed (Vercel/Render) so it works from the phone at the beach?
4. Should this eventually live inside The Lane Report instead of standing alone?
5. Board recommendations from the quiver: in v1 or later?
