from datetime import date, timedelta
import json
from pathlib import Path

import pytest

from musa_nowcast.alternative_experiments import SERIES, fit_before, parse_series, quarter_supply, supply_feature
from musa_nowcast.data import RegionWeight
from musa_nowcast.futures_scenarios import parse_report, quarterly_scenario


def test_fitting_excludes_target_future_and_unpublished_outcomes():
    rows = [{'quarter':f'202{i}Q1','quarter_end':f'202{i}-03-31','outcome_available_at':f'202{i}-05-01',
             'features':[i], 'actual_cpg':20+i,'prediction_cpg':20} for i in range(8)]
    model, known = fit_before(rows,date(2028,1,1))
    assert len(known)==8
    rows.append({'quarter':'2028Q1','quarter_end':'2028-03-31','outcome_available_at':'2027-12-01',
                 'features':[999], 'actual_cpg':999,'prediction_cpg':0})
    rows.append({'quarter':'2019Q1','quarter_end':'2019-03-31','outcome_available_at':'2028-01-01',
                 'features':[999], 'actual_cpg':999,'prediction_cpg':0})
    second, known = fit_before(rows,date(2028,1,1))
    assert len(known)==8
    assert model.predict_one([3])==second.predict_one([3])
    with pytest.raises(ValueError):fit_before(rows,date(2021,1,1))


def synthetic_supply():
    # Weekly Friday series, including prior year for leap-year quarter handling.
    dates = []; d = date(2023,1,6)
    while d <= date(2024,4,5): dates.append(d); d+=timedelta(days=7)
    return {key:{d:(100.0 if key.startswith('stocks') else 80.0) for d in dates} for key in SERIES}


def test_supply_blocks_missing_weeks_and_does_not_use_final_week():
    series = synthetic_supply(); weights = [RegionWeight('Gulf Coast',1)]
    feature, detail = supply_feature(series,date(2024,1,1),date(2024,3,31),weights)
    assert feature==[0,0]
    assert max(detail['observation_dates'])=='2024-03-22'
    series['stocks_PADD3'][date(2024,3,29)] = 999999
    assert supply_feature(series,date(2024,1,1),date(2024,3,31),weights)[0]==[0,0]
    del series['stocks_PADD2'][date(2024,3,22)]
    with pytest.raises(ValueError,match='Missing exact weekly'):quarter_supply(series,date(2024,1,1),date(2024,3,31),weights)


REPORT = '''National Daily Ethanol Report October 7, 2026
Closing Settlement Prices as of 10/6/2026
NYMEX RBOB Gasoline ($/gal) 3.2732 (Nov 26) 3.0880 (Dec 26) 2.9674 (Jan 27) 2.9045 (Feb 27) 2.9011 (Mar 27) 3.1070 (Apr 27)
'''


def test_futures_preserves_basis_and_never_fills_missing_contracts():
    curve = parse_report(REPORT)
    assert curve['settlement_observation_date']=='2026-10-06'
    assert curve['report_publication_date']=='2026-10-07'
    assert curve['contracts'][0]['settlement_cpg']==pytest.approx(327.32)
    q1 = quarterly_scenario(curve,'2027Q1')
    assert q1['rbob_scenario_cpg']==pytest.approx(292.4333333333)
    assert q1['musa_retail_margin_cpg'] is None
    assert q1['scenarios_are_probabilistic'] is False
    q2 = quarterly_scenario(curve,'2027Q2')
    assert q2['missing_months']==['2027-05','2027-06']
    assert q2['rbob_scenario_cpg'] is None


def test_futures_rejects_wrong_units_future_quote_or_duplicate_month():
    with pytest.raises(ValueError):parse_report(REPORT.replace('$/gal','cents/bushel'))
    with pytest.raises(ValueError):parse_report(REPORT.replace('10/6/2026','10/8/2026'))
    with pytest.raises(ValueError):parse_report(REPORT.replace('Feb 27','Jan 27'))


def test_real_eia_series_identity_checked():
    root = Path('data/alternative_margin_experiments/2026-10-07_supply_v1')
    if not root.exists():pytest.skip('Local regional supply archive absent')
    raw = (root/'stocks_PADD3.xls').read_bytes()
    assert len(parse_series(raw,'WGTSTP31'))>1000
    with pytest.raises(ValueError):parse_series(raw,'WGTSTP11')


def test_research_results_never_promote_or_score_unreported_q3():
    p = Path('data/alternative_margin_experiments/2026-10-07_evaluation_v1/results.json')
    if not p.exists():pytest.skip('Local research evaluation absent')
    result = json.loads(p.read_text())
    assert result['production_changed'] is False
    assert result['strict_pit_validated'] is False
    for r in result['results'].values():
        for row in r['rows']:
            assert len(row['training_quarters'])>=8
            assert row['quarter'] not in row['training_quarters']
    assert result['current_shadows']['lagged_gap']['actual_cpg'] is None
