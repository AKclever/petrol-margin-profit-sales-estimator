from pathlib import Path
import json

import pytest

from musa_nowcast.revenue_gap_audit import association, lagged_rows, pearson, ranks, reported_sss, reported_volume_and_margin


def test_rank_ties_and_zero_variance():
    assert ranks([9,1,1,4]) == [4,1.5,1.5,3]
    assert pearson([1,1,1],[2,3,4]) is None
    assert pearson([1,2,3],[3,2,1]) == pytest.approx(-1)
    assert association([{'quarter':'Q','x':None,'y':2}], 'x','y')['n'] == 0


def test_sss_is_reported_not_inferred_from_store_volume_levels():
    raw = b'<p>volumes on a same store sales ("SSS") basis declined 4.7%</p><table><tr><td>Fuel gallons per month</td><td>(4.7)</td><td>%</td></tr></table>'
    assert reported_sss(raw)['value'] == -4.7
    with pytest.raises(ValueError,match='disagree'):
        reported_sss(raw.replace(b'(4.7)</td>',b'(3.7)</td>'))
    assert reported_sss(b'<table><tr><td>Retail fuel volume SSS</td><td>200.0</td><td>220.0</td></tr></table>')['value'] is None


def test_sss_historical_improved_word():
    assert reported_sss(b'<p>volumes on a same store sales ("SSS") basis improved 1.8%</p>')['value'] == 1.8


def test_target_basis_excludes_wholesale_or_total_margin():
    with pytest.raises(ValueError):
        reported_volume_and_margin(b'<table><tr><td>Total fuel contribution</td><td>40.0</td></tr></table>')


def test_lag_must_be_exact_previous_quarter_and_public_before_cutoff():
    rows = [{'quarter':'2025Q4','quarter_end':'2025-12-31','revenue_proxy_error_cpg':2,
             'revenue_gap_available_at':'2026-03-31'},
            {'quarter':'2026Q1','quarter_end':'2026-03-31','actual_minus_production_cpg':3},
            {'quarter':'2026Q3','quarter_end':'2026-09-30','actual_minus_production_cpg':4}]
    assert lagged_rows(rows) == []
    rows[0]['revenue_gap_available_at'] = '2026-03-30'
    assert len(lagged_rows(rows)) == 1


def test_archived_full_coverage_and_no_manufactured_first_year_gap():
    root = Path('data/revenue_gap_all/2026-10-07_review_v1')
    if not root.exists():
        pytest.skip('Local all-quarter audit not installed')
    rows = json.loads((root/'quarter_rows.json').read_text())['rows']
    summary = json.loads((root/'summary.json').read_text())
    assert summary['coverage'] == {'total_quarters':30,'retail_revenue_quarters':30,
                                   'direct_sss_quarters':30,'yoy_gap_quarters':26,
                                   'production_oof_quarters':22}
    assert all(r.get('revenue_proxy_error_cpg') is None for r in rows[:4])
    assert all(r.get('actual_minus_production_cpg') is None for r in rows[:8])
    assert all(abs(r['identity_reconciliation_cpg']) < 1e-10 for r in rows[8:])
    assert not summary['production_changed']


def test_previous_six_results_reproduced():
    new = Path('data/revenue_gap_all/2026-10-07_review_v1/quarter_rows.json')
    old = Path('data/revenue_forward/2026-10-07_v2/revenue_diagnostics.json')
    if not new.exists() or not old.exists():
        pytest.skip('Local archived comparisons not installed')
    rows = {r['quarter']:r for r in json.loads(new.read_text())['rows']}
    for old_row in json.loads(old.read_text())['rows']:
        for field in ['revenue_proxy_error_cpg','implied_cost_residual_cpg','actual_minus_production_cpg']:
            assert rows[old_row['quarter']][field] == pytest.approx(old_row[field])
