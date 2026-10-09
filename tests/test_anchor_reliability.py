import copy
import json

import pytest

from musa_nowcast.anchor_reliability import ROOT, make_anchor, tail_metrics


def targets():
    return {r['quarter']: r for r in json.loads(
        (ROOT / 'historical_targets.json').read_text())['quarters']}


def test_current_and_future_outcomes_cannot_change_anchor():
    source = targets()
    expected = make_anchor('2023Q3', source)
    changed = copy.deepcopy(source)
    for quarter, row in changed.items():
        if quarter >= '2023Q3':
            row['retail_margin_cpg'] = 1000
    assert make_anchor('2023Q3', changed) == expected


def test_unpublished_recent_quarter_blocks_instead_of_filling():
    source = targets()
    source['2023Q2']['available_at'] = '2023-09-30'
    with pytest.raises(ValueError, match='MISSING_FOUR_PUBLISHED_RECENT_QUARTERS'):
        make_anchor('2023Q3', source)
    source.pop('2023Q2')
    with pytest.raises(ValueError, match='MISSING_FOUR_PUBLISHED_RECENT_QUARTERS'):
        make_anchor('2023Q3', source)


def test_fixed_equal_blend_and_complete_seasonal_windows():
    anchor = make_anchor('2023Q3', targets())
    assert anchor['blended_anchor_cpg'] == pytest.approx(
        .5 * anchor['original_anchor_cpg'] + .5 * anchor['alternative_anchor_cpg'])
    assert anchor['alternative_anchor_cpg'] == pytest.approx(
        anchor['recent_four_mean_cpg'] + anchor['seasonal_offset_cpg'])
    assert len(anchor['recent_input_quarters']) == 4
    assert all(len(row['window']) == 4 for row in anchor['seasonal_inputs'])


def test_insufficient_seasonal_history_remains_blocked():
    with pytest.raises(ValueError, match='FEWER_THAN_TWO_PRIOR_SEASONAL_OFFSETS'):
        make_anchor('2015Q3', targets())


def test_large_error_threshold_inclusive_and_rmse_separate():
    baseline = {'a': {'actual_cpg': 0, 'prediction_cpg': 5},
                'b': {'actual_cpg': 0, 'prediction_cpg': 0}}
    shadow = {'a': {'actual_cpg': 0, 'prediction_cpg': 4},
              'b': {'actual_cpg': 0, 'prediction_cpg': 6}}
    metrics = tail_metrics(baseline, shadow, ['a', 'b'])
    assert metrics['production']['large_error_count'] == 1
    assert metrics['production']['mae_cpg'] == 2.5
    assert metrics['production']['rmse_cpg'] == pytest.approx((25 / 2) ** .5)
    assert metrics['challenger']['large_error_count'] == 1
    assert tail_metrics(baseline, shadow, []) == {'n': 0}


def test_archived_all_quarter_activation_and_ordinary_cost():
    result = json.loads(open('data/anchor_reliability/2026-10-08_v1/results.json').read())
    modern = result['by_regime']['later_regime']
    assert len(modern['quarters']) == 22
    assert len(modern['original_large_error_quarters']) == 6
    assert modern['ordinary_group']['n'] == 16
    assert modern['ordinary_group']['challenger']['large_error_count'] == 1
    assert result['production_changed'] is False
    assert result['automatic_promotion'] is False
    for row in result['rows']:
        assert row['prediction_cpg'] == pytest.approx(
            row['anchor_evidence']['blended_anchor_cpg'] + row['market_adjustment_unchanged_cpg'])
        assert row['market_adjustment_unchanged_cpg'] == pytest.approx(
            row['production_prediction_cpg'] - row['seasonal_cpg'])
    rows = {r['quarter']: r for r in result['rows']}
    for quarter in ['2022Q1', '2026Q2']:
        row = rows[quarter]
        assert abs(row['actual_cpg'] - row['prediction_cpg']) > abs(
            row['actual_cpg'] - row['production_prediction_cpg'])
