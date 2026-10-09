import copy
import json
from pathlib import Path

from musa_nowcast.combined_challengers import crosses_diesel_break, joint
from musa_nowcast.joint_all_features import SPEC, groups

ROOT = Path('data/joint_all_features/2026-10-08_v1')


def test_joint_features_width_and_frozen_order():
    spec = json.loads(SPEC.read_text())
    rows = json.loads((ROOT/'frozen_feature_rows.json').read_text())
    assert rows['feature_names'] == spec['feature_order']
    assert len(spec['feature_order']) == 16
    assert len(rows['rows']) == 15
    assert all(len(r['features']) == 16 for r in rows['rows'])


def test_all_feature_input_evidence_cutoffs():
    rows = json.loads((ROOT/'frozen_feature_rows.json').read_text())['rows']
    for r in rows:
        assert not crosses_diesel_break(r['quarter'])
        evidence = r['feature_evidence']; cutoff = r['quarter_end']
        assert evidence['gap_available_at'] < cutoff
        assert all(p['available_at'] < cutoff for p in evidence['peers'].values())
        assert all(d < cutoff for d in evidence['floor']['input_available_at'])


def test_all_feature_heldout_actual_and_future_features_do_not_affect_prediction():
    rows = json.loads((ROOT/'frozen_feature_rows.json').read_text())['rows']
    first = joint(rows)[0]['2024Q4']['prediction_cpg']
    changed = copy.deepcopy(rows)
    for r in changed:
        if r['quarter'] >= '2024Q4':
            r['actual_cpg'] += 100
        if r['quarter'] > '2024Q4':
            r['features'] = [999]*16
    assert joint(changed)[0]['2024Q4']['prediction_cpg'] == first


def test_big_miss_coverage_keeps_unscored_null():
    result = json.loads((ROOT/'results.json').read_text())
    assert result['production_changed'] is False
    assert result['tail_edge_demonstrated'] is False
    assert len(result['big_miss_coverage']) == 6
    scored = [r for r in result['big_miss_coverage'] if r['status'] == 'SCORED']
    assert [r['quarter'] for r in scored] == ['2026Q2']
    assert all(r['joint_prediction_cpg'] is None and r['joint_abs_error_cpg'] is None
               for r in result['big_miss_coverage'] if r['status'] == 'BLOCKED')


def test_group_definition_not_chosen_from_challenger_errors():
    baseline = {'2025Q1':{'actual_cpg':10,'prediction_cpg':9},'2025Q2':{'actual_cpg':20,'prediction_cpg':10}}
    shadow = {'2025Q1':{'actual_cpg':10,'prediction_cpg':0},'2025Q2':{'actual_cpg':20,'prediction_cpg':20}}
    g = groups(baseline,shadow,['2025Q1'])
    assert g['original_big_misses']['quarters'] == ['2025Q1']
    assert g['other_eligible_quarters']['quarters'] == ['2025Q2']
