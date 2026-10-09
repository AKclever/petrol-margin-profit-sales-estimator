from dataclasses import replace
import json

import pytest

from musa_nowcast.anchor_reliability import ROOT
from musa_nowcast.data import load_actuals,load_weights
from musa_nowcast.deep_diagnosis import decompose
from musa_nowcast.joint_all_features import market_from_json
from musa_nowcast.model import NowcastEngine


def engine():
    market=json.loads((ROOT/'normalized_market.json').read_text())['regular']
    return NowcastEngine(market_from_json(market),load_weights('data/weights.csv'),load_actuals('data/actuals.csv'))


def test_all22_arithmetic_reproduction():
    e=engine()
    baseline={r['quarter']:r for r in json.loads((ROOT/'results.json').read_text())['baseline_rows'] if r['quarter']>='2021Q1'}
    count=0
    for index,actual in enumerate(e.actuals):
        if actual.quarter not in baseline:continue
        d=decompose(e,index);count+=1
        assert d['reconstructed_production_cpg'] == pytest.approx(baseline[actual.quarter]['prediction_cpg'],abs=1e-8)
        assert d['prior_year_anchor_cpg']+d['intercept_contribution_cpg']+sum(d['centered_feature_contributions_cpg'].values()) == pytest.approx(d['reconstructed_production_cpg'])
        assert d['shrunken_market_adjustment_cpg'] == pytest.approx(.5*d['unshrunk_model_yoy_change_cpg'])
    assert count==22


def test_heldout_actual_is_only_scoring_not_fitted():
    e=engine();index=next(i for i,a in enumerate(e.actuals) if a.quarter=='2022Q1')
    before=decompose(e,index)
    e.actuals[index]=replace(e.actuals[index],retail_margin_cpg=1000.)
    after=decompose(e,index)
    assert before['reconstructed_production_cpg']==after['reconstructed_production_cpg']
    assert before['actual_yoy_change_cpg']!=after['actual_yoy_change_cpg']


def test_counterintuitive_signs_are_preserved_not_corrected():
    e=engine()
    index=next(i for i,a in enumerate(e.actuals) if a.quarter=='2022Q1')
    d=decompose(e,index)
    assert d['centered_feature_contributions_cpg']['rising_squeeze']==pytest.approx(8.51695882094259)
    index=next(i for i,a in enumerate(e.actuals) if a.quarter=='2026Q2')
    d=decompose(e,index)
    assert d['raw_feature_slopes']['falling_capture']<0
    assert d['centered_feature_contributions_cpg']['falling_capture']==pytest.approx(-.8722274600919501)


def test_diagnosis_does_not_claim_cost_recovery_or_no_disclosure():
    r=json.load(open('data/deep_miss_diagnosis/2026-10-08_v1/diagnosis.json'))
    assert len(r['rows'])==22
    assert len(r['large_quarters'])==6
    assert len(r['ordinary_quarters'])==16
    assert r['production_changed'] is False
    assert r['confirmed_company_cost_observations']==0
    assert all(x['economic_root_cause_cents_attribution']=='UNRESOLVED' for x in r['rows'])
    q=json.load(open('data/deep_miss_diagnosis/2026-10-08_v1/new_disclosure_candidates.json'))
    assert q['original_audit_unchanged'] is True
    assert q['candidates'][0]['forecast_assimilated'] is False
