"""Constrained causal state-space research challenger; never production."""
from __future__ import annotations

import argparse
import json
import math
from datetime import date, timedelta
from pathlib import Path

from .data import load_actuals, load_market, load_weights
from .geo import _predictions
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .weekly_adjustment import load_demand, quarterly_path
from .timing import _metrics

SPEC = Path('data/state_space_spec_v1.json')
WEEK = timedelta(days=7)


def kalman_update(mean, variance, observation, noise):
    if not all(math.isfinite(x) for x in (mean, variance, observation, noise)) or variance < 0 or noise <= 0:
        raise ValueError('invalid Kalman input')
    gain = variance / (variance + noise)
    return mean + gain * (observation - mean), (1 - gain) * variance


def fit_pricing(market, region, cutoff):
    """Earlier regional history only; bounded convex ridge solution per sign."""
    rows = sorted((m for m in market if m.region == region and m.week + timedelta(days=4) <= cutoff),
                  key=lambda m: m.week)
    if len(rows) < 30:
        raise ValueError('insufficient regional training history')
    equilibrium = sum(r.retail_cpg-r.wholesale_cpg for r in rows)/len(rows)
    xy = [0., 0.]
    xx = [0., 0.]
    for previous, current in zip(rows, rows[1:]):
        if current.week - previous.week != WEEK:
            continue
        gap = current.wholesale_cpg + equilibrium - previous.retail_cpg
        side = 0 if gap >= 0 else 1
        xy[side] += gap * (current.retail_cpg - previous.retail_cpg)
        xx[side] += gap * gap
    speeds = [min(1., max(0., (x+100*.35)/(v+100))) for x,v in zip(xy,xx)]
    return {'equilibrium_spread_cpg': equilibrium, 'rise_speed': speeds[0], 'fall_speed': speeds[1],
            'last_training_week': str(rows[-1].week), 'training_week_count': len(rows)}


def filter_region(market, region, pricing, cost_q, cutoff):
    """Forward-only cost and asymmetric pump-price filters, no smoother."""
    rows = sorted((m for m in market if m.region == region and m.week + timedelta(days=4) <= cutoff),
                  key=lambda m: m.week)
    result = {}
    previous = None
    for row in rows:
        if previous is None or row.week - previous.week != WEEK:
            cost, pump = row.wholesale_cpg, row.retail_cpg
            cost_var, pump_var = 25., 4.
        else:
            cost, cost_var = kalman_update(cost, cost_var+cost_q, row.wholesale_cpg, 25.)
            gap = cost + pricing['equilibrium_spread_cpg'] - pump
            speed = pricing['rise_speed'] if gap >= 0 else pricing['fall_speed']
            pump_prior = pump + speed*gap
            # Approximate independent scalar filters: cost variance is propagated,
            # but cross-covariance and pricing-parameter uncertainty are not.
            pump_prior_var = (1-speed)**2*pump_var + speed**2*cost_var + 9.
            pump, pump_var = kalman_update(pump_prior, pump_prior_var, row.retail_cpg, 4.)
        result[row.week] = {'latent_cost_cpg': cost, 'latent_regional_retail_cpg': pump,
                           'latent_spread_cpg': pump-cost, 'cost_variance': cost_var,
                           'retail_variance': pump_var}
        previous = row
    return result


def aggregate(records, paths):
    """Use frozen V1 gallon weights, with an explicit final-week carry."""
    output = []
    for record in records:
        source = date.fromisoformat(record['demand_source_week'])
        state = paths[record['region']][source]
        output.append(record | state)
    spread = sum(r['gallon_weight_proxy']*r['latent_spread_cpg'] for r in output)
    return spread, output


def offset_state(history, spreads, season):
    # Each seasonal company-vs-proxy offset is a random walk across years.
    mean, variance = 0., 100.
    last_year = None
    updates = []
    for actual in history:
        if int(actual.quarter[-1]) != season:
            continue
        elapsed = 0 if last_year is None else actual.start.year-last_year
        mean, variance = kalman_update(mean, variance+4*elapsed,
                                        actual.retail_margin_cpg-spreads[actual.quarter], 4.)
        updates.append({'quarter': actual.quarter, 'offset_mean_cpg': mean, 'offset_variance': variance})
        last_year = actual.start.year
    return mean, variance, last_year, updates


def predict(market, weights, demand, history, target, cost_q):
    if not history or history[-1].end >= target[1]:
        raise ValueError('training must end before forecast quarter')
    cutoff = target[2]
    pricing = {w.region: fit_pricing(market, w.region, history[-1].end) for w in weights}
    paths = {w.region: filter_region(market,w.region,pricing[w.region],cost_q,cutoff) for w in weights}
    spreads = {}
    for actual in history:
        _, records = quarterly_path(market,weights,demand,actual.start,actual.end)
        spreads[actual.quarter], _ = aggregate(records,paths)
    _, records = quarterly_path(market,weights,demand,target[1],target[2])
    spread, weekly = aggregate(records,paths)
    mean, variance, year, updates = offset_state(history,spreads,int(target[0][-1]))
    if year is None:
        raise ValueError('no seasonal offset observations')
    variance += 4*(target[1].year-year)
    for row in weekly:
        row['latent_company_margin_cpg'] = row['latent_spread_cpg']+mean
    point = spread+mean
    if abs(sum(r['gallon_weight_proxy']*r['latent_company_margin_cpg'] for r in weekly)-point) > 1e-9:
        raise ValueError('weekly-quarter reconciliation failure')
    return {'prediction_cpg': point, 'proxy_spread_cpg': spread, 'company_basis_offset_cpg': mean,
            'offset_state_variance_only': variance, 'pricing': pricing, 'offset_updates': updates,
            'last_training_quarter': history[-1].quarter}, weekly


def evaluate(output, demand_path):
    output.mkdir(parents=True, exist_ok=False)
    spec = json.loads(SPEC.read_text())
    market_path, weights_path, actuals_path = map(Path,['data/market.csv','data/weights.csv','data/actuals.csv'])
    market, weights, actuals = load_market(market_path),load_weights(weights_path),load_actuals(actuals_path)
    if any(a.quarter >= '2026Q3' for a in actuals):
        raise ValueError('target or future company actual in input')
    demand = load_demand(demand_path)
    # Match weekly V1's established warmup eligibility; fail on internal gaps.
    history = [a for a in actuals if a.quarter >= '2019Q2']
    champion = NowcastEngine(market,weights,actuals)
    production = {r['quarter']:r for r in _predictions(champion)}
    predictions = {}
    for index in range(spec['minimum_training_quarters'], len(history)):
        heldout = history[index]
        result, _ = predict(market,weights,demand,history[:index],
                            (heldout.quarter,heldout.start,heldout.end),spec['central_cost_process_variance'])
        prior = next(a for a in history[:index] if a.quarter == f'{heldout.start.year-1}Q{heldout.quarter[-1]}')
        point = result['prediction_cpg']
        predictions[heldout.quarter] = result | {'quarter': heldout.quarter,'actual_cpg':heldout.retail_margin_cpg,
          'direction_correct': (point>prior.retail_margin_cpg)-(point<prior.retail_margin_cpg) ==
          (heldout.retail_margin_cpg>prior.retail_margin_cpg)-(heldout.retail_margin_cpg<prior.retail_margin_cpg)}
    common = sorted(set(predictions)&set(production))
    metrics = _metrics(production,predictions,common)
    scenarios = {}
    for name, cost_q in spec['fixed_cost_scenarios'].items():
        result, weekly = predict(market,weights,demand,history,('2026Q3',date(2026,7,1),date(2026,9,30)),cost_q)
        scenarios[name] = result
        save(output/f'weekly_{name}.json', {'latent_allocations_not_observed_company_margins':weekly})
    point = scenarios['central']['prediction_cpg']
    result = {'model_id':spec['model_id'], 'forecast_created_at':now(), 'quarter':'2026Q3',
      'evaluation_role':'Q3_2026_POST_PATH_RETROSPECTIVE_RESEARCH_SHADOW',
      'retail_margin_cpg':point, 'production_same_inputs_cpg':champion.forecast('2026Q3',date(2026,7,1),date(2026,9,30),date.today()).retail_margin_cpg,
      'eventual_actual_margin_cpg':None, 'production_changed':False,'automatic_promotion':False,
      'scenarios':scenarios,'scenario_range_not_confidence_interval':[min(r['prediction_cpg'] for r in scenarios.values()),max(r['prediction_cpg'] for r in scenarios.values())],
      'metrics':metrics,'specification':spec,
      'input_hashes':{str(p):sha(p) for p in [market_path,weights_path,actuals_path,demand_path,SPEC,Path(__file__),Path('musa_nowcast/weekly_adjustment.py')]}}
    save(output/'backtest.json',{'evaluation_role':spec['evaluation_role'],'metrics':metrics,
      'rows':[predictions[q]|{'production_prediction_cpg':production[q]['prediction_cpg']} for q in common]})
    (output/'inputs').mkdir()
    for path in [market_path,weights_path,actuals_path,demand_path,SPEC,Path(__file__),
                 Path('musa_nowcast/weekly_adjustment.py'),Path('musa_nowcast/model.py'),
                 Path('musa_nowcast/mathutils.py'),Path('musa_nowcast/geo.py'),Path('musa_nowcast/timing.py')]:
        with (output/'inputs'/path.name).open('xb') as handle:
            handle.write(path.read_bytes())
    save(output/'forecast.json',result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--demand',type=Path,default=Path('data/weekly_adjustment/q3_2026_v1_run2/national_demand.xls'))
    args = parser.parse_args()
    result = evaluate(args.output,args.demand)
    print(json.dumps({k:result[k] for k in ['retail_margin_cpg','production_same_inputs_cpg','scenario_range_not_confidence_interval','metrics']},indent=2))


if __name__ == '__main__':
    main()
