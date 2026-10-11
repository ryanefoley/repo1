"""FastAPI app. Run: uvicorn surfbreak.main:app --reload (from backend/)."""
from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import analyze, config, dates, scorecard, spots, store

app = FastAPI(title="Surf Break Analyzer")


@app.get("/api/health")
def health():
    return {"ok": True, "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "model": config.MODEL, "effort": config.EFFORT}


@app.get("/api/spots")
def list_spots():
    return {
        "regions": [{"id": r, "name": spots.REGION_NAMES[r]} for r in spots.REGION_ORDER],
        "spots": [
            {"id": s["id"], "name": s["name"], "region": s["region"], "parent": s.get("parent"),
             "default": bool(s.get("default")), "confidence": s["confidence"]}
            for s in spots.load()
        ],
    }


@app.get("/api/analyze")
def run_analysis(
    date: str = "today",
    start: int = Query(..., ge=0, le=23),
    end: int = Query(..., ge=1, le=24),
    scope: Literal["lane", "county"] = "lane",
    spot_ids: str | None = None,
    dry_run: bool = False,
    refresh: bool = False,
):
    # Sync def: FastAPI runs it in a worker thread, so a multi-minute model call
    # doesn't block other requests.
    try:
        day = dates.parse_date(date)
        ids = [s for s in spot_ids.split(",") if s] if spot_ids else None
        res = analyze.run(day, start, end, scope=scope, ids=ids, dry_run=dry_run, use_cache=not refresh)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except analyze.AnalysisError as e:
        raise HTTPException(502, str(e))
    except Exception as e:  # API auth/network errors from the SDK
        name = type(e).__name__
        if name in ("AuthenticationError", "PermissionDeniedError"):
            raise HTTPException(500, "Anthropic API key missing or invalid (set ANTHROPIC_API_KEY)")
        if name in ("APIConnectionError", "APITimeoutError", "RateLimitError", "InternalServerError", "APIStatusError"):
            raise HTTPException(502, f"Anthropic API error: {e}")
        raise
    if not dry_run:
        res.pop("prompt", None)
    return res


class SessionIn(BaseModel):
    date: str
    spot_id: str
    breaking: Literal["yes", "marginal", "no"]
    size_ft: float | None = None
    start_hour: int | None = None
    end_hour: int | None = None
    notes: str = ""
    prediction_id: str | None = None


@app.post("/api/sessions")
def add_session(s: SessionIn):
    try:
        spots.select(ids=[s.spot_id])
        return store.log_session(**s.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/sessions")
def get_sessions():
    return store.list_sessions()


@app.get("/api/scorecard")
def get_scorecard():
    pairs = scorecard.match(store.list_sessions(), store.list_predictions())
    return {"pairs": len(pairs), **scorecard.score(pairs)}


# Serve the built frontend (npm run build) if present.
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "not found")
        f = config.FRONTEND_DIST / path
        if path and f.is_file() and config.FRONTEND_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
