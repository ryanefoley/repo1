"""Fixtures: a mock HTTP transport serving realistic data for 2026-10-11
(big mid-period NW, small S underneath, NW wind), and a fake Anthropic client."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from surfbreak import analyze, config  # noqa: E402
from surfbreak.fetchers import http as http_mod  # noqa: E402

NOW = datetime(2026, 10, 11, 9, 30, tzinfo=config.TZ)

# Times are UTC. 16:50Z = 09:50 PDT.
NDBC_46042_TXT = """\
#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft
2026 10 11 17 00 340  7.0  9.0    MM    MM    MM  MM 1001.4  14.7  16.8  11.0   MM +1.4    MM
2026 10 11 16 50 340  6.0  8.0   4.5    11   8.7 337 1001.4  14.8  16.8  11.2   MM   MM    MM
2026 10 11 15 20 315  7.0 10.0   4.4    11   8.2 330 1001.1  14.7  16.8  11.0   MM   MM    MM
2026 10 11 13 50 315 10.0 13.0   4.0    12   7.8 315 1001.2  14.6  16.9  10.9   MM   MM    MM
2026 10 11 11 50 315 11.0 14.0   3.8    11   7.8 320 1001.3  14.5  17.0  10.8   MM   MM    MM
"""

NDBC_46042_SPEC = """\
#YY  MM DD hh mm WVHT  SwH  SwP  WWH  WWP SwD WWD  STEEPNESS  APD MWD
#yr  mo dy hr mn    m    m  sec    m  sec  -  degT     -      sec degT
2026 10 11 16 40  4.5  3.6 11.1  2.4  7.1  NW NNW    AVERAGE  8.7 337
2026 10 11 15 10  4.4  3.5 11.1  2.4  6.7  NW NNW    AVERAGE  8.2 330
"""

NDBC_46236_TXT = """\
#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft
2026 10 11 16 56  MM   MM   MM   2.6    11   8.4 290     MM    MM  16.9    MM   MM   MM    MM
"""


def _hourly(day: str, fn) -> dict:
    times = [f"{day}T{h:02d}:00" for h in range(24)]
    cols: dict = {"time": times}
    for h in range(24):
        for k, v in fn(h).items():
            cols.setdefault(k, []).append(v)
    return {"latitude": 36.93, "longitude": -122.02, "timezone": "America/Los_Angeles", "hourly": cols}


def marine_payload(day: str) -> dict:
    return _hourly(day, lambda h: {
        "wave_height": 13.5, "wave_direction": 318, "wave_period": 9.0,
        "wind_wave_height": 6.5, "wind_wave_direction": 330, "wind_wave_period": 6.5,
        "swell_wave_height": 11.5, "swell_wave_direction": 312, "swell_wave_period": 11.2,
        "swell_wave_peak_period": 12.0,
        "secondary_swell_wave_height": 1.8, "secondary_swell_wave_direction": 200,
        "secondary_swell_wave_period": 15.0,
        "tertiary_swell_wave_height": None, "tertiary_swell_wave_direction": None,
        "tertiary_swell_wave_period": None,
    })


def wind_payload(day: str) -> dict:
    return _hourly(day, lambda h: {
        "wind_speed_10m": 8.0 if h < 11 else 16.0,
        "wind_direction_10m": 320,
        "wind_gusts_10m": 12.0 if h < 11 else 22.0,
    })


TIDES_HILO = {"predictions": [
    {"t": "2026-10-10 18:40", "v": "5.10", "type": "H"},
    {"t": "2026-10-11 01:10", "v": "1.90", "type": "L"},
    {"t": "2026-10-11 06:55", "v": "4.40", "type": "H"},
    {"t": "2026-10-11 13:20", "v": "0.30", "type": "L"},
    {"t": "2026-10-11 19:45", "v": "5.30", "type": "H"},
    {"t": "2026-10-12 02:15", "v": "1.70", "type": "L"},
    {"t": "2026-10-12 07:50", "v": "4.30", "type": "H"},
]}


def make_handler(fail: set[str] | None = None, calls: list | None = None):
    fail = fail or set()

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        if calls is not None:
            calls.append(str(url))
        host, path = url.host, url.path
        for f in fail:
            if f in str(url):
                return httpx.Response(503, text="down")
        if host == "www.ndbc.noaa.gov":
            name = path.rsplit("/", 1)[-1]
            body = {"46042.txt": NDBC_46042_TXT, "46042.spec": NDBC_46042_SPEC,
                    "46236.txt": NDBC_46236_TXT, "46012.txt": NDBC_46042_TXT,
                    "46012.spec": NDBC_46042_SPEC}.get(name)
            return httpx.Response(200, text=body) if body else httpx.Response(404)
        if host == "marine-api.open-meteo.com":
            return httpx.Response(200, json=marine_payload(url.params["start_date"]))
        if host == "api.open-meteo.com":
            return httpx.Response(200, json=wind_payload(url.params["start_date"]))
        if host == "api.tidesandcurrents.noaa.gov":
            return httpx.Response(200, json=TIDES_HILO)
        return httpx.Response(404)

    return handler


@pytest.fixture
def mock_http():
    calls: list[str] = []
    http_mod.set_client(httpx.Client(transport=httpx.MockTransport(make_handler(calls=calls))))
    yield calls
    http_mod.set_client(None)


@pytest.fixture
def failing_http():
    def use(*fail):
        http_mod.set_client(httpx.Client(transport=httpx.MockTransport(make_handler(fail=set(fail)))))
    yield use
    http_mod.set_client(None)


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    analyze._result_cache.clear()
    yield tmp_path / "data"


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.message


class FakeClient:
    """Records the request and returns a canned analysis for whatever spots were asked."""

    def __init__(self, stop_reason="end_turn", mutate=None):
        self.requests: list[dict] = []
        self.stop_reason = stop_reason
        self.mutate = mutate
        self.messages = SimpleNamespace(stream=self._stream)

    def _stream(self, **kwargs):
        self.requests.append(kwargs)
        user = kwargs["messages"][0]["content"]
        payload = json.loads(user[user.index("{"):])
        ids = payload["request"]["spot_ids_in_order"]
        out = {
            "summary": "Big mid-period NW; the Point is the call.",
            "swell_read": "Primary 11 s from 312°, small 15 s S underneath.",
            "wind_tide_read": "NW 16 kt in the afternoon, side-offshore at the Lane.",
            "best_call": "The Point around 4pm on the rising tide.",
            "spots": [
                {"id": i, "breaking": "yes" if i == "lane-point" else "no",
                 "size_ft_low": 6 if i == "lane-point" else 0, "size_ft_high": 10 if i == "lane-point" else 0,
                 "quality": 3 if i == "lane-point" else 1, "best_time": "16:00-17:00",
                 "why": "Because physics.", "key_inputs": ["11 s @ 312°"], "confidence": "medium"}
                for i in reversed(ids)  # deliberately out of order
            ],
            "caveats": [],
        }
        if self.mutate:
            out = self.mutate(out)
        msg = SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="thinking", thinking="..."), SimpleNamespace(type="text", text=json.dumps(out))],
            usage=SimpleNamespace(input_tokens=9000, output_tokens=3000,
                                  cache_creation_input_tokens=0, cache_read_input_tokens=6000),
        )
        return FakeStream(msg)


@pytest.fixture
def fake_client():
    return FakeClient()
