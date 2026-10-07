from datetime import date, timedelta

import pytest

from musa_nowcast.data import MarketWeek,RegionWeight
from musa_nowcast.weekly_adjustment import PositiveRidge,WeeklyError,forecast_weekly,quarterly_path,regional_path,update_states


def fixture():
    market,demand = [],{}
    for i in range(150):
        week = date(2024,1,1)+timedelta(days=7*i)
        market.append(MarketWeek(week,"test",300+(i%7),200+(i%5)*4))
        demand[week] = 8000+(i%4)*100
    return market,[RegionWeight("test",1)],demand


def test_asymmetric_states_keep_memory_through_reversals():
    squeeze,capture = update_states(0,0,20,5)
    assert (squeeze,capture) == (15,0)
    assert update_states(squeeze,capture,-20,-5) == (7.5,15)


def test_reversing_price_sequence_changes_memory():
    def states(prices):
        rows = [MarketWeek(date(2024,1,1)+timedelta(days=7*i),"test",300,p) for i,p in enumerate(prices)]
        return [(r["squeeze_state"],r["capture_state"]) for r in regional_path(rows,"test").values()]
    first = [200,200,220,180,200]
    second = [200,200,180,220,200]
    assert sum(first) == sum(second)
    assert states(first) != states(second)


def test_calendar_boundaries_and_proxy_shares_reconcile():
    market,weights,demand = fixture()
    features,rows = quarterly_path(market,weights,demand,date(2026,7,1),date(2026,9,30))
    assert sum(r["days_in_quarter"] for r in rows) == 92
    assert sum(r["gallon_weight_proxy"] for r in rows) == pytest.approx(1)
    assert sum(r["days_in_quarter"] for r in rows if r["boundary_imputed"]) == 3
    assert len(features) == 3


def test_future_week_prices_are_not_used_for_end_stub():
    market,weights,demand = fixture()
    baseline = quarterly_path(market,weights,demand,date(2026,7,1),date(2026,9,30))[0]
    altered = [MarketWeek(m.week,m.region,10000,10000) if m.week >= date(2026,9,28) else m for m in market]
    assert quarterly_path(altered,weights,demand,date(2026,7,1),date(2026,9,30))[0] == baseline


def test_quarterly_supervision_and_weekly_allocations_reconcile():
    model = PositiveRidge().fit([[1,0,2],[2,1,0],[4,2,5],[3,0,1]],[1,2,4,3])
    rows = [{"features":[1,0,2],"gallon_weight_proxy":.3},
            {"features":[4,2,5],"gallon_weight_proxy":.7}]
    point,weekly = forecast_weekly(model,25,[1,1,1],rows)
    assert point == pytest.approx(sum(r["latent_margin_cpg"]*r["gallon_weight_proxy"] for r in weekly))


def test_sign_constraints_do_not_fit_opposite_economics():
    model = PositiveRidge().fit([[i,0,0] for i in range(8)],[-i for i in range(8)])
    assert all(c >= 0 for c in model.model.coefficients[1:])
    assert model.predict_one([0,0,0]) == pytest.approx(model.predict_one([7,0,0]))


def test_missing_demand_blocks_not_equal_weight_fallback():
    market,weights,demand = fixture()
    del demand[date(2026,8,3)]
    with pytest.raises(WeeklyError,match="missing demand"):
        quarterly_path(market,weights,demand,date(2026,7,1),date(2026,9,30))


def test_internal_market_gap_is_not_filled():
    market,weights,demand = fixture()
    market = [m for m in market if m.week != date(2026,8,3)]
    with pytest.raises(WeeklyError,match="missing regional"):
        quarterly_path(market,weights,demand,date(2026,7,1),date(2026,9,30))


def test_insufficient_warmup_is_blocked():
    market,weights,demand = fixture()
    with pytest.raises(WeeklyError):
        quarterly_path(market,weights,demand,date(2024,1,1),date(2024,3,31))
