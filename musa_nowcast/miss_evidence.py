"""Descriptive source-level miss audit; no causal labels inferred from keywords."""
import argparse
import json
from pathlib import Path
import re

from .data import load_weights
from .history_floor_basis import OLD, MODERN, bounds
from .joint_all_features import market_from_json
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .revenue_gap_audit import rows_from_html, LARGE_MISS_QUARTERS

SPEC=Path('data/miss_evidence_workstream_spec_v1.json')
HISTORY=Path('data/history_floor_basis/2026-10-07_evaluation_v6')
AUDIT=Path('data/revenue_gap_all/2026-10-07_review_v2/quarter_rows.json')


def candidates(text, pattern):
    return list(dict.fromkeys(text[max(0,m.start()-140):min(len(text),m.end()+220)]
                             for m in re.finditer(pattern,text,re.I)))[:12]


def audit(output):
    output.mkdir(parents=True,exist_ok=False)
    targets=json.loads((HISTORY/'historical_targets.json').read_text())['quarters']
    b={r['quarter']:r for r in json.loads((HISTORY/'results.json').read_text())['baseline_rows']}
    revenue={r['quarter']:r for r in json.loads(AUDIT.read_text())['rows']}
    engine=NowcastEngine(market_from_json(json.loads((HISTORY/'normalized_market.json').read_text())['regular']),load_weights('data/weights.csv'),[])
    save(output/'specification.json',json.loads(SPEC.read_text()))
    inputs=[SPEC,AUDIT,HISTORY/'historical_targets.json',HISTORY/'results.json',HISTORY/'normalized_market.json',Path(__file__)]
    save(output/'input_hashes.json',{'captured_at':now(),'files':[{'path':str(p),'sha256':sha(p)} for p in inputs]})
    rows=[]
    for target in targets:
        q=target['quarter'];path=OLD/f'{q}_release.html' if q<'2019Q1' else MODERN/f'sources/{q}_release.html'
        if sha(path)!=target['source_sha256']:raise ValueError('Source hash changed')
        tree,_=rows_from_html(path.read_bytes());text=' '.join(tree.text_content().split())
        start,end=bounds(q);f=engine.features(start,end)
        rev=revenue.get(q,{})
        dimensions={
            'company_selling_price':{'revenue_gap_cpg':rev.get('revenue_proxy_error_cpg'),
                'direct_same_store_growth_percent':rev.get('reported_same_store_gallon_growth_percent'),
                'interpretation':'DESCRIPTIVE_MIX_TAX_GEOGRAPHY_CONFOUNDED_NOT_DIRECT_PUMP_DISCOUNT',
                'status':'REVENUE_PROXY_AVAILABLE' if rev.get('revenue_proxy_error_cpg') is not None else 'UNRESOLVED_REVENUE_PROXY',
                'source_candidates':candidates(text,r'discount|promotional|pricing strategy|competitive pric')},
            'wholesale_proxy_mismatch':{'status':'UNRESOLVED_NO_DIRECT_DELIVERED_COST_EVIDENCE',
                'supplier_cost_observed':False,'source_candidates':candidates(text,r'freight|supplier|purchase cost|acquisition cost|supply contract')},
            'timing':{'status':'MARKET_PATH_OBSERVED_CAUSAL_CONTRIBUTION_UNRESOLVED',
                'wholesale_change_cpg':f.wholesale_change,'volatility_cpg':f.price_volatility,
                'falling_capture':f.falling_capture,'rising_squeeze':f.rising_squeeze,
                'maximum_weekly_drop_cpg':f.max_weekly_wholesale_drop,'maximum_weekly_increase_cpg':f.max_weekly_wholesale_increase,
                'source_candidates':candidates(text,r'volatil|rising wholesale|falling wholesale|declin.{0,30}wholesale|inventory timing')},
            'accounting_perimeter':{'status':'CANDIDATES_REQUIRE_RETAIL_SPECIFIC_QUANTIFICATION',
                'confirmed_retail_adjustment_cpg':None,
                'source_candidates':candidates(text,r'LIFO|inventory|acquisit|QuickChek|ethanol facilit|discontinued operations')}
        }
        pred=b.get(q)
        rows.append({'quarter':q,'regime':target['regime'],'actual_cpg':target['retail_margin_cpg'],
            'production_prediction_cpg':pred['prediction_cpg'] if pred else None,
            'actual_minus_production_cpg':target['retail_margin_cpg']-pred['prediction_cpg'] if pred else None,
            'original_six_large_miss':q in LARGE_MISS_QUARTERS,
            'source_url':target['source_url'],'raw_file':str(path),'source_sha256':sha(path),
            'source_available_at':target['available_at'],'audit_performed_at':now(),
            'source_scope':'ORIGINAL_EARNINGS_RELEASE_ONLY_NOT_COMPLETED_FILING_AND_CALL_AUDIT',
            'dimensions':dimensions,'causal_explanation':'UNRESOLVED',
            'forecast_changed':False})
    save(output/'quarter_diagnostics.json',{'rows':rows,'role':'POST_RESULT_DESCRIPTIVE_SOURCE_REVIEW_NOT_LIVE_FEATURES',
          'manual_deep_review_pending_quarters':[r['quarter'] for r in rows],
          'summary':{'quarters':len(rows),'four_dimension_records':4*len(rows),
                     'production_oof_rows':sum(r['production_prediction_cpg'] is not None for r in rows),
                     'confirmed_causal_retail_adjustments':0}})
    print('All-quarter evidence inventory:',len(rows),'quarters; causal adjudication remains pending.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path)
    audit(p.parse_args().out)
