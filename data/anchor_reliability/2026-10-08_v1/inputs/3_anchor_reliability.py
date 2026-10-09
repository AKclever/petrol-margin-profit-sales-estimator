"""Frozen recent-level seasonal anchor displacement; unchanged market adjustment."""
import argparse
from datetime import date
import json
import math
from pathlib import Path
from statistics import mean

from .history_floor_basis import bounds, previous, regime
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

SPEC=Path('data/anchor_reliability_spec_v1.json')
ROOT=Path('data/history_floor_basis/2026-10-07_evaluation_v6')


def four_ending(q):
    result=[q]
    for _ in range(3):result.append(previous(result[-1]))
    return list(reversed(result))


def make_anchor(q, targets):
    start,end=bounds(q);cutoff=str(end)
    known={k:v for k,v in targets.items() if v['quarter_end']<str(start) and v['available_at']<cutoff}
    recent=four_ending(previous(q))
    if any(k not in known for k in recent):raise ValueError('MISSING_FOUR_PUBLISHED_RECENT_QUARTERS')
    offsets=[];history=[]
    for years in [1,2,3]:
        prior=f'{int(q[:4])-years}{q[4:]}';window=four_ending(prior)
        if all(k in known for k in window):
            offsets.append(known[prior]['retail_margin_cpg']-mean(known[k]['retail_margin_cpg'] for k in window))
            history.append({'same_season':prior,'window':window,'offset_cpg':offsets[-1]})
    if len(offsets)<2:raise ValueError('FEWER_THAN_TWO_PRIOR_SEASONAL_OFFSETS')
    recent_level=mean(known[k]['retail_margin_cpg'] for k in recent)
    prior=f'{int(q[:4])-1}{q[4:]}'
    if prior not in known:raise ValueError('MISSING_PUBLISHED_PRIOR_YEAR_ANCHOR')
    original=known[prior]['retail_margin_cpg'];alternative=recent_level+mean(offsets)
    older=[f'{int(q[:4])-years}{q[4:]}' for years in [2,3]]
    reference=mean(known[k]['retail_margin_cpg'] for k in older) if all(k in known for k in older) else None
    return {'original_anchor_cpg':original,'recent_four_mean_cpg':recent_level,
        'seasonal_offset_cpg':mean(offsets),'alternative_anchor_cpg':alternative,
        'blended_anchor_cpg':.5*original+.5*alternative,'recent_input_quarters':recent,
        'seasonal_inputs':history,'older_seasonal_reference_cpg':reference,
        'prior_anchor_exceptional':reference is not None and abs(original-reference)>=5}


def tail_metrics(baseline,shadow,quarters):
    if not quarters:return {'n':0}
    result={'n':len(quarters)}
    for name,values in [('production',baseline),('challenger',shadow)]:
        errors=[abs(values[q]['actual_cpg']-values[q]['prediction_cpg']) for q in quarters]
        result[name]={'mae_cpg':mean(errors),'rmse_cpg':math.sqrt(mean(v*v for v in errors)),
            'large_error_count':sum(v>=5 for v in errors),'large_error_frequency':mean(v>=5 for v in errors),
            'worst_abs_error_cpg':max(errors)}
    return result


def evaluate(output):
    output.mkdir(parents=True,exist_ok=False)
    inputs=[SPEC,ROOT/'historical_targets.json',ROOT/'results.json',Path(__file__),Path('musa_nowcast/timing.py')]
    snapshots=output/'inputs';snapshots.mkdir()
    for n,p in enumerate(inputs):
        with (snapshots/f'{n}_{p.name}').open('xb') as f:f.write(p.read_bytes())
    save(output/'frozen_inputs.json',{'frozen_at':now(),'files':[{'path':str(p),'sha256':sha(p)} for p in inputs]})
    targets={r['quarter']:r for r in json.loads((ROOT/'historical_targets.json').read_text())['quarters']}
    baseline={r['quarter']:r for r in json.loads((ROOT/'results.json').read_text())['baseline_rows']}
    anchors={};blocked=[]
    for q in sorted(baseline):
        try:anchors[q]=make_anchor(q,targets)
        except ValueError as exc:blocked.append({'quarter':q,'reason':str(exc)})
    save(output/'frozen_anchor_inputs.json',{'anchors':anchors,'blocked':blocked})
    shadow={}
    for q,a in anchors.items():
        r=baseline[q]
        if abs(r['seasonal_cpg']-a['original_anchor_cpg'])>1e-9:raise ValueError('Archived anchor mismatch')
        adjustment=r['prediction_cpg']-r['seasonal_cpg'];point=a['blended_anchor_cpg']+adjustment
        ref=a['older_seasonal_reference_cpg']
        persistence=None if not a['prior_anchor_exceptional'] else ('PERSISTED' if abs(r['actual_cpg']-ref)>=5 and (r['actual_cpg']-ref)*(a['original_anchor_cpg']-ref)>0 else 'REVERSED_OR_NORMALIZED')
        shadow[q]=r|{'prediction_cpg':point,'production_prediction_cpg':r['prediction_cpg'],
            'market_adjustment_unchanged_cpg':adjustment,'anchor_evidence':a,'exceptional_anchor_outcome':persistence,
            'direction_correct':NowcastEngine._direction(point-r['seasonal_cpg'])==NowcastEngine._direction(r['actual_cpg']-r['seasonal_cpg'])}
    results={}
    for era in ['earlier_low_margin','transition','later_regime']:
        qs=sorted(q for q in shadow if regime(q)==era)
        large=[q for q in qs if abs(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg'])>=5]
        ordinary=[q for q in qs if q not in large]
        exceptional=[q for q in qs if shadow[q]['anchor_evidence']['prior_anchor_exceptional']]
        results[era]={'quarters':qs,'standard_metrics':_metrics(baseline,shadow,qs) if qs else None,
            'tail_metrics':tail_metrics(baseline,shadow,qs),'original_large_error_quarters':large,
            'large_group':tail_metrics(baseline,shadow,large),'ordinary_group':tail_metrics(baseline,shadow,ordinary),
            'exceptional_anchor_groups':{name:tail_metrics(baseline,shadow,[q for q in exceptional if shadow[q]['exceptional_anchor_outcome']==name]) for name in ['PERSISTED','REVERSED_OR_NORMALIZED']}}
    result={'created_at':now(),'production_changed':False,'role':'DEVELOPMENTAL_CURRENT_VINTAGE_NOT_PIT_VALIDATION',
            'by_regime':results,'rows':[shadow[q] for q in sorted(shadow)],'blocked':blocked,
            'current_forecast_changed':False,'automatic_promotion':False}
    save(output/'results.json',result)
    print(json.dumps(results['later_regime'],indent=2))
    for q in results['later_regime']['original_large_error_quarters']:
        r=shadow[q];print(q,'actual',r['actual_cpg'],'production',round(r['production_prediction_cpg'],3),'anchor-shadow',round(r['prediction_cpg'],3))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);evaluate(p.parse_args().out)
