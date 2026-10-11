import json
from datetime import date

import pytest
from conftest import NOW, FakeClient
from fastapi.testclient import TestClient

from surfbreak import analyze, conditions, dates, features, scorecard, spots, store
from surfbreak.schema import JSON_SCHEMA

DAY = date(2026, 10, 11)


def test_spot_selection():
    lane = spots.select("lane")
    assert [s["id"] for s in lane] == [
        "lane-indicators", "lane-middle-peak", "lane-point", "lane-slot", "lane-slot-second-peak", "cowells"]
    county = spots.select("county")
    assert len(county) == len(spots.load()) > 20
    assert county[0]["region"] == "north_coast" and county[-1]["region"] == "south_county"
    with pytest.raises(ValueError):
        spots.select(ids=["nope"])


def test_features_match_todays_read(mock_http):
    cond = conditions.gather(DAY, 16, 17, ["santa_cruz"], now=NOW)
    by_id = {f["id"]: f for f in features.build(spots.select("lane"), cond)}

    point = {p["kind"]: p for p in by_id["lane-point"]["forecast_partitions"]}
    assert point["primary_swell"]["window_position"] == "ok"
    assert point["primary_swell"]["wraps_in"]  # 11.2 s >= 10 s

    second = {p["kind"]: p for p in by_id["lane-slot-second-peak"]["forecast_partitions"]}
    assert second["primary_swell"]["window_position"] == "outside"  # 312° NW can't reach it
    assert second["secondary_swell"]["window_position"] == "best"  # the small 200° S can

    # Observed buoy split is used today.
    assert by_id["lane-point"]["observed_partitions"][0]["kind"] == "observed_swell"
    assert by_id["lane-point"]["naive_face_ft_observed"] > by_id["lane-slot-second-peak"]["naive_face_ft_observed"]

    assert by_id["lane-point"]["wind"]["relative_to_break"] == "cross-offshore"
    assert by_id["lane-point"]["tide"]["state"] == "rising"


def test_wind_relation():
    assert features.wind_relation(20, 200) == "offshore"
    assert features.wind_relation(200, 200) == "onshore"
    assert features.wind_relation(290, 200) == "cross-shore"


def test_dry_run_builds_prompt(mock_http):
    res = analyze.run(DAY, 16, 17, dry_run=True, now=NOW)
    sys_blocks = res["prompt"]["system"]
    assert sys_blocks[-1]["cache_control"] == {"type": "ephemeral"}
    assert "lane-slot-second-peak" in sys_blocks[-1]["text"]
    user = json.loads(res["prompt"]["user"][res["prompt"]["user"].index("{"):])
    assert user["request"]["spot_ids_in_order"][0] == "lane-indicators"
    assert "features" in user and "conditions" in user


def test_system_prompt_is_identical_across_scopes(mock_http):
    a = analyze.run(DAY, 16, 17, scope="lane", dry_run=True, now=NOW)["prompt"]["system"]
    b = analyze.run(DAY, 16, 17, scope="county", dry_run=True, now=NOW)["prompt"]["system"]
    assert a == b  # same cached prefix for both


def test_run_calls_model_and_saves(mock_http, fake_client, tmp_data_dir):
    res = analyze.run(DAY, 16, 17, client=fake_client, now=NOW)
    req = fake_client.requests[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["output_config"]["effort"] == "high"
    assert req["output_config"]["format"]["schema"] == JSON_SCHEMA
    assert req["max_tokens"] >= 16000
    # Reordered to match the request, despite the model returning them reversed.
    assert [c["id"] for c in res["analysis"]["spots"]] == [s["id"] for s in spots.select("lane")]
    assert res["usage"]["cost_usd"] == pytest.approx((9000 * 4 + 3000 * 20 + 6000 * 0.2) / 1e6)
    assert (tmp_data_dir / "predictions" / f"{res['prediction_id']}.json").exists()

    again = analyze.run(DAY, 16, 17, client=fake_client, now=NOW)
    assert again["cached"] and len(fake_client.requests) == 1


def test_run_reports_missing_spots(mock_http):
    def drop_one(out):
        out["spots"] = [s for s in out["spots"] if s["id"] != "cowells"]
        return out

    res = analyze.run(DAY, 16, 17, client=FakeClient(mutate=drop_one), now=NOW)
    assert any("cowells" in w for w in res["warnings"])


def test_run_errors(mock_http):
    with pytest.raises(analyze.AnalysisError):
        analyze.run(DAY, 16, 17, client=FakeClient(stop_reason="max_tokens"), now=NOW)

    def bad(out):
        out["spots"][0]["breaking"] = "maybe"
        return out

    with pytest.raises(analyze.AnalysisError):
        analyze.run(DAY, 16, 17, client=FakeClient(mutate=bad), now=NOW, use_cache=False)


def test_no_data_stops_before_model(failing_http):
    failing_http("ndbc", "open-meteo", "tidesandcurrents")
    client = FakeClient()
    with pytest.raises(analyze.AnalysisError):
        analyze.run(DAY, 16, 17, client=client, now=NOW)
    assert client.requests == []


def test_scorecard(mock_http, fake_client):
    res = analyze.run(DAY, 16, 17, client=fake_client, now=NOW)
    store.log_session(date="2026-10-11", spot_id="lane-point", breaking="yes", size_ft=9, start_hour=16, end_hour=18)
    store.log_session(date="2026-10-11", spot_id="lane-slot-second-peak", breaking="marginal", size_ft=3,
                      notes="a couple of sets", prediction_id=res["prediction_id"])
    pairs = scorecard.match(store.list_sessions(), store.list_predictions())
    sc = scorecard.score(pairs)
    assert sc["overall"]["n"] == 2
    assert sc["overall"]["breaking_exact_acc"] == 0.5
    assert sc["overall"]["breaking_yes_no_acc"] == 0.5
    assert sc["overall"]["size_mae_ft"] == pytest.approx((1 + 3) / 2)
    assert sc["misses"][0]["spot_id"] == "lane-slot-second-peak"
    assert "NW" in next(iter(sc["by_swell_bucket"]))


def test_dates():
    from datetime import date as d

    today = d(2026, 10, 11)  # Sunday
    assert dates.parse_date("sat", today) == d(2026, 10, 17)
    assert dates.parse_date("sun", today) == today
    assert dates.parse_date("tomorrow", today) == d(2026, 10, 12)
    assert dates.parse_window("16-17") == (16, 17)
    assert dates.parse_window("dawn") == (6, 9)
    with pytest.raises(ValueError):
        dates.parse_window("18-16")


def test_api(mock_http, monkeypatch, fake_client):
    from surfbreak import main

    real_run = analyze.run
    monkeypatch.setattr(analyze, "run", lambda *a, **k: real_run(*a, **{**k, "client": fake_client, "now": NOW}))
    c = TestClient(main.app)
    assert len(c.get("/api/spots").json()["spots"]) > 20

    r = c.get("/api/analyze", params={"date": "2026-10-11", "start": 16, "end": 17})
    assert r.status_code == 200
    body = r.json()
    assert "prompt" not in body and body["analysis"]["spots"]

    r = c.get("/api/analyze", params={"date": "2026-10-11", "start": 16, "end": 17, "dry_run": True})
    assert "prompt" in r.json()

    assert c.get("/api/analyze", params={"date": "2026-10-11", "start": 17, "end": 16}).status_code == 400

    r = c.post("/api/sessions", json={"date": "2026-10-11", "spot_id": "lane-point", "breaking": "yes", "size_ft": 8})
    assert r.status_code == 200
    assert c.post("/api/sessions", json={"date": "2026-10-11", "spot_id": "x", "breaking": "yes"}).status_code == 400
    assert c.get("/api/scorecard").json()["pairs"] == 1


def test_regression_rerun(mock_http, fake_client, monkeypatch, capsys):
    import regression

    res = analyze.run(DAY, 16, 17, client=fake_client, now=NOW)
    store.log_session(date="2026-10-11", spot_id="lane-point", breaking="yes", size_ft=8,
                      prediction_id=res["prediction_id"])
    assert regression.main([]) == 0  # dry: no calls
    assert len(fake_client.requests) == 1

    real = analyze.rerun_saved
    monkeypatch.setattr(analyze, "rerun_saved", lambda p, client=None: real(p, client=fake_client))
    assert regression.main(["--yes"]) == 0
    assert len(fake_client.requests) == 2
    out = capsys.readouterr().out
    assert "before:" in out and "now:" in out


def test_missing_key_is_a_clear_error(mock_http, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(analyze.AnalysisError, match="ANTHROPIC_API_KEY"):
        analyze.run(DAY, 16, 17, now=NOW)
