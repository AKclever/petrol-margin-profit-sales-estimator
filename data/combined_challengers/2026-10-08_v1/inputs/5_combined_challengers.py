"""Small frozen combination experiment with diesel-break exclusions."""
import argparse
from datetime import date
import json
from pathlib import Path

from .history_floor_basis import bounds, residual_shadow
from .mathutils import RidgeModel
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

SPEC = Path('data/combined_challengers_spec_v1.json')
HISTORY = Path('data/history_floor_basis/2026-10-07_evaluation_v6/results.json')
ALT = Path('data/alternative_margin_experiments/2026-10-07_evaluation_v2/results.json')
CASY = Path('data/peer_surprise/2026-10-07_v2/result.json')
ATD = Path('data/couchetard_peer/2026-10-07_v3/result.json')


def crosses_diesel_break(q):
    start, end = bounds(q); old_start, _ = bounds(f'{int(q[:4])-1}{q[4:]}')
    return old_start < date(2022,6,13) <= end


def point(row, value):
    return row | {'prediction_cpg':value, 'direction_correct':
        NowcastEngine._direction(value-row['seasonal_cpg']) == NowcastEngine._direction(row['actual_cpg']-row['seasonal_cpg'])}


def joint(rows):
    out = {}; blocked = []
    for r in rows:
        training = [t for t in rows if t['quarter_end'] < r['quarter_end'] and t['outcome_available_at'] < r['quarter_end']]
        if len(training) < 8:
            blocked.append({'quarter':r['quarter'],'reason':'FEWER_THAN_EIGHT_PUBLISHED_COMPLETE_FEATURE_ROWS'});continue
        model = RidgeModel(10).fit([t['features'] for t in training], [t['actual_cpg']-t['prediction_cpg'] for t in training])
        correction = .5*model.predict_one(r['features'])
        out[r['quarter']] = point(r,r['prediction_cpg']+correction) | {'correction_cpg':correction,
            'training_quarters':[t['quarter'] for t in training]}
    return out, blocked


def blend(components, baseline):
    common = sorted(set.intersection(*(set(c) for c in components.values())))
    return {q:point(baseline[q],sum(c[q]['prediction_cpg'] for c in components.values())/len(components)) |
        {'component_predictions':{name:c[q]['prediction_cpg'] for name,c in components.items()}} for q in common}


def summary(baseline, candidate):
    quarters = sorted(candidate)
    if not quarters:
        return {'status':'BLOCKED_NO_MATCHED_ROWS'}
    best = max(quarters,key=lambda q:abs(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg'])-abs(candidate[q]['actual_cpg']-candidate[q]['prediction_cpg']))
    return {'metrics':_metrics(baseline,candidate,quarters), 'quarters':quarters,
        'remove_best_benefit_sensitivity':{'omitted_quarter':best,'metrics':_metrics(baseline,candidate,[q for q in quarters if q!=best]) if len(quarters)>1 else None},
        'rows':[candidate[q] for q in quarters]}


def select_peer(rows, q):
    start,end = map(str,bounds(q))
    eligible = [r for r in rows if r['available_at'] < end and r['start'] <= end and r['end'] >= start]
    return max(eligible,key=lambda r:(r['available_at'],r['end'])) if eligible else None


def evaluate(output):
    output.mkdir(parents=True,exist_ok=False)
    paths = [SPEC,HISTORY,ALT,CASY,ATD,Path(__file__),Path('musa_nowcast/mathutils.py'),Path('musa_nowcast/timing.py'),Path('musa_nowcast/history_floor_basis.py')]
    snapshots = output/'inputs'; snapshots.mkdir()
    for n,p in enumerate(paths):
        with (snapshots/f'{n}_{p.name}').open('xb') as f:f.write(p.read_bytes())
    save(output/'frozen_inputs.json',{'frozen_at':now(),'files':[{'path':str(p),'sha256':sha(p)} for p in paths]})
    h,a,c,t = [json.loads(p.read_text()) for p in [HISTORY,ALT,CASY,ATD]]
    baseline = {r['quarter']:r for r in h['baseline_rows'] if r['quarter'] >= '2021Q1'}
    diesel_rows = [r for r in h['diesel']['feature_rows'] if r['quarter'] >= '2021Q1' and not crosses_diesel_break(r['quarter'])]
    clean,clean_blocked = residual_shadow(diesel_rows)
    gap_rows = a['results']['lagged_gap']['rows']
    # Gap archive's scored rows alone lose early training examples. Recover
    # original features directly from the already archived all-quarter audit.
    audit_path = Path('data/revenue_gap_all/2026-10-07_review_v2/quarter_rows.json')
    audit = {r['quarter']:r for r in json.loads(audit_path.read_text())['rows']}
    target_path = HISTORY.parent/'historical_targets.json'
    targets = {r['quarter']:r for r in json.loads(target_path.read_text())['quarters']}
    save(output/'additional_input_hashes.json',{'files':[{'path':str(p),'sha256':sha(p)} for p in [audit_path,target_path]]})
    from .history_floor_basis import previous
    combined = []; peer_combined = []; input_excluded = []
    for r in diesel_rows:
        q = r['quarter']; prior = audit.get(previous(q))
        if not prior or prior.get('revenue_proxy_error_cpg') is None or prior['revenue_gap_available_at'] >= r['quarter_end']:
            input_excluded.append({'quarter':q,'reason':'NO_PUBLISHED_PRIOR_REVENUE_GAP'});continue
        row = r | {'features':r['features']+[prior['revenue_proxy_error_cpg']],
                   'gap_available_at':prior['revenue_gap_available_at']}
        combined.append(row)
        cp,tp = select_peer(c['peer_predictions'],q),select_peer(t['peer_predictions'],q)
        if cp and tp:
            peer_combined.append(row | {'features':row['features']+[cp['surprise_cpg'],tp['surprise_cpg']],
                                       'peers':{'caseys':cp,'couchetard':tp}})
        else:input_excluded.append({'quarter':q,'reason':'MISSING_PUBLISHED_OVERLAPPING_PEER'})
    two, two_blocked = joint(combined); four, four_blocked = joint(peer_combined)
    gap = {r['quarter']:r for r in gap_rows}
    components = {'clean_diesel':clean,'lagged_gap':gap,
        'regional_supply':{r['quarter']:r for r in a['results']['regional_supply']['rows']},
        'floor':{r['quarter']:r for r in h['floor']['shadow_rows']},
        'all_grade':{r['quarter']:r for r in h['all_grade']['shadow_rows']},
        'caseys':{r['quarter']:r for r in c['backtest_rows']},
        'couchetard':{r['quarter']:r for r in t['backtest_rows']}}
    # Every archived component must reference exactly the same outcomes/baseline.
    for name,component in components.items():
        for q,r in component.items():
            if q in baseline and r['actual_cpg'] != baseline[q]['actual_cpg']:
                raise ValueError(f'Different target basis: {name} {q}')
    candidates = {'clean_diesel':clean,
        'equal_blend_clean_diesel_and_gap':blend({'diesel':clean,'gap':gap},baseline),
        'joint_clean_diesel_and_gap':two,'joint_clean_diesel_gap_caseys_couchetard':four,
        'equal_blend_all_compatible_available_shadows':blend(components,baseline)}
    result = {'created_at':now(),'production_changed':False,'role':'DEVELOPMENTAL_CURRENT_VINTAGE_NOT_PIT_VALIDATION',
        'diesel_break_audit':{'break_date':'2022-06-13','source_url':'https://www.eia.gov/petroleum/gasdiesel/diesel_proc-methods.php',
            'excluded_modern_quarters':[q for q in baseline if crosses_diesel_break(q)],
            'bridge_adjustment_inferred':False,'clean_training_rows':[r['quarter'] for r in diesel_rows]},
        'results':{name:summary(baseline,v) for name,v in candidates.items()},
        'individuals_on_all_blend_rows':{name:summary(baseline,{q:v[q] for q in candidates['equal_blend_all_compatible_available_shadows']}) for name,v in components.items()},
        'blocked':{'diesel':clean_blocked,'joint_two':two_blocked,'joint_four':four_blocked,'inputs':input_excluded},
        'peer_features_available_rows':[r['quarter'] for r in peer_combined],
        'no_current_quarter_adjustment':True,'automatic_promotion':False}
    save(output/'results.json',result)
    print(json.dumps({k:v.get('metrics') for k,v in result['results'].items()},indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path)
    evaluate(p.parse_args().out)
