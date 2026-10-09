from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest

from musa_nowcast.caseys_specific import SOURCE, ROOT, component_forecasts, extract
from musa_nowcast.data import load_weights
from musa_nowcast.joint_all_features import market_from_json

ARCHIVE=Path('data/caseys_specific/2026-10-08_evaluation_v2')


def inputs():
    records=json.loads((ARCHIVE/'components.json').read_text())['records']
    market=market_from_json(json.loads((ROOT/'normalized_market.json').read_text())['regular'])
    return records,market,load_weights('data/caseys/weights.csv')


def test_current_quarter_not_ytd_and_zero_is_explicit():
    records,_,_=inputs(); by_q={r['quarter']:r for r in records}
    row=extract((SOURCE/'F2023Q4.html').read_bytes(),by_q['F2023Q4'])
    assert row['fuel_gallons']==635916000
    assert row['rin_proceeds_dollars']==0
    assert row['ex_rin_proxy_cpg']==row['retail_margin_cpg']
    row=extract((SOURCE/'F2022Q1.html').read_bytes(),by_q['F2022Q1'])
    assert row['rin_proceeds_dollars']==18700000
    assert row['rin_proceeds_cpg']==pytest.approx(18700000/667534000*100)


def test_missing_disclosure_never_means_zero():
    records,_,_=inputs(); expected=records[0]
    with pytest.raises(ValueError):
        extract(b'<html>No RIN disclosure</html>',expected)
    changed=expected|{'retail_margin_cpg':999}
    with pytest.raises(ValueError,match='CURRENT_MARGIN'):
        extract((SOURCE/'F2021Q3.html').read_bytes(),changed)


def test_own_rin_and_margin_outcomes_do_not_change_own_prediction():
    records,market,weights=inputs()
    before,_=component_forecasts(records,market,weights)
    altered=deepcopy(records)
    for row in altered:
        if row['quarter']=='F2024Q2':
            row['rin_proceeds_cpg']=50
            row['ex_rin_proxy_cpg']=999
    after,_=component_forecasts(altered,market,weights)
    assert before['F2024Q2']==after['F2024Q2']


def test_later_market_observations_cannot_change_historical_prediction():
    records,market,weights=inputs()
    before,_=component_forecasts(records,market,weights)
    trimmed=[m for m in market if m.week<=date(2023,10,31)]
    short=[r for r in records if r['end']<='2023-10-31']
    after,_=component_forecasts(short,trimmed,weights)
    assert before['F2024Q2']==after['F2024Q2']


def test_archive_scoring_and_training_dates():
    components=json.loads((ARCHIVE/'components.json').read_text())
    assert len(components['records'])==22
    reviews={r['quarter']:r for r in components['source_reviews']}
    assert reviews['F2027Q1']['reason']=='BLOCKED_RIN_ACCOUNTING_CHANGE_PROCEEDS_NOT_TOTAL_RECOGNIZED_INCOME'
    results=json.loads((ARCHIVE/'results.json').read_text())
    assert len(results['rows'])==14
    assert not results['production_changed'] and not results['strict_market_pit_verified']
    assert not results['groups']['all']['metrics']['passes_pre_registered_gate']
    indexed={r['quarter']:r for r in components['records']}
    for row in results['rows']:
        assert row['prediction_cpg']==pytest.approx(row['ex_rin_forecast_cpg']+row['rin_forecast_cpg'])
        assert row['quarter'] not in row['training_quarters']
        assert len(row['rin_training_quarters'])==4
        assert all(indexed[q]['available_at']<row['information_cutoff'] for q in row['training_quarters'])
