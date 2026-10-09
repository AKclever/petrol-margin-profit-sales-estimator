"""Predict the sign of MUSA forecast error separately from margin direction."""
import argparse
import json
import math
from pathlib import Path

from .earnings_event_replay import era, select
from .prospective import sha

DATA=Path('data/earnings_event_replay/2026-10-08_v3/dataset.json')
SPEC=Path('data/error_direction_spec_v1.json')


def sign(value):
    return 'ABOVE' if value>1e-10 else 'BELOW' if value < -1e-10 else 'ABSTAIN'


def predictions(target, records):
    cutoff=target['end']
    past=sorted([r for r in records if r['company']=='MUSA' and r['end']<target['start']
        and r['available_at']<cutoff and era(r)==era(target)],key=lambda r:r['end'])
    residuals=[r['actual_cpg']-r['prediction_cpg'] for r in past]
    majority=sign(sum(1 if x>1e-10 else -1 if x < -1e-10 else 0 for x in residuals)) if len(past)>=4 else 'ABSTAIN'
    payload={'quarter':target['quarter'],'era':era(target),'cutoff':cutoff,
        'production_forecast_cpg':target['prediction_cpg'],'historical_majority':majority,
        'prior_residual_training':[{'quarter':r['quarter'],'available_at':r['available_at']} for r in past],
        'signals':{'recent_residual':{'call':sign(sum(residuals[-4:])/4) if len(past)>=4 else 'ABSTAIN'}}}
    for company in ['CASY','ATD']:
        donor=select(target,company,records,cutoff)
        if donor is None:
            payload['signals'][company]={'call':'ABSTAIN','reason':'NO_ELIGIBLE_OVERLAPPING_DONOR'}
        else:
            surprise=donor['actual_cpg']-donor['prediction_cpg']
            payload['signals'][company]={'call':sign(surprise),'surprise_cpg':surprise,
                'quarter':donor['quarter'],'available_at':donor['available_at'],
                'source_sha256':donor['source_sha256'],'source_url':donor['source_url']}
    return payload


def score(rows, method):
    called=[r for r in rows if r['actual_direction']!='ABSTAIN' and r['signals'][method]['call']!='ABSTAIN']
    n=len(called)
    if not n:return {'eligible_rows':len(rows),'calls':0}
    correct=sum(r['signals'][method]['call']==r['actual_direction'] for r in called)
    recalls={label:(sum(r['actual_direction']==label and r['signals'][method]['call']==label for r in called)/
                   sum(r['actual_direction']==label for r in called))
             if any(r['actual_direction']==label for r in called) else None for label in ['ABOVE','BELOW']}
    p=correct/n;z=1.96;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    majority=[r for r in called if r['historical_majority']!='ABSTAIN']
    return {'eligible_rows':len(rows),'calls':n,'coverage':n/len(rows),'correct':correct,'accuracy':p,
        'above_recall':recalls['ABOVE'],'below_recall':recalls['BELOW'],
        'balanced_accuracy':sum(recalls.values())/2 if None not in recalls.values() else None,
        'always_above_accuracy':sum(r['actual_direction']=='ABOVE' for r in called)/n,
        'always_below_accuracy':sum(r['actual_direction']=='BELOW' for r in called)/n,
        'historical_majority_calls':len(majority),
        'historical_majority_accuracy':sum(r['historical_majority']==r['actual_direction'] for r in majority)/len(majority) if majority else None,
        'signal_accuracy_on_majority_coverage':sum(r['signals'][method]['call']==r['actual_direction'] for r in majority)/len(majority) if majority else None,
        'wilson_descriptive_95_interval':[center-half,center+half],
        'leave_one_out_accuracy_range':[(correct-1)/(n-1) if correct else 0,correct/(n-1) if correct<n else 1] if n>1 else None,
        'interval_note':'Descriptive independent-Bernoulli interval; serial dependence and repeated research are not accounted for'}


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    paths=[DATA,SPEC,Path(__file__),Path('musa_nowcast/earnings_event_replay.py')]
    (output/'inputs').mkdir()
    for i,p in enumerate(paths):(output/'inputs'/f'{i}_{p.name}').write_bytes(p.read_bytes())
    (output/'manifest.json').write_text(json.dumps([{'path':str(p),'sha256':sha(p)} for p in paths],indent=2)+'\n')
    records=json.loads(DATA.read_text())['records']
    targets=[r for r in records if r['company']=='MUSA']
    frozen=[predictions(r,records) for r in targets]
    (output/'frozen_predictions.json').write_text(json.dumps(frozen,indent=2)+'\n')
    outcomes={r['quarter']:r['actual_cpg'] for r in targets}
    scored=[r | {'actual_cpg':outcomes[r['quarter']],
                 'actual_direction':sign(outcomes[r['quarter']]-r['production_forecast_cpg']),
                 'absolute_production_error_cpg':abs(outcomes[r['quarter']]-r['production_forecast_cpg'])} for r in frozen]
    groups={}
    for group in ['all','modern','modern_large','modern_ordinary']:
        rows=[r for r in scored if (group=='all' or r['era']=='modern') and
              (group!='modern_large' or r['absolute_production_error_cpg']>=5) and
              (group!='modern_ordinary' or r['absolute_production_error_cpg']<5)]
        groups[group]={m:score(rows,m) for m in ['CASY','ATD','recent_residual']}
    result={'role':json.loads(SPEC.read_text())['role'],'groups':groups,'scored_rows':scored,
            'production_changed':False,'probability_calibrated':False,'automatic_adjustment':False}
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(groups['modern'],indent=2))
    print('Large misses:',json.dumps(groups['modern_large'],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
