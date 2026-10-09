from copy import deepcopy
import json
from pathlib import Path

from musa_nowcast.error_direction import DATA, predictions, score, sign
from musa_nowcast.prospective import sha

ROOT = Path('data/error_direction/2026-10-08_v1')


def test_sign_and_missing_evidence_abstain():
    assert sign(0) == sign(1e-11) == 'ABSTAIN'
    assert sign(1) == 'ABOVE'
    assert sign(-1) == 'BELOW'
    target = {'quarter': '2023Q3', 'start': '2023-07-01', 'end': '2023-09-30', 'prediction_cpg': 30}
    row = predictions(target, [])
    assert all(x['call'] == 'ABSTAIN' for x in row['signals'].values())


def test_target_and_future_outcomes_cannot_change_call():
    records = json.loads(DATA.read_text())['records']
    target = next(r for r in records if r['company'] == 'MUSA' and r['quarter'] == '2023Q3')
    original = predictions(target, records)
    changed = deepcopy(records)
    for r in changed:
        if r['available_at'] >= target['end']:
            r['actual_cpg'] = 999
    assert predictions(target, changed) == original
    assert 'actual_cpg' not in original


def test_same_day_publication_is_excluded():
    records = json.loads(DATA.read_text())['records']
    target = next(r for r in records if r['company'] == 'MUSA' and r['quarter'] == '2023Q3')
    row = predictions(target, records)
    donor = next(r for r in records if r['company'] == 'CASY' and r['quarter'] == row['signals']['CASY']['quarter'])
    same_day = donor | {'available_at': target['end']}
    assert predictions(target, [same_day])['signals']['CASY']['call'] == 'ABSTAIN'


def test_scoring_uses_identical_called_rows_and_balanced_accuracy():
    rows = [{'actual_direction': a, 'historical_majority': m, 'signals': {'CASY': {'call': c}}}
            for a, m, c in [('ABOVE', 'ABOVE', 'ABOVE'), ('ABOVE', 'ABSTAIN', 'BELOW'),
                            ('BELOW', 'ABOVE', 'BELOW'), ('BELOW', 'BELOW', 'ABSTAIN')]]
    result = score(rows, 'CASY')
    assert result['calls'] == 3
    assert result['correct'] == 2
    assert result['coverage'] == .75
    assert result['balanced_accuracy'] == .75
    assert result['historical_majority_calls'] == 2
    assert result['signal_accuracy_on_majority_coverage'] == 1


def test_frozen_archive_and_cutoffs():
    result = json.loads((ROOT/'results.json').read_text())
    frozen = json.loads((ROOT/'frozen_predictions.json').read_text())
    assert len(frozen) == 44
    assert not result['production_changed']
    assert not result['probability_calibrated']
    assert not result['automatic_adjustment']
    assert result['groups']['modern']['CASY']['correct'] == 15
    assert result['groups']['modern']['ATD']['correct'] == 16
    assert result['groups']['modern_large']['CASY']['calls'] == 6
    for row in frozen:
        assert 'actual_cpg' not in row
        for source in row['prior_residual_training']:
            assert source['available_at'] < row['cutoff']
            assert source['quarter'] != row['quarter']
        for company in ['CASY', 'ATD']:
            signal = row['signals'][company]
            if 'available_at' in signal:
                assert signal['available_at'] < row['cutoff']
    for i, item in enumerate(json.loads((ROOT/'manifest.json').read_text())):
        assert sha(ROOT/'inputs'/f'{i}_{Path(item["path"]).name}') == item['sha256']
