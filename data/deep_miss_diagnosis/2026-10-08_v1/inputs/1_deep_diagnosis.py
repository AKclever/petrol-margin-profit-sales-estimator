"""Source-linked model arithmetic diagnosis; never a production correction."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean

from .anchor_reliability import ROOT, tail_metrics
from .data import load_actuals, load_weights
from .joint_all_features import market_from_json
from .mathutils import RidgeModel
from .model import NowcastEngine, FEATURE_NAMES, MARKET_CHANGE_SHRINKAGE
from .pit_replay import now, save
from .prospective import sha

SPEC=Path('data/deep_miss_diagnosis_spec_v1.json')
DEEP=Path('data/accounting_miss_audit/2026-10-07_deeper_v2')
CONTROLS=Path('data/deep_miss_diagnosis/2026-10-08_controls_v1')


def decompose(engine, index):
    rows,targets=engine._training()
    prior=engine._prior_year_index(index)
    if prior is None: raise ValueError('missing prior-year anchor')
    x,y=engine._change_training(rows,targets,index)
    model=RidgeModel(engine.alpha).fit(x,y)
    delta=engine._changes(rows[index],rows[prior])
    contributions={name:MARKET_CHANGE_SHRINKAGE*c*(v-m)/s for name,c,v,m,s in
                   zip(FEATURE_NAMES,model.coefficients[1:],delta,model.means,model.scales)}
    intercept=MARKET_CHANGE_SHRINKAGE*model.coefficients[0]
    point=targets[prior]+intercept+sum(contributions.values())
    return {'reconstructed_production_cpg':point,'prior_year_anchor_cpg':targets[prior],
            'actual_yoy_change_cpg':targets[index]-targets[prior],
            'unshrunk_model_yoy_change_cpg':model.predict_one(delta),
            'shrunken_market_adjustment_cpg':point-targets[prior],
            'intercept_contribution_cpg':intercept,'centered_feature_contributions_cpg':contributions,
            'feature_deltas_cpg':dict(zip(FEATURE_NAMES,delta)),
            'raw_feature_slopes':dict(zip(FEATURE_NAMES,[c/s for c,s in zip(model.coefficients[1:],model.scales)])),
            'unshrunk_sensitivity_prediction_cpg':targets[prior]+model.predict_one(delta),
            'sensitivity_role':'MODEL_MECHANICS_ONLY_NOT_NEW_VALIDATION',
            'training_quarters':[a.quarter for a in engine.actuals[:index]],
            'weekly_cost_or_margin_observed':False}


def evaluate(output):
    output.mkdir(parents=True,exist_ok=False)
    files=[SPEC,Path(__file__),Path('musa_nowcast/model.py'),Path('musa_nowcast/mathutils.py'),
           Path('data/actuals.csv'),Path('data/weights.csv'),ROOT/'results.json',ROOT/'normalized_market.json',
           Path('data/miss_evidence/2026-10-08_v1/quarter_diagnostics.json'),
           Path('data/revenue_gap_all/2026-10-07_review_v2/quarter_rows.json'),
           Path('data/partial_quarter_disclosure_audit.csv'),DEEP/'source_checks.json',DEEP/'reviewed_findings.json',
           CONTROLS/'source_checks.json']
    (output/'inputs').mkdir()
    for i,p in enumerate(files):
        with (output/'inputs'/f'{i}_{p.name}').open('xb') as handle:handle.write(p.read_bytes())
    save(output/'input_hashes.json',{'created_at':now(),'files':[{'path':str(p),'sha256':sha(p)} for p in files]})
    source_checks=json.loads((DEEP/'source_checks.json').read_text())['source_checks']
    controls=json.loads((CONTROLS/'source_checks.json').read_text())['checks']
    verified=[]
    for source in source_checks+controls:
        if not source.get('raw_file') or not source.get('sha256'):continue
        path=(DEEP/source['raw_file']) if source in source_checks else Path(source['raw_file'])
        if sha(path)!=source['sha256']:raise ValueError('raw documentary hash mismatch')
        verified.append(source|{'raw_path':str(path),'hash_verified_at':now(),
                               'scope':'TARGETED_DOCUMENTARY_REVIEW_NOT_EXHAUSTIVE_DISCLOSURE_AUDIT'})
    save(output/'source_checks.json',{'sources':verified})
    market=market_from_json(json.loads((ROOT/'normalized_market.json').read_text())['regular'])
    engine=NowcastEngine(market,load_weights('data/weights.csv'),load_actuals('data/actuals.csv'))
    b={r['quarter']:r for r in json.loads((ROOT/'results.json').read_text())['baseline_rows'] if r['quarter']>='2021Q1'}
    inventory={r['quarter']:r for r in json.loads(files[8].read_text())['rows']}
    revenue={r['quarter']:r for r in json.loads(files[9].read_text())['rows']}
    with files[10].open(newline='') as handle:disclosures={r['quarter']:r for r in csv.DictReader(handle)}
    rows=[]; sensitivity={}
    for index,actual in enumerate(engine.actuals):
        q=actual.quarter
        if q not in b:continue
        d=decompose(engine,index)
        if abs(d['reconstructed_production_cpg']-b[q]['prediction_cpg'])>1e-8:
            raise ValueError('archived production reproduction mismatch')
        f=inventory[q]['dimensions']['timing'];r=revenue.get(q,{})
        rows.append({'quarter':q,'actual_cpg':b[q]['actual_cpg'],'production_prediction_cpg':b[q]['prediction_cpg'],
                     'actual_minus_production_cpg':b[q]['actual_cpg']-b[q]['prediction_cpg'],
                     'original_large_miss':abs(b[q]['actual_cpg']-b[q]['prediction_cpg'])>=5,
                     'model_arithmetic_status':'CONFIRMED_REPRODUCED','model_decomposition':d,
                     'market_path':{k:v for k,v in f.items() if k!='source_candidates'},
                     'company_revenue_gap_cpg':r.get('revenue_proxy_error_cpg'),
                     'revenue_gap_is_pure_price_difference':False,
                     'disclosure_audit_state':disclosures[q]['audit_status'],
                     'economic_root_cause_cents_attribution':'UNRESOLVED',
                     'release_source':{'source_url':inventory[q]['source_url'],'sha256':inventory[q]['source_sha256'],
                                       'available_at':inventory[q]['source_available_at']}})
        sensitivity[q]=b[q]|{'prediction_cpg':d['unshrunk_sensitivity_prediction_cpg']}
    qs=sorted(b);large=[r['quarter'] for r in rows if r['original_large_miss']];ordinary=[q for q in qs if q not in large]
    def comparison(group):
        selected=[r for r in rows if r['quarter'] in group]
        return {'n':len(group),'mean_volatility_cpg':mean(r['market_path']['volatility_cpg'] for r in selected),
                'mean_abs_revenue_gap_cpg':mean(abs(r['company_revenue_gap_cpg']) for r in selected if r['company_revenue_gap_cpg'] is not None),
                'positive_rising_squeeze_slope_count':sum(r['model_decomposition']['raw_feature_slopes']['rising_squeeze']>0 for r in selected),
                'negative_falling_capture_slope_count':sum(r['model_decomposition']['raw_feature_slopes']['falling_capture']<0 for r in selected)}
    result={'created_at':now(),'role':'RETROSPECTIVE_DOCUMENTARY_AND_MODEL_ARITHMETIC_DIAGNOSIS',
            'production_changed':False,'model_fitted_for_new_forecasts':False,'all_22_predictions_reproduced':True,
            'rows':rows,'large_quarters':large,'ordinary_quarters':ordinary,
            'group_context':{'large':comparison(large),'ordinary':comparison(ordinary)},
            'unshrunk_sensitivity_all22':tail_metrics(b,sensitivity,qs),
            'unshrunk_sensitivity_original_large':tail_metrics(b,sensitivity,large),
            'unshrunk_sensitivity_original_ordinary':tail_metrics(b,sensitivity,ordinary),
            'disclosure_audit_not_changed':True,'confirmed_company_cost_observations':0,
            'supplier_cost_backsolved_from_actual_margin':False}
    save(output/'diagnosis.json',result)
    print(json.dumps({k:result[k] for k in ['group_context','unshrunk_sensitivity_all22','unshrunk_sensitivity_original_large','unshrunk_sensitivity_original_ordinary']},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    evaluate(parser.parse_args().out)
