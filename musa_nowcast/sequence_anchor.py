"""Frozen sequence/seasonal-anchor residual correction; research only."""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import date, timedelta
from pathlib import Path

from .data import load_actuals, load_market, load_weights
from .geo import _predictions
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics
from .weekly_adjustment import PositiveRidge

SPEC = Path('data/sequence_anchor_spec_v1.json')
WEEK = timedelta(days=7)
FEATURE_NAMES = ['negative_anchor_anomaly','persistent_capture','negative_persistent_squeeze']


def calibration(model):
    # Metadata override only: the reused optimizer's original names described
    # weekly V1 features, not this residual model. No fitting rule is changed.
    return model.export() | {'feature_names':FEATURE_NAMES,
                             'constraints':'nonnegative on negative anchor anomaly, capture, negative squeeze'}


def contributions(model, row):
    result = {'intercept':.5*model.model.coefficients[0]}
    for index,coef,mean,scale in zip(model.active,model.model.coefficients[1:],
                                   model.model.means,model.model.scales):
        result[FEATURE_NAMES[index]] = .5*coef*(row[index]-mean)/scale
    return result


def regional_states(market, region):
    rows = sorted((r for r in market if r.region == region), key=lambda r:r.week)
    result = {}
    previous = None
    capture = squeeze = 0.
    transitions = 0
    for row in rows:
        if previous is None or row.week-previous.week != WEEK:
            capture = squeeze = 0.
            transitions = 0
        else:
            wholesale = row.wholesale_cpg-previous.wholesale_cpg
            retail = row.retail_cpg-previous.retail_cpg
            capture_impulse = max(retail-wholesale,0.) if wholesale < 0 else 0.
            squeeze_impulse = max(wholesale-retail,0.) if wholesale > 0 else 0.
            capture = .8*capture+capture_impulse
            squeeze = .8*squeeze+squeeze_impulse
            transitions += 1
            result[row.week] = {'capture':capture,'squeeze':squeeze,'transitions':transitions,
                                'capture_impulse':capture_impulse,'squeeze_impulse':squeeze_impulse}
        previous = row
    return result


def anchor_anomaly(history, quarter):
    earlier = sorted((a for a in history if a.quarter < quarter and a.quarter[-1] == quarter[-1]),
                     key=lambda a:a.quarter)[-3:]
    prior_key = f'{int(quarter[:4])-1}Q{quarter[-1]}'
    prior = next((a for a in earlier if a.quarter == prior_key),None)
    if prior is None:
        raise ValueError('missing prior-year seasonal anchor')
    values = [a.retail_margin_cpg for a in earlier]
    median = statistics.median(values)
    anomaly = prior.retail_margin_cpg-median if len(values) >= 2 else 0.
    return anomaly, {'prior_year_margin_cpg':prior.retail_margin_cpg,
                     'earlier_seasonal_quarters':[a.quarter for a in earlier],
                     'earlier_seasonal_median_cpg':median,'anchor_anomaly_cpg':anomaly}


def features(engine, history, quarter, start, end, paths):
    basket = engine._weekly_basket(start,end)
    expected = engine.features(start,end).expected_weeks
    if len(basket) != expected:
        raise ValueError('missing internal complete market week')
    anomaly, anchor = anchor_anomaly(history,quarter)
    regional = []
    for region, weight in engine.weights.items():
        states = []
        for week,_,_ in basket:
            if week not in paths[region] or paths[region][week]['transitions'] < 8:
                raise ValueError('missing regional state or insufficient warmup')
            states.append(paths[region][week])
        regional.append({'region':region,'weight':weight,
                         'persistent_capture_cpg':statistics.mean(r['capture'] for r in states),
                         'persistent_squeeze_cpg':statistics.mean(r['squeeze'] for r in states)})
    capture = sum(r['weight']*r['persistent_capture_cpg'] for r in regional)
    squeeze = sum(r['weight']*r['persistent_squeeze_cpg'] for r in regional)
    return [-anomaly,capture,-squeeze], anchor | {'regional_sequence':regional,'complete_weeks':len(basket)}


def fit_correction(rows, quarter):
    earlier = sorted((r for r in rows if r['quarter'] < quarter),key=lambda r:r['quarter'])
    if len(earlier) < 8:
        raise ValueError('insufficient eight earlier out-of-fold residuals')
    model = PositiveRidge().fit([r['features'] for r in earlier],
                               [r['actual_cpg']-r['prediction_cpg'] for r in earlier])
    return model, earlier


def evaluate(output):
    output.mkdir(parents=True,exist_ok=False)
    inputs = list(map(Path,['data/market.csv','data/weights.csv','data/actuals.csv']))
    market, weights, actuals = load_market(inputs[0]),load_weights(inputs[1]),load_actuals(inputs[2])
    if any(a.quarter >= '2026Q3' for a in actuals):
        raise ValueError('target or future outcome in input')
    engine = NowcastEngine(market,weights,actuals)
    paths = {w.region:regional_states(market,w.region) for w in weights}
    indexed = {a.quarter:a for a in actuals}
    residuals = []
    for row in _predictions(engine):
        actual = indexed[row['quarter']]
        feature, detail = features(engine,actuals,actual.quarter,actual.start,actual.end,paths)
        residuals.append(row | {'features':feature,'feature_details':detail})
    challenger, excluded = {}, []
    for row in residuals:
        quarter = row['quarter']
        earlier = [r for r in residuals if r['quarter'] < quarter]
        if len(earlier) < 8:
            excluded.append({'quarter':quarter,'reason':'insufficient earlier OOF residuals'})
            continue
        model, training = fit_correction(residuals,quarter)
        correction = .5*model.predict_one(row['features'])
        point = row['prediction_cpg']+correction
        prior = row['seasonal_cpg']
        challenger[quarter] = {'quarter':quarter,'actual_cpg':row['actual_cpg'],'prediction_cpg':point,
          'production_prediction_cpg':row['prediction_cpg'],'correction_cpg':correction,
          'direction_correct': (point>prior)-(point<prior) == (row['actual_cpg']>prior)-(row['actual_cpg']<prior),
          'training_residual_quarters':[r['quarter'] for r in training],
          'calibration':calibration(model),'features':row['features'],'feature_details':row['feature_details'],
          'production_abs_error_cpg':abs(row['actual_cpg']-row['prediction_cpg']),
          'challenger_abs_error_cpg':abs(row['actual_cpg']-point)}
    production = {r['quarter']:r for r in residuals}
    common = sorted(challenger)
    metrics = _metrics(production,challenger,common)
    for row in challenger.values():
        row['paired_abs_error_improvement_cpg'] = row['production_abs_error_cpg']-row['challenger_abs_error_cpg']
    model, training = fit_correction(residuals,'2026Q3')
    feature, detail = features(engine,actuals,'2026Q3',date(2026,7,1),date(2026,9,30),paths)
    production_point = engine.forecast('2026Q3',date(2026,7,1),date(2026,9,30),date(2026,10,7)).retail_margin_cpg
    correction = .5*model.predict_one(feature)
    spec = json.loads(SPEC.read_text())
    snapshot_paths = inputs+[SPEC,Path(__file__),Path('musa_nowcast/weekly_adjustment.py'),
                            Path('musa_nowcast/model.py'),Path('musa_nowcast/mathutils.py'),
                            Path('musa_nowcast/timing.py'),Path('musa_nowcast/geo.py')]
    result = {'model_id':spec['model_id'],'forecast_created_at':now(),'quarter':'2026Q3',
      'evaluation_role':spec['evaluation_role'],'production_same_inputs_cpg':production_point,
      'retail_margin_cpg':production_point+correction,'correction_cpg':correction,'features':feature,
      'feature_details':detail,'calibration':calibration(model),'correction_contributions_cpg':contributions(model,feature),
      'training_residual_quarters':[r['quarter'] for r in training],
      'metrics':metrics,'eventual_actual_margin_cpg':None,'production_changed':False,'automatic_promotion':False,
      'specification':spec,'input_hashes':{str(p):sha(p) for p in snapshot_paths}}
    save(output/'forecast.json',result)
    save(output/'backtest.json',{'evaluation_role':spec['evaluation_role'],'metrics':metrics,
                               'rows':[challenger[q] for q in common],'excluded':excluded})
    save(output/'production_oof_residuals.json',{'rows':residuals})
    (output/'inputs').mkdir()
    for path in snapshot_paths:
        with (output/'inputs'/path.name).open('xb') as handle:
            handle.write(path.read_bytes())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    result = evaluate(args.output)
    print(json.dumps({k:result[k] for k in ['retail_margin_cpg','production_same_inputs_cpg','correction_cpg','metrics']},indent=2))


if __name__ == '__main__':
    main()
