"""Six directional peer transfers, fixed overlap split and influence checks."""
import argparse
from datetime import date
import json
from pathlib import Path

from .earnings_event_replay import BASES, era, select, overlap, donor_input, loading, validate
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

SPEC=Path('data/peer_direction_diagnostics_spec_v1.json')
DATASET=Path('data/earnings_event_replay/2026-10-08_v3/dataset.json')


def overlap_class(fraction):
    if not 0<=fraction<=1:raise ValueError('INVALID_OVERLAP_FRACTION')
    return 'HIGH' if fraction>=.5 else 'LOW' if fraction>0 else 'NO_OVERLAP'


def direction_forecasts(records, donor_company, recipient_company):
    if donor_company==recipient_company:raise ValueError('SELF_TRANSFER_FORBIDDEN')
    forecasts=[];excluded=[]
    for target in records:
        if target['company']!=recipient_company or target.get('actual_cpg') is None:continue
        cutoff=target['available_at'];donor=select(target,donor_company,records,cutoff)
        if donor is None:
            excluded.append({'quarter':target['quarter'],'reason':'NO_PUBLISHED_OVERLAPPING_DONOR'});continue
        days=overlap(target,donor)
        fraction=days/((date.fromisoformat(target['end'])-date.fromisoformat(target['start'])).days+1)
        x=donor_input(target,donor);coefficient,pairs=loading(target,donor_company,records,cutoff)
        forecasts.append({'quarter':target['quarter'],'recipient':recipient_company,'donor':donor_company,
            'start':target['start'],'end':target['end'],'era':era(target),'cutoff':cutoff,
            'baseline_cpg':target['prediction_cpg'],'seasonal_cpg':target['seasonal_cpg'],
            'fixed_prediction_cpg':target['prediction_cpg']+.5*x,
            'fitted_prediction_cpg':target['prediction_cpg']+.5*coefficient*x if coefficient is not None else None,
            'fitted_eligible':coefficient is not None,'loading':coefficient,'training_pairs':pairs,
            'donor_quarter':donor['quarter'],'donor_available_at':donor['available_at'],
            'donor_source_url':donor['source_url'],'donor_source_sha256':donor['source_sha256'],
            'overlap_days':days,'overlap_fraction':fraction,'overlap_class':overlap_class(fraction),
            'overlap_weighted_surprise_cpg':x})
    return forecasts,excluded


def concentration(rows, method):
    if not rows:return {'n':0}
    gains=[(r['quarter'],r['baseline_abs_error_cpg']-r[method+'_abs_error_cpg']) for r in rows]
    n=len(gains);total=sum(v for _,v in gains)
    positive=[(q,v) for q,v in gains if v>0]
    best=max(positive,key=lambda p:p[1]) if positive else None
    loo=[{'removed_quarter':q,'remaining_mean_improvement_cpg':(total-v)/(n-1)} for q,v in gains] if n>1 else []
    remaining=(total-best[1])/(n-1) if best and n>1 else None
    return {'n':n,'mean_improvement_cpg':total/n,'improved':sum(v>0 for _,v in gains),
            'worsened':sum(v<0 for _,v in gains),'unchanged':sum(v==0 for _,v in gains),
            'largest_positive_contributor':{'quarter':best[0],'abs_error_improvement_cpg':best[1]} if best else None,
            'largest_share_of_positive_gains':best[1]/sum(v for _,v in positive) if best else None,
            'improvement_without_best_quarter_cpg':remaining,
            'positive_gain_disappears_without_best':bool(total>0 and remaining is not None and remaining<=0),
            'worst_leave_one_out_mean_cpg':min(r['remaining_mean_improvement_cpg'] for r in loo) if loo else None,
            'leave_one_out':loo,'refitted':False}


def summarize(rows):
    if not rows:return {'n':0}
    baseline={r['quarter']:{'actual_cpg':r['actual_cpg'],'prediction_cpg':r['baseline_cpg'],
              'direction_correct':NowcastEngine._direction(r['baseline_cpg']-r['seasonal_cpg'])==
                                  NowcastEngine._direction(r['actual_cpg']-r['seasonal_cpg'])} for r in rows}
    result={'n':len(rows),'loading_zero_count':sum(r['loading']==0 for r in rows),
            'original_large_error_count':sum(r['baseline_abs_error_cpg']>=5 for r in rows)}
    for method in ['fixed','fitted']:
        shadows={r['quarter']:{'prediction_cpg':r[method+'_prediction_cpg'],
                    'direction_correct':NowcastEngine._direction(r[method+'_prediction_cpg']-r['seasonal_cpg'])==
                                        NowcastEngine._direction(r['actual_cpg']-r['seasonal_cpg'])} for r in rows}
        metrics=_metrics(baseline,shadows,sorted(baseline))
        ordinary=[r for r in rows if r['baseline_abs_error_cpg']<5]
        large=[r for r in rows if r['baseline_abs_error_cpg']>=5]
        result[method]={'metrics':metrics,'concentration':concentration(rows,method),
            'ordinary_mean_improvement_cpg':sum(r['baseline_abs_error_cpg']-r[method+'_abs_error_cpg'] for r in ordinary)/len(ordinary) if ordinary else None,
            'large_mean_improvement_cpg':sum(r['baseline_abs_error_cpg']-r[method+'_abs_error_cpg'] for r in large)/len(large) if large else None,
            'baseline_errors_ge5':sum(r['baseline_abs_error_cpg']>=5 for r in rows),
            'shadow_errors_ge5':sum(r[method+'_abs_error_cpg']>=5 for r in rows)}
    return result


def evaluate(output):
    output.mkdir(parents=True,exist_ok=False)
    paths=[SPEC,Path(__file__),DATASET,Path('musa_nowcast/earnings_event_replay.py'),Path('musa_nowcast/timing.py')]
    save(output/'frozen_inputs.json',{'created_at':now(),'files':[{'path':str(p),'sha256':sha(p)} for p in paths]})
    (output/'inputs').mkdir()
    for i,p in enumerate(paths):
        with (output/'inputs'/f'{i}_{p.name}').open('xb') as handle:handle.write(p.read_bytes())
    records=json.loads(DATASET.read_text())['records']
    for r in records:validate(r)
    frozen={}
    for donor in BASES:
        for recipient in BASES:
            if donor==recipient:continue
            rows,excluded=direction_forecasts(records,donor,recipient)
            frozen[donor+'_TO_'+recipient]={'forecasts':rows,'no_overlap_exclusions':excluded}
    save(output/'frozen_forecasts.json',{'frozen_at':now(),'directions':frozen})
    targets={(r['company'],r['quarter']):r for r in records}
    results={}
    for name,payload in frozen.items():
        scored=[]
        for row in payload['forecasts']:
            actual=targets[(row['recipient'],row['quarter'])]['actual_cpg']
            scored.append(row|{'actual_cpg':actual,'baseline_abs_error_cpg':abs(actual-row['baseline_cpg']),
                'fixed_abs_error_cpg':abs(actual-row['fixed_prediction_cpg']),
                'fitted_abs_error_cpg':abs(actual-row['fitted_prediction_cpg']) if row['fitted_eligible'] else None})
        groups={}
        for modern in [False,True]:
            subset=[r for r in scored if not modern or r['era']=='modern']
            eligible=[r for r in subset if r['fitted_eligible']]
            label='modern' if modern else 'all'
            groups[label]={'fixed_available':len(subset),'fitted_available':len(eligible),
                'fixed_only_coverage_mae_cpg':sum(r['fixed_abs_error_cpg'] for r in subset)/len(subset) if subset else None,
                'baseline_on_fixed_coverage_mae_cpg':sum(r['baseline_abs_error_cpg'] for r in subset)/len(subset) if subset else None,
                'matched':{b:summarize([r for r in eligible if b=='ALL' or r['overlap_class']==b]) for b in ['ALL','HIGH','LOW']}}
        results[name]={'groups':groups,'scored_rows':scored,'no_overlap_exclusions':payload['no_overlap_exclusions']}
    payload={'role':json.loads(SPEC.read_text())['role'],'directions':results,'production_changed':False,
             'automatic_promotion':False,'strict_market_pit_verified':False,'overlap_threshold':.5}
    save(output/'results.json',payload)
    print(json.dumps({n:{b:g['groups']['modern']['matched'][b] for b in ['ALL','HIGH','LOW']} for n,g in results.items()},indent=2))
    return payload


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path)
    evaluate(p.parse_args().out)
