from copy import deepcopy
import json

from musa_nowcast.error_direction import DATA
from musa_nowcast.peer_consensus import consensus_call, forecast


def test_missing_disagreement_and_filter_boundaries():
    signals = {c: {'call': 'ABOVE', 'overlap_fraction': .5, 'surprise_cpg': 2}
               for c in ('CASY', 'ATD')}
    assert consensus_call(signals, True, True) == 'ABOVE'
    signals['ATD']['overlap_fraction'] = .499
    assert consensus_call(signals, True) == 'ABSTAIN'
    assert consensus_call(signals, False, True) == 'ABOVE'
    signals['ATD']['surprise_cpg'] = 1.999
    assert consensus_call(signals, False, True) == 'ABSTAIN'
    signals['ATD']['call'] = 'BELOW'
    assert consensus_call(signals) == 'ABSTAIN'
    signals['ATD'] = {'call': 'ABSTAIN'}
    assert consensus_call(signals, True, True) == 'ABSTAIN'


def test_future_outcomes_do_not_change_consensus():
    records = json.loads(DATA.read_text())['records']
    target = next(r for r in records if r['company'] == 'MUSA' and r['quarter'] == '2023Q3')
    before = forecast(target, records)
    changed = deepcopy(records)
    for row in changed:
        if row['available_at'] >= target['end']:
            row['actual_cpg'] = 999
    assert forecast(target, changed) == before
    assert 'actual_direction' not in before


def test_same_rows_consensus_cannot_outperform_agreeing_individuals():
    records = json.loads(DATA.read_text())['records']
    for target in [r for r in records if r['company'] == 'MUSA']:
        row = forecast(target, records)
        call = row['signals']['consensus']['call']
        if call != 'ABSTAIN':
            assert call == row['signals']['CASY']['call'] == row['signals']['ATD']['call']


def test_archive_preserves_negative_results_and_no_promotion():
    from pathlib import Path
    from musa_nowcast.prospective import sha
    root = Path('data/peer_consensus/2026-10-08_v1')
    result = json.loads((root/'results.json').read_text())
    modern = result['groups']['modern']
    assert modern['consensus']['consensus']['correct'] == 12
    assert modern['consensus']['consensus']['calls'] == 15
    assert modern['strength_only']['consensus']['correct'] == 7
    assert modern['strength_only']['consensus']['calls'] == 10
    assert modern['overlap_only']['consensus']['calls'] == 0
    assert result['variant_promoted'] is None
    assert not result['production_changed']
    for i, item in enumerate(json.loads((root/'manifest.json').read_text())):
        assert sha(root/'inputs'/f'{i}_{Path(item["path"]).name}') == item['sha256']
