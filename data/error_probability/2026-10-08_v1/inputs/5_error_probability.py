"""Exploratory chronological direction and tail probabilities."""
import argparse
from datetime import date
import json
import math
from pathlib import Path
from statistics import mean

from .data import QuarterActual, load_market, load_weights
from .earnings_event_replay import era
from .error_direction import DATA
from .model import NowcastEngine
from .peer_magnitude import LIVE, features
from .prospective import sha
from .risk import assess

SPEC = Path('data/error_probability_spec_v1.json')
MARKET = Path('data/q3_focus/2026-10-08_v3/market.csv')
WEIGHTS = Path('data/weights.csv')


def sigmoid(x):
    return 1/(1+math.exp(-max(-30., min(30., x))))


def fit_probability(pairs, x):
    if len(pairs)<8 or len({p['y'] for p in pairs})<2:
        return {'status': 'BLOCKED_INSUFFICIENT_HISTORY_OR_CLASSES', 'n': len(pairs)}
    base = (sum(p['y'] for p in pairs)+1)/(len(pairs)+2)
    intercept = math.log(base/(1-base))
    w = [0.]*len(x)
    for _ in range(1000):
        gradients = [4*v for v in w]
        for p in pairs:
            error = sigmoid(intercept+sum(a*b for a,b in zip(w,p['x'])))-p['y']
            for j in range(len(w)):
                gradients[j] += error*p['x'][j]
        w = [v-.1*g/len(pairs) for v,g in zip(w, gradients)]
    return {'status': 'EXPLORATORY', 'n': len(pairs), 'base_probability': base,
            'probability': sigmoid(intercept+sum(a*b for a,b in zip(w,x))), 'coefficients': w}


def input_row(target, records, market, weights):
    peer = features(target, records)
    row = {'quarter': target['quarter'], 'era': era(target), 'cutoff': target['end'],
           'production_cpg': target['prediction_cpg'], 'direction_x': None, 'tail_x': None}
    if peer:
        row['direction_x'] = [max(-3.,min(3.,v/5)) for v in peer['x']]
        row['peer_evidence'] = peer
    # Market archive begins in 2019. Never fabricate earlier risk features.
    known = [r for r in records if r['company']=='MUSA' and r['start']>='2019-01-01'
             and r['end']<target['start'] and r['available_at']<target['end']]
    row['risk_training_quarters'] = [r['quarter'] for r in known]
    actuals = [QuarterActual(r['quarter'],date.fromisoformat(r['start']),date.fromisoformat(r['end']),r['actual_cpg'])
               for r in sorted(known,key=lambda r:r['start'])]
    try:
        engine = NowcastEngine([m for m in market if str(m.week)<=target['end']], weights, actuals)
        risk = assess(engine,date.fromisoformat(target['start']),date.fromisoformat(target['end']),date.fromisoformat(target['end']))
        levels = [r['level'] for r in risk['risks'].values()]
        row['tail_x'] = [(levels.count('HIGH')+.5*levels.count('MEDIUM'))/4]
        row['risk'] = risk
    except (ValueError, StopIteration, IndexError, ZeroDivisionError) as exc:
        row['risk_blocker'] = str(exc) or type(exc).__name__
    return row


def forecast(target, frozen_inputs, outcomes):
    row = dict(target)
    for name in ('direction','tail'):
        pairs = []
        for prior in frozen_inputs:
            outcome = outcomes.get(prior['quarter'])
            if prior['era']!=target['era'] or prior['cutoff']>=target['cutoff'] or not outcome or outcome['available_at']>=target['cutoff'] or prior[name+'_x'] is None:
                continue
            error = outcome['actual_cpg']-prior['production_cpg']
            if name=='direction' and abs(error)<=1e-10:
                continue
            pairs.append({'quarter': prior['quarter'], 'available_at': outcome['available_at'],
                          'x': prior[name+'_x'], 'y': int(error>0) if name=='direction' else int(abs(error)>=5)})
        row[name+'_training'] = pairs
        row[name] = fit_probability(pairs,target[name+'_x']) if target[name+'_x'] is not None else {'status':'BLOCKED_MISSING_INPUT'}
    if all(row[k]['status']=='EXPLORATORY' for k in ('direction','tail')):
        up, tail = row['direction']['probability'],row['tail']['probability']
        row['three_state_independence_approximation'] = {'large_downside': tail*(1-up), 'within_5c': 1-tail, 'large_upside': tail*up}
    return row


def scoring(rows, name):
    eligible = [r for r in rows if r[name]['status']=='EXPLORATORY']
    if not eligible:
        return {'n':0}
    def label(r):
        e = r['actual_cpg']-r['production_cpg']
        return int(e>0) if name=='direction' else int(abs(e)>=5)
    result = {'n':len(eligible), 'events':sum(label(r) for r in eligible)}
    for method, key in [('model','probability'),('base_rate','base_probability')]:
        probs = [r[name][key] for r in eligible]
        result[method] = {'brier': mean((p-label(r))**2 for p,r in zip(probs,eligible)),
                          'log_loss': mean(-label(r)*math.log(p)-(1-label(r))*math.log(1-p) for p,r in zip(probs,eligible))}
    result['calibration_bins'] = []
    for low,high in [(0,1/3),(1/3,2/3),(2/3,1.000001)]:
        bucket = [r for r in eligible if low<=r[name]['probability']<high]
        result['calibration_bins'].append({'low':low,'high':min(high,1),'n':len(bucket),
            'mean_probability':mean(r[name]['probability'] for r in bucket) if bucket else None,
            'event_rate':mean(label(r) for r in bucket) if bucket else None})
    return result


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    paths=[DATA,SPEC,MARKET,WEIGHTS,LIVE,Path(__file__),Path('musa_nowcast/risk.py'),Path('musa_nowcast/model.py'),Path('musa_nowcast/peer_magnitude.py')]
    (output/'inputs').mkdir()
    for i,p in enumerate(paths):
        (output/'inputs'/f'{i}_{p.name}').write_bytes(p.read_bytes())
    (output/'manifest.json').write_text(json.dumps([{'path':str(p),'sha256':sha(p)} for p in paths],indent=2)+'\n')
    records=json.loads(DATA.read_text())['records']
    peer=json.loads(LIVE.read_text())['peer_predictions'][-1]
    peer |= {'company':'CASY','source_sha256':peer['source']['sha256']}
    records.append(peer)
    market,weights=load_market(MARKET),load_weights(WEIGHTS)
    targets=[r for r in records if r['company']=='MUSA']
    inputs=[input_row(t,records,market,weights) for t in targets]
    (output/'frozen_features.json').write_text(json.dumps(inputs,indent=2)+'\n')
    outcomes={t['quarter']:t for t in targets}
    frozen=[forecast(t,inputs,outcomes) for t in inputs]
    current=input_row({'quarter':'2026Q3','start':'2026-07-01','end':'2026-09-30','prediction_cpg':28.94},records,market,weights)
    current=forecast(current,inputs,outcomes)
    (output/'frozen_predictions.json').write_text(json.dumps({'historical':frozen,'q3_2026':current},indent=2)+'\n')
    scored=[r | {'actual_cpg':outcomes[r['quarter']]['actual_cpg']} for r in frozen]
    groups={}
    for group in ('modern','modern_large','modern_ordinary'):
        rows=[r for r in scored if r['era']=='modern' and
              (group!='modern_large' or abs(r['actual_cpg']-r['production_cpg'])>=5) and
              (group!='modern_ordinary' or abs(r['actual_cpg']-r['production_cpg'])<5)]
        groups[group]={name:scoring(rows,name) for name in ('direction','tail')}
    result={'role':json.loads(SPEC.read_text())['role'],'groups':groups,'scored_rows':scored,'q3_2026':current,
            'production_changed':False,'probability_calibrated':False,'promoted':False}
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(groups,indent=2))
    print('Q3', {k:current[k] for k in ('direction','tail')})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
