from datetime import date, datetime

import pytest
from conftest import NDBC_46042_SPEC, NDBC_46042_TXT, NOW, TIDES_HILO

from surfbreak import conditions, config
from surfbreak.fetchers import FetchError, ndbc, tides
from surfbreak.units import angle_diff, compass_to_deg, deg_to_compass, distance_outside, in_range


def test_units():
    assert angle_diff(350, 10) == 20
    assert angle_diff(10, 190) == 180
    assert in_range(355, 340, 20) and not in_range(30, 340, 20)
    assert distance_outside(315, 180, 215) == 100
    assert compass_to_deg("NW") == 315 and compass_to_deg("MM") is None
    assert deg_to_compass(312) == "NW" and deg_to_compass(200) == "SSW"


def test_parse_txt_converts_units_and_skips_missing():
    rows = ndbc.parse_txt(NDBC_46042_TXT)
    assert rows[0]["wave_height_ft"] is None  # MM row
    latest = rows[1]
    assert latest["wave_height_ft"] == pytest.approx(14.8, abs=0.1)
    assert latest["dominant_period_s"] == 11
    assert latest["mean_wave_dir_deg"] == 337
    assert latest["wind_kt"] == pytest.approx(11.7, abs=0.1)


def test_parse_spec_splits_swell_and_windwave():
    s = ndbc.parse_spec(NDBC_46042_SPEC)[0]
    assert s["swell_dir"] == "NW" and s["swell_dir_deg"] == 315
    assert s["swell_period_s"] == 11.1
    assert s["windwave_dir_deg"] == 337.5
    assert s["swell_height_ft"] == pytest.approx(11.8, abs=0.1)


def test_bad_ndbc_format():
    with pytest.raises(FetchError):
        ndbc.parse_table("<html>not found</html>")


def test_tide_interpolation():
    ext = tides.parse_hilo(TIDES_HILO)
    lo = datetime(2026, 10, 11, 13, 20, tzinfo=config.TZ)
    assert tides.interpolate(ext, lo) == pytest.approx(0.30)
    hi = datetime(2026, 10, 11, 19, 45, tzinfo=config.TZ)
    mid = lo + (hi - lo) / 2
    assert tides.interpolate(ext, mid) == pytest.approx((0.30 + 5.30) / 2, abs=0.01)
    assert tides.tide_state(ext, mid) == "rising"


def test_gather_today_includes_buoys(mock_http):
    cond = conditions.gather(date(2026, 10, 11), 16, 17, ["santa_cruz"], now=NOW)
    assert cond["is_today"]
    assert cond["buoys"]["46042"]["spectral_latest"]["swell_dir"] == "NW"
    assert len(cond["forecast"]["santa_cruz"]["window_hours"]) == 2  # 16:00 and 17:00
    assert cond["tide"]["window_hours"][0]["state"] == "rising"
    assert all(s["status"] == "ok" for s in cond["sources"])
    assert conditions.usable(cond)


def test_gather_future_skips_buoys(mock_http):
    cond = conditions.gather(date(2026, 10, 14), 6, 9, ["north_coast"], now=NOW)
    assert cond["buoys"] == {}
    assert any(s["status"] == "skipped" for s in cond["sources"])
    assert not any("ndbc" in u for u in mock_http)


def test_gather_degrades_when_sources_fail(failing_http):
    failing_http("ndbc", "tidesandcurrents")
    cond = conditions.gather(date(2026, 10, 11), 16, 17, ["santa_cruz"], now=NOW)
    errors = [s for s in cond["sources"] if s["status"] == "error"]
    assert len(errors) == 4  # 3 buoys + tides
    assert cond["tide"] is None
    assert conditions.usable(cond)  # forecast still there


def test_date_limits(mock_http):
    with pytest.raises(ValueError):
        conditions.gather(date(2026, 10, 20), 6, 9, ["santa_cruz"], now=NOW)
    with pytest.raises(ValueError):
        conditions.gather(date(2026, 10, 11), 9, 9, ["santa_cruz"], now=NOW)
