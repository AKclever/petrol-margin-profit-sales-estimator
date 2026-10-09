from copy import deepcopy
import json
from pathlib import Path

import pytest

from musa_nowcast.error_probability import fit_probability, forecast, scoring
from musa_nowcast.prospective import sha

ROOT = Path('data/error_probability/2026-10-08_v1')


def test_history_and_class_requirements():
    assert fit_probability([], [0])['status'].startswith('BLOCKED')
    assert fit_probability([{'x':[0], 'y':0}]*8,[0])['status'].startswith('BLOCKED')
    pairs = [{'x':[0], 'y':i%2} for i in range(8)]
    row = fit_probability(pairs,[0])
    assert row['probability'] == row['base_probability'] == .5
    assert row['coefficients'] == [0]


def test_future_outcomes_do_not_affect_frozen_prediction():
    inputs = json.loads((ROOT/'frozen_features.json').read_text())
    records = json.loads((ROOT/'inputs/0_dataset.json').read_text())['records']
    outcomes = {r['quarter']:r for r in records if r['company']=='MUSA'}
    target = next(r for r in inputs if r['quarter']=='2023Q3')
    original = forecast(target,inputs,outcomes)
    changed = deepcopy(outcomes)
    for r in changed.values():
        if r['available_at']>=target['cutoff']:
            r['actual_cpg']=999
    assert forecast(target,inputs,changed) == original


def test_publication_cutoffs_and_joint_probability_sum():
    frozen = json.loads((ROOT/'frozen_predictions.json').read_text())
    for row in frozen['historical']+[frozen['q3_2026']]:
        assert 'actual_cpg' not in row
        for name in ('direction','tail'):
            for prior in row[name+'_training']:
                assert prior['available_at']<row['cutoff']
                assert prior['quarter']!=row['quarter']
        if 'three_state_independence_approximation' in row:
            assert sum(row['three_state_independence_approximation'].values()) == pytest.approx(1)


def test_archive_negative_findings_and_hashes():
    result = json.loads((ROOT/'results.json').read_text())
    assert not result['production_changed']
    assert not result['probability_calibrated']
    assert not result['promoted']
    assert result['groups']['modern']['direction']['n']==14
    assert result['groups']['modern']['tail']['n']==13
    tail = result['groups']['modern_large']['tail']
    assert tail['model']['brier']>tail['base_rate']['brier']
    for i,item in enumerate(json.loads((ROOT/'manifest.json').read_text())):
        assert sha(ROOT/'inputs'/f'{i}_{Path(item["path"]).name}')==item['sha256']


def test_brier_and_logloss_identity():
    rows = [{'actual_cpg':1,'production_cpg':0,
             'direction':{'status':'EXPLORATORY','probability':.5,'base_probability':.5}}]
    result = scoring(rows,'direction')
    assert result['model']['brier']==.25
    assert result['model']==result['base_rate']
