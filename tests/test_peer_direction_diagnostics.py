from copy import deepcopy
import json
from pathlib import Path

import pytest

from musa_nowcast.earnings_event_replay import load_archive, loading, select
from musa_nowcast.peer_direction_diagnostics import concentration, direction_forecasts, overlap_class

ROOT = Path('data/peer_direction_diagnostics/2026-10-08_v1')


def test_overlap_boundary_and_invalid_values():
    assert overlap_class(.5) == 'HIGH'
    assert overlap_class(.49999) == 'LOW'
    assert overlap_class(0) == 'NO_OVERLAP'
    for value in [-.01, 1.01, float('nan')]:
        with pytest.raises(ValueError):
            overlap_class(value)


def test_self_transfer_forbidden():
    with pytest.raises(ValueError, match='SELF_TRANSFER'):
        direction_forecasts([], 'MUSA', 'MUSA')


def test_target_and_future_actuals_do_not_change_prediction():
    records = load_archive()
    target = next(r for r in records if r['company'] == 'MUSA' and r['quarter'] == '2023Q3')
    original = next(r for r in direction_forecasts(records, 'CASY', 'MUSA')[0] if r['quarter'] == target['quarter'])
    changed = deepcopy(records)
    for row in changed:
        if row['available_at'] >= target['available_at']:
            row['actual_cpg'] = 999
    replay = next(r for r in direction_forecasts(changed, 'CASY', 'MUSA')[0] if r['quarter'] == target['quarter'])
    assert original == replay
    assert 'actual_cpg' not in original


def test_formulas_reuse_loading_and_same_day_donor_is_excluded():
    records = load_archive()
    target = next(r for r in records if r['company'] == 'MUSA' and r['quarter'] == '2023Q3')
    row = next(r for r in direction_forecasts(records, 'CASY', 'MUSA')[0] if r['quarter'] == target['quarter'])
    coefficient, pairs = loading(target, 'CASY', records, target['available_at'])
    assert row['loading'] == coefficient
    assert row['training_pairs'] == pairs
    x = row['overlap_weighted_surprise_cpg']
    assert row['fixed_prediction_cpg'] == pytest.approx(row['baseline_cpg'] + .5*x)
    assert row['fitted_prediction_cpg'] == pytest.approx(row['baseline_cpg'] + .5*coefficient*x)
    donor = select(target, 'CASY', records, target['available_at'])
    assert select(target, 'CASY', [donor], donor['available_at']) is None


def test_concentration_detects_one_quarter_dependence_without_refitting():
    rows = [{'quarter': 'A', 'baseline_abs_error_cpg': 10, 'fixed_abs_error_cpg': 6},
            {'quarter': 'B', 'baseline_abs_error_cpg': 1, 'fixed_abs_error_cpg': 2},
            {'quarter': 'C', 'baseline_abs_error_cpg': 1, 'fixed_abs_error_cpg': 2}]
    result = concentration(rows, 'fixed')
    assert result['positive_gain_disappears_without_best']
    assert result['improvement_without_best_quarter_cpg'] == -1
    assert result['largest_share_of_positive_gains'] == 1
    assert not result['refitted']
    assert concentration([], 'fixed') == {'n': 0}
    assert concentration(rows[:1], 'fixed')['improvement_without_best_quarter_cpg'] is None


def test_archive_all_directions_matched_bins_and_training_cutoffs():
    result = json.loads((ROOT/'results.json').read_text())
    frozen = json.loads((ROOT/'frozen_forecasts.json').read_text())
    assert len(result['directions']) == 6
    assert not result['production_changed']
    assert not result['strict_market_pit_verified']
    assert result['overlap_threshold'] == .5
    for name, payload in result['directions'].items():
        for group in payload['groups'].values():
            bins = group['matched']
            assert bins['ALL']['n'] == bins['HIGH']['n'] + bins['LOW']['n']
            for summary in bins.values():
                if not summary['n']:
                    continue
                for method in ['fixed', 'fitted']:
                    assert summary[method]['metrics']['identical_backtest_rows'] == summary['n']
        for row in frozen['directions'][name]['forecasts']:
            assert 'actual_cpg' not in row and 'baseline_abs_error_cpg' not in row
            assert row['donor_available_at'] < row['cutoff']
            for pair in row['training_pairs']:
                assert pair['recipient_quarter'] != row['quarter']
                assert pair['donor_available_at'] < pair['recipient_available_at'] < row['cutoff']
