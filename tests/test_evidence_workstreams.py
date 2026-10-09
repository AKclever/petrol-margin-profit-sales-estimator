from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from musa_nowcast.evidence_intake import validate_panel, primary_eligible
from scripts.expand_older_peer_evidence import caseys_target


def test_manual_panel_missing_identities_and_scraping_blocked():
    with pytest.raises(ValueError,match='No verified'):
        validate_panel({'collection_mode':'MANUAL_ONLY','pairs':[]})
    with pytest.raises(ValueError,match='permission'):
        validate_panel({'collection_mode':'AUTOMATIC','pairs':[]})


def cp(created, coverage=1, risk=None):
    return {'evaluation_role':'PROSPECTIVE_CAPTURE','quarter':'2026Q4','forecast_created_at':created,
            'production_forecast':{'coverage':coverage},'regime_risk_state':risk or {'overall_risk':'NORMAL'}}


def test_primary_capture_window_no_hindsight_selection():
    assert not primary_eligible(cp('2027-01-02T23:59:59Z'))
    assert primary_eligible(cp('2027-01-03T00:00:00Z'))
    assert primary_eligible(cp('2027-01-07T23:59:59Z'))
    assert not primary_eligible(cp('2027-01-08T00:00:00Z'))
    assert not primary_eligible(cp('2027-01-04T00:00:00Z',coverage=.9))
    r=cp('2027-01-04T00:00:00Z');r['evaluation_role']='RETROSPECTIVE_MECHANICAL_REPLAY'
    assert not primary_eligible(r)


def test_caseys_quarter_achieved_not_annual_goal_or_merchandise():
    raw=b'<p>Fuel - The annual goal is an average margin of 15.3 cents per gallon. For the third quarter, same-store gallons sold rose 2.2% with an average margin of 22.0 cents per gallon. Renewable fuel credits were sold.</p><p>Grocery and Other Merchandise - margin 32.0%</p>'
    r=caseys_target(raw)
    assert r['reported_margin_cpg']==22
    assert 'RIN' in r['target_basis']
    assert r['usable_for_new_forecast_model'] is False


def test_all_quarter_inventory_is_not_a_causal_or_absence_claim():
    r=json.loads(Path('data/miss_evidence/2026-10-08_v1/quarter_diagnostics.json').read_text())
    assert len(r['rows'])==52
    assert all(len(v['dimensions'])==4 for v in r['rows'])
    assert all(v['causal_explanation']=='UNRESOLVED' for v in r['rows'])
    assert r['summary']['confirmed_causal_retail_adjustments']==0


def test_older_peer_source_cutoffs_for_all_original_misses():
    r=json.loads(Path('data/older_peer_evidence/2026-10-08_review_v4/review.json').read_text())
    from musa_nowcast.history_floor_basis import bounds
    for row in r['original_big_miss_peer_evidence']:
        end=str(bounds(row['quarter'])[1])
        for name in ['caseys','couchetard']:
            assert row[name] is not None
            assert row[name]['available_at']<end
    assert r['production_changed'] is False


def test_disclosure_queue_never_auto_assimilates_prior_actuals():
    r=json.loads(Path('data/miss_evidence/2026-10-08_v1/live_disclosure_review_queue.json').read_text())
    assert all(v['numeric_assimilation_authorized'] is False for v in r['rows'])
    assert all(v['negative_disclosure_conclusion_authorized'] is False for v in r['rows'])
