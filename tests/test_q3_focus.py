from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest

from musa_nowcast.data import load_actuals, load_market, load_weights
from musa_nowcast.model import NowcastEngine
from musa_nowcast.prospective import sha
from musa_nowcast.q3_focus import fixed_peer_shadow

ROOT=Path('data/q3_focus/2026-10-08_v3')


def test_focused_snapshot_scope_and_no_production_change():
    r=json.loads((ROOT/'results.json').read_text())
    assert not r['production_changed']
    assert r['frozen_official_forecast']['retail_margin_cpg']==29.54
    assert r['refreshed_frozen_method_forecast']['retail_margin_cpg']==28.94
    assert len(r['weekly_path'])==12
    assert r['weekly_path'][-1]['week']=='2026-09-21'
    assert r['management_evidence']['period']=='SECOND_HALF_2026'
    assert r['management_evidence']['basis']=='ALL_IN'
    assert not r['management_evidence']['usable_retail_anchor']


def test_peer_fixed_formula_and_future_publications_excluded():
    records=json.loads(Path('data/peer_surprise/2026-10-07_v2/result.json').read_text())['peer_predictions']
    donor=records[-1]|{'company':'CASY','source_url':records[-1]['source']['url'],
                      'source_sha256':records[-1]['source']['sha256']}
    result=fixed_peer_shadow(28.94,[donor])
    expected=.5*(31/92)*(47.8-42.70206011891245)
    assert result['correction_cpg']==pytest.approx(expected)
    assert result['retail_margin_cpg']==pytest.approx(28.94+expected)
    assert fixed_peer_shadow(28.94,[donor|{'available_at':'2026-10-08'}])['status'].startswith('BLOCKED')


def test_quarter_boundary_excludes_cross_october_week():
    engine=NowcastEngine(load_market(ROOT/'market.csv'),load_weights(Path('data/weights.csv')),
                         load_actuals(Path('data/actuals.csv')))
    assert any(row.week==date(2026,9,28) for row in engine.market)
    basket=engine._weekly_basket(date(2026,7,1),date(2026,9,30),date(2026,10,8))
    assert len(basket)==12 and basket[-1][0]==date(2026,9,21)


def test_raw_snapshots_and_supply_bridge():
    for row in json.loads((ROOT/'manifest.json').read_text()):
        assert sha(Path(row['path']))==row['sha256']
    r=json.loads((ROOT/'results.json').read_text())['refreshed_frozen_method_forecast']
    assert r['all_in_base_cpg']==pytest.approx(r['retail_margin_cpg']+r['supply_rin_base_cpg'])
