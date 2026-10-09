from copy import deepcopy
import json
from pathlib import Path

import pytest

from musa_nowcast.earnings_event_replay import BASES, checkpoint, ingest, load_archive, select, update, validate
from musa_nowcast.prospective import sha

ARCHIVE=Path('data/earnings_event_replay/2026-10-08_v3')


def test_own_and_future_outcomes_do_not_change_checkpoint():
    records=load_archive();target=next(r for r in records if r['company']=='MUSA' and r['quarter']=='2023Q3')
    cutoff=target['available_at'];first=checkpoint(target,records,cutoff)
    changed=deepcopy(records)
    for r in changed:
        if r['available_at']>=cutoff:r['actual_cpg']=999
    last=checkpoint(target,changed,cutoff)
    assert first==last


def test_donor_publication_and_period_overlap():
    records=load_archive();target=next(r for r in records if r['company']=='MUSA' and r['quarter']=='2023Q3')
    donor=select(target,'ATD',records,target['available_at'])
    assert donor['available_at']<target['available_at']
    assert select(target,'ATD',[donor],donor['available_at']) is None
    no_overlap=donor|{'start':'2010-01-01','end':'2010-03-31'}
    assert select(target,'ATD',[no_overlap],target['available_at']) is None


def test_forecasts_never_before_market_period_and_no_compounding():
    records=load_archive();target=next(r for r in records if r['company']=='MUSA' and r['quarter']=='2023Q3')
    with pytest.raises(ValueError,match='BASELINE_NOT_AVAILABLE'):
        checkpoint(target,records,target['end'])
    first=checkpoint(target,records,target['available_at'])
    assert first==checkpoint(target,records,target['available_at'])
    assert first['prediction_cpg']==pytest.approx(target['prediction_cpg']+first['correction_cpg'])


def test_target_basis_and_nonfinite_guard():
    r=load_archive()[0]
    with pytest.raises(ValueError,match='TARGET_BASIS'):validate(r|{'target_basis':'ALL_IN'})
    with pytest.raises(ValueError,match='NONFINITE'):validate(r|{'actual_cpg':float('nan')})


def test_ingestion_idempotent_hash_checked_and_conflicts_blocked(tmp_path):
    r=load_archive()[0];raw=tmp_path/'raw.html';raw.write_text('original source fixture')
    event=r|{'raw_source_path':str(raw),'source_sha256':sha(raw),'captured_at':'2026-10-08T12:00:00Z'}
    path=tmp_path/'event.json';path.write_text(json.dumps(event));ledger=tmp_path/'events.jsonl'
    assert ingest(ledger,path)=='APPENDED'
    assert ingest(ledger,path)=='ALREADY_ARCHIVED'
    assert len(ledger.read_text().splitlines())==1
    path.write_text(json.dumps(event|{'actual_cpg':999}))
    with pytest.raises(ValueError,match='CONFLICTING'):ingest(ledger,path)
    raw.write_text('changed source')
    with pytest.raises(ValueError,match='HASH_MISMATCH'):ingest(ledger,path)


def test_update_creates_immutable_research_checkpoint(tmp_path):
    records=load_archive();dataset=tmp_path/'dataset.json';dataset.write_text(json.dumps({'records':records}))
    ledger=tmp_path/'empty.jsonl';ledger.write_text('')
    checkpoints=update(dataset,ledger,'2023-10-01',tmp_path/'run')
    assert checkpoints
    assert all(r['information_cutoff']=='2023-10-01' for r in checkpoints)
    with pytest.raises(FileExistsError):update(dataset,ledger,'2023-10-01',tmp_path/'run')


def test_archived_loading_training_no_leakage():
    data=json.loads((ARCHIVE/'frozen_checkpoints.json').read_text())
    results=json.loads((ARCHIVE/'results.json').read_text())
    assert results['event_count']==101
    assert len(results['rows'])==128
    assert not results['production_changed'] and not results['strict_market_pit_verified']
    for c in data['checkpoints']:
        for transfer in c['transfers']:
            assert transfer['donor_available_at']<c['information_cutoff']
            assert 0<=transfer['loading']<=1
            assert len(transfer['training_pairs'])>=8
            for pair in transfer['training_pairs']:
                assert pair['recipient_quarter']!=c['quarter']
                assert pair['donor_available_at']<pair['recipient_available_at']<c['information_cutoff']
    assert all(not g['all_metrics']['passes_pre_registered_gate'] for g in results['groups'].values())
