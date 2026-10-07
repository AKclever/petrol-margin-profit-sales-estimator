import pytest

from musa_nowcast.alfred import CUTOFF, validate_snapshot


def snapshot():
    return {"realtime_start": CUTOFF, "realtime_end": CUTOFF, "units": "lin", "count": 1,
            "offset": 0, "observations": [{"realtime_start": CUTOFF, "realtime_end": CUTOFF,
                                            "date": "2025-06-09", "value": "2.949"}]}


def test_correct_snapshot_accepted_without_inventing_intraday_availability():
    assert validate_snapshot(snapshot(), "GASREGECW", "2019-01-01")[0]["date"] == "2025-06-09"


def test_empty_or_truncated_responses_do_not_pass_pit_validation():
    payload = snapshot()
    payload["count"] = 2
    with pytest.raises(ValueError, match="truncated"):
        validate_snapshot(payload, "GASREGECW", "2019-01-01")
    payload["observations"] = []
    with pytest.raises(ValueError, match="empty"):
        validate_snapshot(payload, "GASREGECW", "2019-01-01")


def test_future_vintage_or_future_observation_is_rejected():
    payload = snapshot()
    payload["realtime_end"] = "2026-10-07"
    with pytest.raises(ValueError, match="wrong vintage"):
        validate_snapshot(payload, "GASREGECW", "2019-01-01")
    payload = snapshot()
    payload["observations"][0]["date"] = "2025-06-16"
    with pytest.raises(ValueError, match="PIT window"):
        validate_snapshot(payload, "GASREGECW", "2019-01-01")
