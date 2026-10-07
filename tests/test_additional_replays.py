import json
from datetime import date, timedelta

import pytest

from musa_nowcast.additional_replays import bounds, market_snapshot, proxy_share
from musa_nowcast.alfred import sha


def test_quarter_bounds_include_leap_day():
    assert bounds("2024Q1") == (date(2024,1,1), date(2024,3,31))
    assert bounds("2023Q4") == (date(2023,10,1), date(2023,12,31))


def test_proxy_month_boundary_uses_demand_not_days():
    start, end = bounds("2023Q1")
    demand = {}
    day = start
    while day <= end:
        week = day+timedelta(days=(4-day.weekday())%7)
        demand[week-timedelta(days=364)] = 100 if week.month == 1 else 200
        if week <= date(2023,1,27):
            demand[week] = 100
        day += timedelta(days=1)
    share, allocations = proxy_share(start,date(2023,1,31),end,demand)
    assert 0 < share < 31/90
    assert len(allocations) == 90
    assert allocations["2023-01-31"]["projected"] is True
    assert allocations["2023-01-26"]["projected"] is False


def snapshot(tmp_path, vintage="2023-02-02", observed="2023-02-06"):
    path = tmp_path/"series.json"
    path.write_text(json.dumps({"realtime_start": vintage, "realtime_end": vintage,
        "count": 1, "offset": 0, "units": "lin", "observations": [
            {"date": observed, "value": "3.0", "realtime_start": vintage, "realtime_end": vintage}]}))
    return {"case": {"cutoff": "2023-02-02"}, "market": [
        {"file": str(path), "sha256": sha(path), "series_id": "GASREGECW"}]}


def test_future_market_observation_blocks(tmp_path):
    with pytest.raises(ValueError, match="outside historical"):
        market_snapshot(snapshot(tmp_path))


def test_future_market_vintage_blocks(tmp_path):
    with pytest.raises(ValueError, match="wrong-vintage"):
        market_snapshot(snapshot(tmp_path, vintage="2026-10-07"))


def test_raw_market_tampering_blocks(tmp_path):
    manifest = snapshot(tmp_path)
    manifest["market"][0]["sha256"] = "wrong"
    with pytest.raises(ValueError, match="hash mismatch"):
        market_snapshot(manifest)


def test_missing_demand_support_does_not_fall_back_to_calendar():
    with pytest.raises(ZeroDivisionError):
        proxy_share(*[date(2023,1,1),date(2023,1,31),date(2023,3,31)], {})
