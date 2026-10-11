"""On-disk storage for predictions and session reports (data/ is gitignored)."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from . import config

BREAKING = ("yes", "marginal", "no")


def _pred_dir() -> Path:
    d = config.DATA_DIR / "predictions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sessions_file() -> Path:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return config.DATA_DIR / "sessions.jsonl"


def save_prediction(result: dict) -> str:
    req = result["request"]
    stamp = datetime.now(config.TZ).strftime("%Y%m%dT%H%M%S")
    pid = f"{req['date']}_{req['start_hour']:02d}-{req['end_hour']:02d}_{req['scope']}_{stamp}"
    record = {k: v for k, v in result.items() if k != "prompt"}
    record["prediction_id"] = pid
    record["saved_at"] = datetime.now(config.TZ).isoformat(timespec="seconds")
    (_pred_dir() / f"{pid}.json").write_text(json.dumps(record, indent=1, default=str))
    return pid


def load_prediction(pid: str) -> dict:
    if not re.fullmatch(r"[\w.-]+", pid):
        raise ValueError("bad prediction id")
    return json.loads((_pred_dir() / f"{pid}.json").read_text())


def list_predictions() -> list[dict]:
    out = []
    for p in sorted(_pred_dir().glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except ValueError:
            continue
    return out


def log_session(*, date: str, spot_id: str, breaking: str, size_ft: float | None = None,
                start_hour: int | None = None, end_hour: int | None = None,
                notes: str = "", prediction_id: str | None = None) -> dict:
    if breaking not in BREAKING:
        raise ValueError(f"breaking must be one of {BREAKING}")
    datetime.strptime(date, "%Y-%m-%d")
    rec = {
        "id": uuid.uuid4().hex[:12],
        "logged_at": datetime.now(config.TZ).isoformat(timespec="seconds"),
        "date": date,
        "start_hour": start_hour,
        "end_hour": end_hour,
        "spot_id": spot_id,
        "breaking": breaking,
        "size_ft": size_ft,
        "notes": notes,
        "prediction_id": prediction_id,
    }
    with open(_sessions_file(), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def list_sessions() -> list[dict]:
    f = _sessions_file()
    if not f.exists():
        return []
    return [json.loads(ln) for ln in f.read_text().splitlines() if ln.strip()]
