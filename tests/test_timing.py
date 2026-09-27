from datetime import date

import pytest

from musa_nowcast.data import MarketWeek
from musa_nowcast.timing import TimingError, transform_market


def _market() -> list[MarketWeek]:
    return [
        MarketWeek(date(2026, 1, 5), "Gulf", 300.0, 200.0),
        MarketWeek(date(2026, 1, 12), "Gulf", 310.0, 220.0),
        MarketWeek(date(2026, 1, 19), "Gulf", 320.0, 260.0),
    ]


def test_fixed_timing_transforms_are_mechanical_and_predefined():
    lag = transform_market(_market(), "A_LAG_1_WEEK")
    blend = transform_market(_market(), "B_CURRENT_PRIOR_50_50")
    trailing = transform_market(_market(), "C_TRAILING_3_WEEK_EQUAL")
    assert [row.wholesale_cpg for row in lag] == [200.0, 220.0]
    assert [row.wholesale_cpg for row in blend] == [210.0, 240.0]
    assert [row.wholesale_cpg for row in trailing] == [pytest.approx(680.0 / 3.0)]


def test_timing_transform_does_not_bridge_missing_weeks():
    market = [_market()[0], _market()[2]]
    with pytest.raises(TimingError, match="produced no rows"):
        transform_market(market, "A_LAG_1_WEEK")


def test_unknown_timing_candidate_is_rejected():
    with pytest.raises(TimingError, match="Unknown timing candidate"):
        transform_market(_market(), "OPTIMIZED_AFTER_THE_FACT")
