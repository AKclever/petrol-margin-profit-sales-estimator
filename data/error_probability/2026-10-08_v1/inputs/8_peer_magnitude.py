"""Small constrained peer-surprise correction, fitted chronologically."""
import argparse
import json
import math
from pathlib import Path
from statistics import mean

from .earnings_event_replay import donor_input, era, select
from .error_direction import DATA
from .prospective import sha

SPEC = Path('data/peer_magnitude_spec_v1.json')
LIVE = Path('data/peer_surprise/2026-10-07_v2/result.json')


def features(target, records):
    donors = [select(target, c, records, target['end']) for c in ('CASY', 'ATD')]
    if any(d is None for d in donors):
        return None
    return {'x': [donor_input(target, d) for d in donors],
            'donors': [{'company': d['company'], 'quarter': d['quarter'],
                        'available_at': d['available_at'], 'source_sha256': d['source_sha256']}
                       for d in donors]}


def coefficients(pairs):
    # Convex box-constrained quadratic: interior solution plus edge optima.
    a = 25 + sum(p['x'][0]**2 for p in pairs)
    b = sum(p['x'][0]*p['x'][1] for p in pairs)
    c = 25 + sum(p['x'][1]**2 for p in pairs)
    u = sum(p['x'][0]*p['y'] for p in pairs)
    v = sum(p['x'][1]*p['y'] for p in pairs)
    clamp = lambda x: min(1., max(0., x))
    candidates = [(t, clamp((v-b*t)/c)) for t in (0., 1.)]
    candidates += [(clamp((u-b*t)/a), t) for t in (0., 1.)]
    interior = ((u*c-v*b)/(a*c-b*b), (v*a-u*b)/(a*c-b*b))
    if all(0 <= x <= 1 for x in interior):
        candidates.append(interior)
    return list(min(candidates, key=lambda w: a*w[0]**2+2*b*w[0]*w[1]+c*w[1]**2-2*u*w[0]-2*v*w[1]))


def forecast(target, records):
    f = features(target, records)
    pairs = []
    for prior in records:
        if prior['company'] != 'MUSA' or era(prior) != era(target) or prior['end'] >= target['start'] or prior['available_at'] >= target['end']:
            continue
        pf = features(prior, records)
        if pf:
            pairs.append({'quarter': prior['quarter'], 'available_at': prior['available_at'],
                          'feature_cutoff': prior['end'], 'donors': pf['donors'], 'x': pf['x'],
                          'y': prior['actual_cpg']-prior['prediction_cpg']})
    row = {'quarter': target['quarter'], 'era': era(target), 'cutoff': target['end'],
           'production_cpg': target['prediction_cpg'], 'features': f, 'training_pairs': pairs}
    if f is None or len(pairs) < 8:
        return row | {'status': 'BLOCKED_MISSING_PEER_OR_INSUFFICIENT_TRAINING'}
    w = coefficients(pairs)
    correction = sum(a*b for a, b in zip(w, f['x']))
    return row | {'status': 'RESEARCH_ONLY', 'coefficients': w, 'correction_cpg': correction,
                  'fitted_cpg': target['prediction_cpg']+correction,
                  'fixed_casy_cpg': target['prediction_cpg']+.5*f['x'][0]}


def metrics(rows):
    if not rows:
        return {'n': 0}
    result = {'n': len(rows)}
    for method in ('production', 'fixed_casy', 'fitted'):
        errors = [abs(r['actual_cpg']-r[method+'_cpg']) for r in rows]
        gains = [abs(r['actual_cpg']-r['production_cpg'])-e for r, e in zip(rows, errors)]
        result[method] = {'mae_cpg': mean(errors), 'rmse_cpg': math.sqrt(mean(e*e for e in errors)),
                          'large_error_count': sum(e >= 5 for e in errors),
                          'worst_error_cpg': max(errors), 'quarters_worsened': sum(g < -1e-10 for g in gains),
                          'mean_gain_without_best_cpg': (sum(gains)-max(gains))/(len(gains)-1) if len(gains)>1 else None}
    return result


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    paths = [DATA, SPEC, LIVE, Path(__file__), Path('musa_nowcast/earnings_event_replay.py')]
    (output/'inputs').mkdir()
    for i, p in enumerate(paths):
        (output/'inputs'/f'{i}_{p.name}').write_bytes(p.read_bytes())
    (output/'manifest.json').write_text(json.dumps([{'path': str(p), 'sha256': sha(p)} for p in paths], indent=2)+'\n')
    records = json.loads(DATA.read_text())['records']
    targets = [r for r in records if r['company']=='MUSA']
    frozen = [forecast(r, records) for r in targets]
    live_peer = json.loads(LIVE.read_text())['peer_predictions'][-1]
    live_peer |= {'company': 'CASY', 'source_sha256': live_peer['source']['sha256']}
    current = forecast({'quarter': '2026Q3', 'start': '2026-07-01', 'end': '2026-09-30',
                        'prediction_cpg': 28.94}, records+[live_peer])
    (output/'frozen_predictions.json').write_text(json.dumps({'historical': frozen, 'q3_2026': current}, indent=2)+'\n')
    actuals = {r['quarter']: r['actual_cpg'] for r in targets}
    scored = [r | {'actual_cpg': actuals[r['quarter']]} for r in frozen if r['status']=='RESEARCH_ONLY']
    groups = {}
    for group in ('all', 'modern', 'modern_large', 'modern_ordinary'):
        rows = [r for r in scored if (group=='all' or r['era']=='modern') and
                (group!='modern_large' or abs(r['actual_cpg']-r['production_cpg'])>=5) and
                (group!='modern_ordinary' or abs(r['actual_cpg']-r['production_cpg'])<5)]
        groups[group] = metrics(rows)
    result = {'role': json.loads(SPEC.read_text())['role'], 'groups': groups, 'scored_rows': scored,
              'blocked_quarters': [r['quarter'] for r in frozen if r['status']!='RESEARCH_ONLY'],
              'q3_2026': current, 'production_changed': False, 'variant_promoted': False}
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(groups, indent=2))
    print('Q3', {k: v for k, v in current.items() if k not in ('training_pairs', 'features')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
