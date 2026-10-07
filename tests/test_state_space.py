from datetime import date, timedelta

import pytest

from musa_nowcast.data import MarketWeek, QuarterActual, RegionWeight
from musa_nowcast.state_space import fit_pricing, filter_region, kalman_update, offset_state, predict


def inputs():
    market, demand = [], {}
    for i in range(150):
        week = date(2024,1,1)+timedelta(days=7*i)
        market.append(MarketWeek(week,'test',300+i%7,200+(i%5)*4))
        demand[week] = 8000+i%4*100
    history = [QuarterActual('2024Q2',date(2024,4,1),date(2024,6,30),25),
               QuarterActual('2025Q2',date(2025,4,1),date(2025,6,30),28)]
    return market, [RegionWeight('test',1)], demand, history


def test_kalman_update():
    mean, var = kalman_update(10,4,20,4)
    assert mean == 15
    assert var == 2
    with pytest.raises(ValueError):
        kalman_update(0,-1,10,4)


def test_pricing_bounds_and_no_future_fit():
    market,_,_,_ = inputs()
    cutoff = date(2025,6,30)
    fitted = fit_pricing(market,'test',cutoff)
    altered = [MarketWeek(r.week,r.region,10000,1) if r.week > cutoff else r for r in market]
    assert fit_pricing(altered,'test',cutoff) == fitted
    assert 0 <= fitted['rise_speed'] <= 1
    assert 0 <= fitted['fall_speed'] <= 1


def test_forward_filter_is_not_a_smoother():
    market,_,_,_ = inputs()
    pricing = fit_pricing(market,'test',date(2024,12,31))
    first = filter_region(market,'test',pricing,100,date(2025,3,31))
    second = filter_region(market,'test',pricing,100,date(2026,9,30))
    assert all(second[w] == r for w,r in first.items())


def test_offset_seasons_stay_separate():
    _,_,_,history = inputs()
    spreads = {'2024Q2':40,'2025Q2':40}
    original = offset_state(history,spreads,2)
    extra = QuarterActual('2025Q3',date(2025,7,1),date(2025,9,30),10000)
    assert offset_state(history+[extra],spreads,2) == original


def test_forecast_reconciles_and_ignores_future_prices():
    market,weights,demand,history = inputs()
    target = ('2026Q2',date(2026,4,1),date(2026,6,30))
    result, weekly = predict(market,weights,demand,history,target,100)
    assert result['prediction_cpg'] == pytest.approx(sum(r['gallon_weight_proxy']*r['latent_company_margin_cpg'] for r in weekly))
    changed = [MarketWeek(r.week,r.region,1,10000) if r.week >= date(2026,6,29) else r for r in market]
    assert predict(changed,weights,demand,history,target,100)[0] == result


def test_target_actual_cannot_be_training():
    market,weights,demand,history = inputs()
    with pytest.raises(ValueError,match='training must end'):
        predict(market,weights,demand,history,('2025Q2',date(2025,4,1),date(2025,6,30)),100)


def test_asymmetric_response_changes_filtered_path():
    market,_,_,_ = inputs()
    pricing = fit_pricing(market,'test',date(2024,12,31))
    altered = pricing | {'rise_speed':1.,'fall_speed':0.}
    assert filter_region(market,'test',pricing,100,date(2025,3,31)) != filter_region(market,'test',altered,100,date(2025,3,31))


def test_internal_missing_market_week_blocks():
    market,weights,demand,history = inputs()
    market = [r for r in market if r.week != date(2026,5,4)]
    with pytest.raises(ValueError,match='missing regional'):
        predict(market,weights,demand,history,('2026Q2',date(2026,4,1),date(2026,6,30)),100)
