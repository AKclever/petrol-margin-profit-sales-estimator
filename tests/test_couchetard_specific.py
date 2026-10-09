from copy import deepcopy
import json
from pathlib import Path

import pytest

from musa_nowcast.couchetard_specific import HISTORY, anchor_forecast, prior_label

ARCHIVE=Path('data/couchetard_specific/2026-10-08_evaluation_v1')


def inputs():
    h=json.loads(HISTORY.read_text())
    return ({r['quarter']:r for r in h['histories']['ATD']},
            {r['quarter']:r for r in h['peer_predictions']['ATD']})


def test_fiscal_anchor_not_calendar_month():
    assert prior_label('F2027Q1')=='F2026Q1'
    records,baseline=inputs()
    f,reason=anchor_forecast(records['F2027Q1'],records,baseline['F2027Q1'])
    assert reason is None
    assert f['prediction_cpg']==pytest.approx(baseline['F2027Q1']['prediction_cpg']+f['anchor_offset_cpg'])
    assert f['recent_level_seasonal_cpg']+f['market_adjustment_cpg']==pytest.approx(f['prediction_cpg'])


def test_own_target_does_not_change_recent_anchor():
    records,baseline=inputs();q='F2025Q2'
    first,_=anchor_forecast(records[q],records,baseline[q])
    changed=deepcopy(records);changed[q]['retail_margin_cpg']=999
    last,_=anchor_forecast(changed[q],changed,baseline[q])
    assert first==last


def test_not_yet_published_values_are_ignored():
    records,baseline=inputs();q='F2025Q2'
    first,_=anchor_forecast(records[q],records,baseline[q])
    changed=deepcopy(records)
    for row in changed.values():
        if row['available_at']>=records[q]['end']:
            row['retail_margin_cpg']=999
    last,_=anchor_forecast(changed[q],changed,baseline[q])
    assert first==last


def test_same_day_prior_release_is_not_eligible():
    records,baseline=inputs();q='F2025Q2'
    changed=deepcopy(records)
    changed['F2024Q2']['available_at']=records[q]['end']
    f,reason=anchor_forecast(changed[q],changed,baseline[q])
    assert f is None and reason=='MISSING_PUBLISHED_FISCAL_ANCHOR'


def test_archive_sample_and_publication_trail():
    results=json.loads((ARCHIVE/'results.json').read_text())
    assert len(results['rows'])==42
    assert len(results['groups']['2021_onward_start']['quarters'])==22
    assert not results['production_changed'] and not results['strict_market_pit_verified']
    assert not results['groups']['all']['metrics']['passes_pre_registered_gate']
    for row in results['rows']:
        assert len(row['change_pairs'])==4
        for pair in row['change_pairs']:
            assert pair['current_available_at']<row['information_cutoff']
            assert pair['prior_available_at']<row['information_cutoff']
            assert pair['quarter']!=row['quarter']
    audit=json.loads((ARCHIVE/'evidence_audit.json').read_text())
    assert len(audit['quarters'])==50
    assert not audit['geographic_weights_changed']
    assert all(r['margin_adjustment_cpg'] is None for r in audit['quarters'])
    assert 'affiliated stores' in audit['footprint_evidence']
