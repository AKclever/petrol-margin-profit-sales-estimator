from datetime import date, timedelta

import pytest

from musa_nowcast.data import MarketWeek, QuarterActual, RegionWeight
from musa_nowcast.model import NowcastEngine
from musa_nowcast.sequence_anchor import anchor_anomaly, contributions, features, fit_correction, regional_states


def actual(year,value):
    return QuarterActual(f'{year}Q3',date(year,7,1),date(year,9,30),value)


def test_anchor_uses_only_earlier_same_season():
    history = [actual(2020,19),actual(2021,24),actual(2022,39.3),actual(2023,28.7)]
    anomaly,detail = anchor_anomaly(history,'2023Q3')
    assert anomaly == pytest.approx(15.3)
    assert detail['earlier_seasonal_quarters'] == ['2020Q3','2021Q3','2022Q3']
    assert anchor_anomaly(history[:-1],'2023Q3') == (anomaly,detail)


def test_initial_anchor_has_no_invented_anomaly():
    assert anchor_anomaly([actual(2021,24)],'2022Q3')[0] == 0
    with pytest.raises(ValueError,match='missing prior-year'):
        anchor_anomaly([],'2022Q3')


def test_sequence_reversal_and_forward_causality():
    def path(prices):
        rows = [MarketWeek(date(2024,1,1)+WEEK*i,'test',300,p) for i,p in enumerate(prices)]
        return regional_states(rows,'test')
    WEEK = timedelta(days=7)
    a = path([200,240,160,200])
    b = path([200,160,240,200])
    assert a[date(2024,1,22)] != b[date(2024,1,22)]
    longer = path([200,240,160,200,10000])
    assert all(longer[w] == r for w,r in a.items())


def test_residual_fit_excludes_target_and_future_labels():
    rows = [{'quarter':f'{2020+i//4}Q{i%4+1}','features':[i,i%3,-i%2],
             'actual_cpg':20+i,'prediction_cpg':20} for i in range(12)]
    model,training = fit_correction(rows,'2022Q1')
    assert len(training) == 8
    changed = [r if r['quarter'] < '2022Q1' else r|{'actual_cpg':10000} for r in rows]
    assert fit_correction(changed,'2022Q1')[0].export() == model.export()
    with pytest.raises(ValueError,match='insufficient'):
        fit_correction(rows,'2021Q4')


def test_regional_nonlinearity_does_not_cancel_opposing_moves():
    rows = [MarketWeek(date(2024,1,1),'a',300,200),MarketWeek(date(2024,1,8),'a',300,220),
            MarketWeek(date(2024,1,1),'b',300,200),MarketWeek(date(2024,1,8),'b',300,180)]
    a,b = regional_states(rows,'a'),regional_states(rows,'b')
    assert a[date(2024,1,8)]['squeeze'] == 20
    assert b[date(2024,1,8)]['capture'] == 20


def test_correction_contributions_reconcile():
    rows = [{'quarter':f'{2020+i//4}Q{i%4+1}','features':[i,i%3,-i%2],
             'actual_cpg':20+i,'prediction_cpg':20} for i in range(12)]
    model,_ = fit_correction(rows,'2022Q1')
    row = [2,4,-5]
    assert sum(contributions(model,row).values()) == pytest.approx(.5*model.predict_one(row))


def test_missing_complete_week_blocks():
    rows = [MarketWeek(date(2024,1,1)+timedelta(days=7*i),'test',300+i%5,200+i%7) for i in range(140)]
    rows = [r for r in rows if r.week != date(2026,8,3)]
    engine = NowcastEngine(rows,[RegionWeight('test',1)],[])
    paths = {'test':regional_states(rows,'test')}
    with pytest.raises(ValueError,match='missing internal'):
        features(engine,[actual(2025,28)],'2026Q3',date(2026,7,1),date(2026,9,30),paths)
