import json
from pathlib import Path

import pytest

from musa_nowcast.earnings_event_replay import BASES
from musa_nowcast.expanded_peer_evidence import normalize, usable_before
from musa_nowcast.prospective import sha

ROOT = Path('data/expanded_peer_evidence/2026-10-08_review_v2')


def test_date_only_cutoff_is_strict_and_validated():
    assert usable_before('2025-05-08', '2025-07-30')
    assert not usable_before('2025-07-30', '2025-07-30')
    assert not usable_before('2025-08-06', '2025-07-30')
    assert not usable_before(None, '2025-07-30')
    with pytest.raises(ValueError):
        usable_before('yesterday', '2025-07-30')


def test_ambiguous_and_wrong_basis_targets_block():
    with pytest.raises(ValueError, match='SOURCE_NOT_CAPTURED'):
        normalize({'status':'CAPTURE_FAILED'})
    with pytest.raises(ValueError, match='AMBIGUOUS'):
        normalize({'status':'RAW_CAPTURED','company':'ARKO','tables':[], 'text':''})
    with pytest.raises(ValueError, match='NOT_A_DIRECT'):
        normalize({'status':'RAW_CAPTURED','company':'MPC','tables':[], 'text':''})


def test_captured_hashes_and_target_definitions():
    d = json.loads((ROOT/'reviewed_evidence.json').read_text())
    assert len(d['targets']) == 10
    assert not d['production_changed']
    capl = next(r for r in d['targets'] if r['company']=='CAPL' and r['quarter']=='2026Q2')
    assert capl['actual_cpg'] == pytest.approx(51.3)
    assert capl['combined_retail_segment_cpg'] == pytest.approx(49.2)
    assert capl['wholesale_cpg'] == pytest.approx(11.1)
    for item in d['source_manifests']:
        assert sha(Path(item['path'])) == item['sha256']
        path = Path(item['path'])
        for c in json.loads(path.read_text())['checks']:
            if c['status']=='RAW_CAPTURED':
                assert sha(path.parent/c['raw_file']) == c['sha256']
    for r in d['targets']:
        assert r['end'] < r['available_at']
        assert not r['historical_vintage_verified']


def test_guidance_is_prior_evidence_not_musa_target():
    d = json.loads((ROOT/'reviewed_evidence.json').read_text())
    assert len(d['guidance_checks']) == 3
    assert sum(r['within_range'] for r in d['guidance_checks']) == 2
    for r in d['guidance_checks']:
        assert r['midpoint_abs_error_cpg'] == pytest.approx(abs(r['eventual_actual_cpg']-r['midpoint_cpg']))
        assert r['usable_before_musa_report']
        assert r['interpretation'] == 'OWN_COMPANY_EBITDA_ASSUMPTION_NOT_MUSA_GUIDANCE'


def test_evidence_pool_does_not_expand_forecast_universe():
    assert set(BASES) == {'MUSA','CASY','ATD'}
    policy = json.loads(Path('data/expanded_peer_company_policy_v1.json').read_text())
    assert set(policy['companies']) == {'ARKO','CAPL','GLP','MPC','ET','AROC','LBRT'}
    assert not policy['production_changed']
    assert policy['companies']['AROC']['role'] == 'EXCLUDED_RETAIL_PEER'
    assert policy['companies']['LBRT']['role'] == 'EXCLUDED_RETAIL_PEER'
