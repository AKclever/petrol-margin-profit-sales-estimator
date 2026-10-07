import importlib.util
from pathlib import Path


def test_candidate_offsets_match_evidence_without_claiming_adjustment():
    path=Path('scripts/capture_deeper_accounting.py')
    spec=importlib.util.spec_from_file_location('deeper',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text='A retail margin is reported. Inventory timing affected supply, not retail. End.'
    matches=module.candidates(text)
    assert matches
    assert all(text[r['start_offset']:r['end_offset']]==r['text'] for r in matches)


def test_reviewed_supply_bridge_not_a_retail_adjustment():
    import json
    import pytest
    path=Path('data/accounting_miss_audit/2026-10-07_deeper_v2/reviewed_findings.json')
    if not path.exists():pytest.skip('local reviewed research archive not installed')
    data=json.loads(path.read_text())
    c=data['q2_2026_supply_components_cpg']
    assert round(c['controllable_including_rins']+c['uncontrollable_inventory_exposure']+c['terminal_and_wholesale'],2)==c['total_supply']
    assert all(r['retail_adjustment_cpg'] is None for r in data['reviewed_quarters'])
    assert data['production_changed'] is False
