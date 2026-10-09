from copy import deepcopy
import json
from pathlib import Path

import pytest

from musa_nowcast.error_direction import DATA
from musa_nowcast.peer_magnitude import coefficients, forecast
from musa_nowcast.prospective import sha


def test_constrained_ridge_and_shrinkage():
    assert coefficients([]) == [0, 0]
    assert coefficients([{'x': [1, 0], 'y': 26}]) == [1, 0]
    assert coefficients([{'x': [1, 0], 'y': -26}]) == [0, 0]
    assert coefficients([{'x': [1, 0], 'y': 13}]) == [.5, 0]


def test_future_outcome_invariance_and_training_cutoffs():
    records = json.loads(DATA.read_text())['records']
    target = next(r for r in records if r['company']=='MUSA' and r['quarter']=='2023Q3')
    row = forecast(target, records)
    changed = deepcopy(records)
    for r in changed:
        if r['available_at'] >= target['end']:
            r['actual_cpg'] = 999
    assert forecast(target, changed) == row
    assert 'actual_cpg' not in row
    for pair in row['training_pairs']:
        assert pair['available_at'] < row['cutoff']
        assert pair['quarter'] != target['quarter']
        for donor in pair['donors']:
            assert donor['available_at'] < pair['feature_cutoff']


def test_missing_inputs_block_instead_of_imputing():
    target = {'quarter': '2026Q3', 'start': '2026-07-01', 'end': '2026-09-30', 'prediction_cpg': 28.94}
    row = forecast(target, [])
    assert row['status'].startswith('BLOCKED')
    assert 'fitted_cpg' not in row


def test_archive_formulas_and_hashed_inputs():
    root = Path('data/peer_magnitude/2026-10-08_v1')
    result = json.loads((root/'results.json').read_text())
    assert not result['production_changed'] and not result['variant_promoted']
    assert result['groups']['modern']['n'] == 14
    assert result['groups']['modern_large']['n'] == 2
    for row in result['scored_rows']+[result['q3_2026']]:
        assert all(0 <= w <= 1 for w in row['coefficients'])
        assert row['fitted_cpg'] == pytest.approx(row['production_cpg']+sum(
            a*b for a, b in zip(row['coefficients'], row['features']['x'])))
        assert row['fixed_casy_cpg'] == pytest.approx(row['production_cpg']+.5*row['features']['x'][0])
    for i, item in enumerate(json.loads((root/'manifest.json').read_text())):
        assert sha(root/'inputs'/f'{i}_{Path(item["path"]).name}') == item['sha256']
