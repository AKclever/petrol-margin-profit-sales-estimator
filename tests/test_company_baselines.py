from copy import deepcopy
import json
from pathlib import Path

import pytest

from musa_nowcast.company_baselines import forecast, metrics
from musa_nowcast.company_evidence_ledger import append_event, eligible_events, read_ledger
from musa_nowcast.prospective import sha

ROOT=Path('data/company_baselines/2026-10-08_evaluation_v3')


def test_ledger_idempotent_conflict_and_tamper(tmp_path):
    event=read_ledger(ROOT/'events.jsonl')[0]
    ledger=tmp_path/'events.jsonl'
    assert append_event(ledger,event)=='APPENDED'
    assert append_event(ledger,event)=='ALREADY_ARCHIVED'
    with pytest.raises(ValueError,match='CONFLICTING'):
        append_event(ledger,event|{'actual_cpg':999})
    envelope=json.loads(ledger.read_text())
    envelope['event']['actual_cpg']=999
    ledger.write_text(json.dumps(envelope)+'\n')
    with pytest.raises(ValueError,match='CHAIN_INVALID'):
        read_ledger(ledger)


def test_same_day_events_excluded_and_annual_guidance_not_training():
    events=read_ledger(ROOT/'events.jsonl')
    event=next(e for e in events if e['company']=='ARKO' and e['kind']=='GUIDANCE' and e['quarter']=='2026FY')
    assert event['period_scope']=='FULL_YEAR_NOT_Q3'
    assert event not in eligible_events(events,event['available_at'])
    assert event in eligible_events(events,'2026-08-08','ARKO')
    target=next(t for t in json.loads((ROOT/'reviewed_targets.json').read_text())['targets']
                if t['company']=='ARKO' and t['quarter']=='2026Q2')
    assert '2026FY' not in forecast(target,events)['training_quarters']


def test_own_future_actual_and_wrong_basis_do_not_change_forecast():
    events=read_ledger(ROOT/'events.jsonl')
    target=next(t for t in json.loads((ROOT/'reviewed_targets.json').read_text())['targets']
                if t['company']=='ARKO' and t['quarter']=='2025Q2')
    before=forecast(target,events)
    altered=deepcopy(events)
    for e in altered:
        if e['available_at']>=target['end'] and e['kind']=='ACTUAL_MARGIN':
            e['actual_cpg']=999
    assert forecast(target|{'actual_cpg':999},altered)==before
    wrong=events[0]|{'company':'ARKO','available_at':'2024-01-01','end':'2023-09-30',
                     'target_basis':'ALL_IN','quarter':'2023Q3','actual_cpg':999}
    assert forecast(target,events+[wrong])==before


def test_prediction_archive_and_scoring_match():
    result=json.loads((ROOT/'results.json').read_text())
    forecasts=json.loads((ROOT/'frozen_predictions.json').read_text())['forecasts']
    assert len(forecasts)==12
    assert all('actual_cpg' not in r for r in forecasts)
    for r in forecasts:
        assert len(r['training_quarters'])>=8
        assert all(d<r['information_cutoff'] for d in r['training_available_at'])
        assert r['blend_cpg']==pytest.approx(.5*(r['seasonal_cpg']+r['recent_cpg']))
    assert not result['production_changed'] and not result['automatic_promotion']
    assert not result['strict_historical_vintage_verified']
    for company,group in result['groups'].items():
        scored=[r for r in result['scored_rows'] if r['company']==company]
        assert len(scored)==6
        for model in ['seasonal','recent','blend']:
            assert metrics(scored,model)==group[model]


def test_frozen_snapshot_hashes_and_five_company_pool():
    events=read_ledger(ROOT/'events.jsonl')
    assert {e['company'] for e in events}=={'MUSA','CASY','ATD','ARKO','CAPL'}
    for i,row in enumerate(json.loads((ROOT/'frozen_inputs.json').read_text())):
        path=ROOT/'inputs'/f'{i}_{Path(row["path"]).name}'
        assert sha(path)==row['sha256']


def test_short_history_blocks():
    events=read_ledger(ROOT/'events.jsonl')
    target=json.loads((ROOT/'reviewed_targets.json').read_text())['targets'][0]
    assert forecast(target,events[:2]) is None
