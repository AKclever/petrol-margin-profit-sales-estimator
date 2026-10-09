"""One strongly regularized joint numeric-feature challenger; research only."""
import argparse
from datetime import date
import json
from pathlib import Path
from statistics import mean

from .alternative_experiments import parse_series, supply_feature
from .combined_challengers import HISTORY, CASY, ATD, crosses_diesel_break, select_peer, joint, summary
from .data import MarketWeek, load_weights
from .history_floor_basis import bounds, previous
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha

SPEC = Path('data/joint_all_features_spec_v1.json')
AUDIT = Path('data/revenue_gap_all/2026-10-07_review_v2/quarter_rows.json')
SUPPLY = Path('data/alternative_margin_experiments/2026-10-07_supply_v1')
COMBINED = Path('data/combined_challengers/2026-10-08_v2/results.json')


def market_from_json(rows):
    return [MarketWeek(date.fromisoformat(r['week']),r['region'],r['retail_cpg'],r['wholesale_cpg']) for r in rows]


def feature_row(r, history, audit, peers, engines, series, weights):
    q = r['quarter']; start,end = bounds(q); cutoff = str(end)
    if crosses_diesel_break(q):
        raise ValueError('DIESEL_SURVEY_BREAK_CROSSING')
    diesel = history['diesel'][q]; floor = history['floor'].get(q)
    if not floor:
        raise ValueError('MISSING_PUBLISHED_COST_VOLUME_FEATURE')
    prior = audit.get(previous(q))
    if not prior or prior.get('revenue_proxy_error_cpg') is None or prior['revenue_gap_available_at'] >= cutoff:
        raise ValueError('MISSING_PUBLISHED_PRIOR_REVENUE_GAP')
    cp,tp = [select_peer(p,q) for p in peers]
    if cp is None or tp is None:
        raise ValueError('MISSING_PUBLISHED_OVERLAPPING_PEER')
    old_start,old_end = bounds(f'{int(q[:4])-1}{q[4:]}')
    changes = []
    for engine in engines:
        current = engine.features(start,end); previous_features = engine.features(old_start,old_end)
        if current.coverage != 1 or previous_features.coverage != 1:
            raise ValueError('INCOMPLETE_MARKET_QUARTER')
        changes.append([a-b for a,b in zip(current.model_values(),previous_features.model_values(),strict=True)])
    grade_increment = [a-b for a,b in zip(changes[1],changes[0],strict=True)]
    supply, supply_evidence = supply_feature(series,start,end,weights)
    values = changes[0]+grade_increment+diesel['features']+[prior['revenue_proxy_error_cpg']]+supply+floor['features']+[cp['surprise_cpg'],tp['surprise_cpg']]
    if len(values) != 16:
        raise ValueError('Unexpected feature width')
    return r | {'quarter_end':cutoff,'outcome_available_at':diesel['outcome_available_at'],'features':values,
                'feature_evidence':{'floor':floor['feature_evidence'], 'gap_available_at':prior['revenue_gap_available_at'],
                    'peers':{'caseys':cp,'couchetard':tp},'supply':supply_evidence,
                    'market_role':'CURRENT_VINTAGE_NOT_HISTORICAL_AVAILABILITY_PROOF'}}


def groups(baseline, shadow, big):
    result = {}
    for name,qs in [('original_big_misses',[q for q in shadow if q in big]),('other_eligible_quarters',[q for q in shadow if q not in big])]:
        qs = sorted(qs)
        result[name] = {'quarters':qs,'n':len(qs),
            'production_mae_cpg':mean(abs(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg']) for q in qs) if qs else None,
            'joint_mae_cpg':mean(abs(shadow[q]['actual_cpg']-shadow[q]['prediction_cpg']) for q in qs) if qs else None}
    return result


def evaluate(output):
    output.mkdir(parents=True,exist_ok=False)
    normalized = HISTORY.parent/'normalized_market.json'
    inputs = [SPEC,HISTORY,CASY,ATD,AUDIT,COMBINED,normalized,SUPPLY/'manifest.json',
              Path('data/weights.csv'),Path('data/actuals.csv'),Path('data/market.csv'),Path(__file__),
              Path('musa_nowcast/combined_challengers.py'),Path('musa_nowcast/alternative_experiments.py'),
              Path('musa_nowcast/model.py'),Path('musa_nowcast/mathutils.py'),Path('musa_nowcast/timing.py')]+sorted(SUPPLY.glob('*.xls'))
    snapshots = output/'inputs';snapshots.mkdir()
    for n,p in enumerate(inputs):
        with (snapshots/f'{n}_{p.name}').open('xb') as f:f.write(p.read_bytes())
    save(output/'frozen_inputs.json',{'frozen_at':now(),'files':[{'path':str(p),'sha256':sha(p)} for p in inputs]})
    spec = json.loads(SPEC.read_text()); h = json.loads(HISTORY.read_text())
    baseline = {r['quarter']:r for r in h['baseline_rows'] if r['quarter'] >= '2021Q1'}
    history = {name:{r['quarter']:r for r in h[name]['feature_rows']} for name in ['diesel','floor']}
    audit = {r['quarter']:r for r in json.loads(AUDIT.read_text())['rows']}
    peer_rows = [json.loads(p.read_text())['peer_predictions'] for p in [CASY,ATD]]
    markets = json.loads(normalized.read_text()); weights = load_weights('data/weights.csv')
    engines = [NowcastEngine(market_from_json(markets[k]),weights,[]) for k in ['regular','all_grade']]
    series = {}
    for source in json.loads((SUPPLY/'manifest.json').read_text())['sources']:
        p = SUPPLY/f"{source['name']}.xls"
        if sha(p) != source['sha256']:
            raise ValueError('Supply source hash changed')
        series[source['name']] = parse_series(p.read_bytes(),source['series_id'])
    rows = [];excluded = []
    for q,r in sorted(baseline.items()):
        try:
            rows.append(feature_row(r,history,audit,peer_rows,engines,series,weights))
        except ValueError as exc:
            excluded.append({'quarter':q,'reason':str(exc)})
    save(output/'frozen_feature_rows.json',{'feature_names':spec['feature_order'],'rows':rows,'excluded':excluded})
    shadow,training_blocked = joint(rows)
    big = spec['big_miss_quarters_frozen_from_original']; coverage = []
    reasons = {r['quarter']:r['reason'] for r in excluded+training_blocked}
    for q in big:
        row = baseline[q]; point = shadow.get(q)
        coverage.append({'quarter':q,'actual_cpg':row['actual_cpg'],'production_prediction_cpg':row['prediction_cpg'],
            'production_abs_error_cpg':abs(row['actual_cpg']-row['prediction_cpg']),
            'joint_prediction_cpg':point['prediction_cpg'] if point else None,
            'joint_abs_error_cpg':abs(point['actual_cpg']-point['prediction_cpg']) if point else None,
            'status':'SCORED' if point else 'BLOCKED','reason':None if point else reasons.get(q,'UNRESOLVED')})
    simpler = {r['quarter']:r for r in json.loads(COMBINED.read_text())['results']['joint_clean_diesel_and_gap']['rows']}
    result = {'created_at':now(),'specification':spec,'production_changed':False,
        'feature_count':16,'complete_feature_rows':len(rows),'evaluation':summary(baseline,shadow),
        'simpler_two_feature_on_same_targets':summary(baseline,{q:simpler[q] for q in shadow}),
        'big_miss_coverage':coverage,'big_vs_other':groups(baseline,shadow,big),
        'input_exclusions':excluded,'training_exclusions':training_blocked,
        'tail_edge_demonstrated':False,'automatic_promotion':False,
        'limitations':['More features than initial training rows; ridge makes the fit possible, not trustworthy',
                       'Only one of six original big misses is scoreable; no general tail-performance claim',
                       'Previously examined history and current market vintages; not independent validation']}
    save(output/'results.json',result)
    print(json.dumps({k:result[k] for k in ['feature_count','complete_feature_rows','big_miss_coverage','big_vs_other']},indent=2))
    print(json.dumps(result['evaluation']['metrics'],indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    evaluate(p.parse_args().out)
