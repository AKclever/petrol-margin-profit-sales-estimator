from datetime import date, timedelta
import json
from pathlib import Path

import pytest

from musa_nowcast.history_floor_basis import (
    OLD, bounds, extract_target, floor_feature, floor_values, regime, residual_shadow,
)


def test_early_direct_margin_not_ytd_or_all_in():
    r = extract_target((OLD/'2013Q3_release.html').read_bytes())
    assert r['retail_margin_cpg'] == 14.8
    assert r['gallons_million'] == 971
    assert r['reconciliation_status'] == 'DIRECT_MARGIN_ONLY_NO_EXACT_CONTRIBUTION_BRIDGE'


def test_billion_rounding_not_comparative_million_gallons():
    r = extract_target((OLD/'2015Q2_release.html').read_bytes())
    assert r['retail_margin_cpg'] == 9
    assert r['gallons_million'] is None
    assert '1.01 billion gallons' in r['target_evidence']['volume_sentence']


def test_quarter_not_annual_and_preliminary_label():
    r = extract_target((OLD/'2017Q4_release.html').read_bytes())
    assert r['retail_margin_cpg'] == 13.8
    assert r['report_status'] == 'PRELIMINARY_REPORTED'
    assert r['reconciliation_status'] == 'RECONCILED_WITHIN_ROUNDING'


def test_bad_contribution_bridge_blocks():
    raw = b'<table><tr><td>Retail fuel margin (cpg)</td><td>10.0</td></tr><tr><td>Retail fuel volume - chain</td><td>1000.0</td></tr><tr><td>Total retail fuel contribution ($ Millions)</td><td>200.0</td></tr></table>'
    with pytest.raises(ValueError, match='bridge'):
        extract_target(raw)


def test_no_consolidated_ethanol_cost_inference():
    r = floor_values((OLD/'2014Q1_release.html').read_bytes(), '2014Q1', 910.1)
    assert r['station_cost_cpg'] is None


def test_floor_uses_only_prior_published_signed_features():
    prior = {'quarter':'2025Q1','available_at':'2025-05-01','station_cost_cpg':23.,'direct_sss_percent':-4.2}
    older = {'quarter':'2024Q1','available_at':'2024-05-01','station_cost_cpg':22.}
    x, _ = floor_feature('2025Q2',{'2025Q1':prior,'2024Q1':older})
    assert x == [1.,4.2]
    prior['direct_sss_percent'] = 2.
    assert floor_feature('2025Q2',{'2025Q1':prior,'2024Q1':older})[0] == [1.,-2.]
    prior['available_at'] = '2025-06-30'
    with pytest.raises(ValueError,match='published'):
        floor_feature('2025Q2',{'2025Q1':prior,'2024Q1':older})


def make_residual(q, availability=None):
    _, end = bounds(q)
    return {'quarter':q,'quarter_end':str(end),'outcome_available_at':availability or str(end+timedelta(days=30)),
            'features':[1.],'actual_cpg':30.,'prediction_cpg':29.,'seasonal_cpg':28.}


def test_residuals_never_pool_regimes():
    rows = [make_residual(f'{y}Q{q}') for y in [2018,2019] for q in range(1,5)]
    rows += [make_residual('2021Q1')]
    shadow, blocked = residual_shadow(rows)
    assert '2021Q1' not in shadow
    assert blocked[-1]['reason'] == 'FEWER_THAN_EIGHT_PUBLISHED_SAME_REGIME_RESIDUALS'


def test_delayed_outcome_not_training_and_no_held_out_actual_leak():
    rows = [make_residual(f'{y}Q{q}') for y in [2021,2022] for q in range(1,5)]
    target = make_residual('2023Q1'); rows.append(target)
    shadow, _ = residual_shadow(rows)
    assert len(shadow['2023Q1']['training_quarters']) == 8
    point = shadow['2023Q1']['prediction_cpg']
    target['actual_cpg'] = 100
    assert residual_shadow(rows)[0]['2023Q1']['prediction_cpg'] == point
    rows[0]['outcome_available_at'] = '2023-04-01'
    assert '2023Q1' not in residual_shadow(rows)[0]


def test_regime_and_calendar_boundaries():
    assert bounds('2020Q1')[1] == date(2020,3,31)
    assert bounds('2013Q4')[1] == date(2013,12,31)
    assert [regime(q) for q in ['2019Q4','2020Q1','2021Q1']] == ['earlier_low_margin','transition','later_regime']


def test_archived_result_reconciliation_and_no_promotions():
    root = Path('data/history_floor_basis/2026-10-07_evaluation_v6')
    r = json.loads((root/'results.json').read_text())
    assert r['target_quarters'] == 52
    assert r['expanded_oof_quarters'] == 44
    assert r['production_changed'] is False
    assert r['market_differences_from_production'] == []
    for name in ['all_grade','floor','diesel']:
        for group in r[name]['by_regime'].values():
            if group['metrics']:
                assert group['metrics']['passes_pre_registered_gate'] is False
    for row in r['diesel']['shadow_rows']:
        assert all(regime(q) == regime(row['quarter']) and q < row['quarter'] for q in row['training_quarters'])
