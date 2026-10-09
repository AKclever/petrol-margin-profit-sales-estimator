"""Two-path, low-parameter economic research estimator. Production is untouched."""
import argparse
from datetime import date, datetime, timezone
import itertools
import json
import math
from pathlib import Path

from .anchor_reliability import ROOT, tail_metrics
from .data import load_actuals, load_market, load_weights
from .history_floor_basis import bounds
from .mathutils import RidgeModel
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics
from .uncertain_quarter import mechanical_replay, modelled_gallon_share_replay
from .weekly_adjustment import load_demand, quarterly_path, WeeklyError

SPEC = Path('data/simple_economic_spec_v1.json')
DEMAND = Path('data/weekly_adjustment/q3_2026_v1_run2/national_demand.xls')
REPLAY = Path('data/historical_pit/2025Q2/2025-06-16/rule_replay_v1')


class EconomicCalibration:
    """Two nonnegative slopes plus an unpenalized intercept, fixed alpha=2."""
    def fit(self, rows, targets):
        if not rows or any(len(row) != 2 for row in rows):
            raise ValueError('two economic features required')
        if len(rows) != len(targets) or not all(math.isfinite(v) for row in rows for v in row) or not all(math.isfinite(y) for y in targets):
            raise ValueError('invalid calibration inputs')
        best = None
        for count in range(3):
            for active in itertools.combinations(range(2), count):
                x = [[row[i] for i in active] for row in rows]
                model = RidgeModel(2).fit(x, targets)
                if any(c < 0 for c in model.coefficients[1:]):
                    continue
                loss = sum((y-model.predict_one(row))**2 for row,y in zip(x,targets)) + 2*sum(c*c for c in model.coefficients[1:])
                if best is None or loss < best[0]:
                    best = loss, active, model
        _, self.active, self.model = best
        return self

    def predict(self, row):
        return self.model.predict_one([row[i] for i in self.active])

    def export(self):
        return {'active_features': self.active, 'standardized_coefficients': self.model.coefficients,
                'means': self.model.means, 'scales': self.model.scales, 'alpha': 2}


def two_features(row):
    return [row[0], row[1]+row[2]]  # weekly V1 stores negative squeeze and positive capture


def fit_at(quarter, targets, features):
    start, end = bounds(quarter)
    eligible = sorted(q for q,r in targets.items() if q in features and
                      r['quarter_end'] < str(start) and r['available_at'] < str(end))[-8:]
    if len(eligible) < 8:
        raise ValueError('FEWER_THAN_EIGHT_PUBLISHED_FEATURE_COMPLETE_QUARTERS')
    model = EconomicCalibration().fit([features[q] for q in eligible],
                                      [targets[q]['retail_margin_cpg'] for q in eligible])
    return model, eligible


def route_forecast(market_forecast_cpg, production_cpg, disclosure=None, *, allow_modelled=False):
    """Explicit research router; incompatible or incomplete disclosures block."""
    if not all(math.isfinite(v) for v in [market_forecast_cpg, production_cpg]):
        raise ValueError('finite forecasts required')
    if disclosure is None:
        return {'status': 'MARKET_ONLY', 'shadow_forecast_cpg': market_forecast_cpg,
                'production_forecast_cpg': production_cpg, 'production_changed': False}
    r = dict(disclosure)
    if not r.get('disclosure_verified'):
        return {'status': 'BLOCKED_UNVERIFIED_DISCLOSURE'}
    if r.get('disclosed_target') != 'retail_margin' or r.get('remaining_target') != 'retail_margin':
        return {'status': 'BLOCKED_INCOMPATIBLE_MARGIN_BASIS'}
    if not r.get('input_hashes'):
        return {'status': 'BLOCKED_MISSING_EVIDENCE_HASHES'}
    share = r.get('observed_gallon_share')
    if share is None:
        return {'status': 'BLOCKED_MISSING_OBSERVED_GALLON_SHARE'}
    if not r.get('gallon_share_method'):
        return {'status': 'BLOCKED_MISSING_GALLON_SHARE_METHOD'}
    if r.get('remaining_margin_estimate_cpg') is None:
        return {'status': 'BLOCKED_MISSING_REMAINING_PERIOD_ESTIMATE'}
    for field in ['observed_gallon_share', 'remaining_margin_estimate_cpg',
                  'disclosed_margin_low_cpg', 'disclosed_margin_high_cpg']:
        if field not in r or not math.isfinite(float(r[field])):
            raise ValueError('finite numeric inputs required')
    cutoff = r.get('remaining_forecast_information_cutoff')
    if not cutoff or not r.get('remaining_forecast_created_at'):
        return {'status': 'BLOCKED_MISSING_REMAINING_FORECAST_TIMESTAMPS'}
    def parsed(value):
        if len(value) == 10:
            return datetime.combine(date.fromisoformat(value), datetime.min.time(), timezone.utc)
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None:
            raise ValueError('intraday timestamps must include timezone')
        return result
    if not r.get('production_information_cutoff') or not r.get('gallon_share_information_cutoff'):
        return {'status': 'BLOCKED_MISSING_COMPONENT_INFORMATION_CUTOFFS'}
    if parsed(r['production_information_cutoff']) != parsed(cutoff) or parsed(r['remaining_market_forecast_as_of']) != parsed(cutoff):
        raise ValueError('production and remaining forecasts require the same information cutoff')
    if parsed(r['gallon_share_information_cutoff']) > parsed(cutoff):
        raise ValueError('gallon share uses information after cutoff')
    if r.get('gallon_share_as_of') and parsed(r['gallon_share_as_of']) > parsed(cutoff):
        raise ValueError('gallon share as_of after cutoff')
    if parsed(r['disclosure_available_at']) > parsed(cutoff):
        raise ValueError('disclosure after remaining forecast information cutoff')
    if parsed(r['remaining_forecast_created_at']) < parsed(cutoff):
        raise ValueError('forecast creation before information cutoff')
    start,end = bounds(r['quarter'])
    if parsed(r['disclosure_period_start']).date() != start or parsed(r['remaining_period_end']).date() != end:
        raise ValueError('disclosed and remaining periods must span target quarter')
    if (parsed(r['remaining_period_start']).date()-parsed(r['disclosure_period_end']).date()).days != 1:
        raise ValueError('disclosed and remaining periods must partition quarter')
    r['production_forecast_at_same_as_of'] = production_cpg
    # Explicit prechecks avoid relying on the legacy replay's lexicographic timestamps.
    if parsed(r['disclosure_available_at']) < parsed(r['disclosure_period_end']):
        raise ValueError('disclosure before observed period end')
    for key in ['disclosure_available_at', 'remaining_market_forecast_as_of']:
        r[key] = parsed(r[key]).astimezone(timezone.utc).isoformat()
    result = (modelled_gallon_share_replay if allow_modelled else mechanical_replay)(r)
    result['production_changed'] = False
    return result


def disclosure_example():
    forecast = json.loads((REPLAY/'forecast.json').read_text())
    score = json.loads((REPLAY/'scoring/score.json').read_text())
    if sha(REPLAY/'forecast.json') != score['frozen_forecast_sha256']:
        raise ValueError('frozen disclosure forecast score hash mismatch')
    reconstructed = forecast['observed_gallon_share']*forecast['disclosed_margin_cpg'] + forecast['remaining_gallon_share']*forecast['remaining_margin_forecast']
    if abs(reconstructed-forecast['shadow_forecast']) > 1e-9:
        raise ValueError('archived mechanical weighted average mismatch')
    return {'role': 'RETROSPECTIVE_MECHANICAL_REPLAY', 'source': str(REPLAY),
            'forecast_sha256': sha(REPLAY/'forecast.json'), 'score_sha256': sha(REPLAY/'scoring/score.json'),
            'new_replay_or_validation': False, 'strict_replay_status': forecast['strict_replay_status'],
            'gallon_share_evidence_type': forecast['gallon_share_evidence_type'],
            'gallon_share_method': forecast['gallon_share_method'],
            'observed_gallon_share': forecast['observed_gallon_share'],
            'remaining_margin_forecast_cpg': forecast['remaining_margin_forecast'],
            'recomputed_shadow_forecast_cpg': reconstructed, 'archived_score': score,
            'limitations': forecast['limitations']}


def evaluate(output):
    output.mkdir(parents=True, exist_ok=False)
    paths = [SPEC, Path(__file__), Path('data/market.csv'), Path('data/weights.csv'),
             Path('data/actuals.csv'), ROOT/'historical_targets.json', ROOT/'results.json', DEMAND,
             Path('musa_nowcast/weekly_adjustment.py'), Path('musa_nowcast/mathutils.py'),
             Path('musa_nowcast/uncertain_quarter.py'), REPLAY/'forecast.json', REPLAY/'scoring/score.json']
    (output/'inputs').mkdir()
    for i,p in enumerate(paths):
        with (output/'inputs'/f'{i}_{p.name}').open('xb') as handle:
            handle.write(p.read_bytes())
    save(output/'frozen_inputs.json', {'created_at': now(), 'files': [{'path': str(p), 'sha256': sha(p)} for p in paths]})
    market, weights = load_market('data/market.csv'), load_weights('data/weights.csv')
    demand = load_demand(DEMAND)
    targets = {r['quarter']:r for r in json.loads((ROOT/'historical_targets.json').read_text())['quarters']}
    baseline = {r['quarter']:r for r in json.loads((ROOT/'results.json').read_text())['baseline_rows']}
    features, paths_by_quarter, exclusions = {}, {}, []
    for actual in load_actuals('data/actuals.csv'):
        try:
            x, records = quarterly_path(market, weights, demand, actual.start, actual.end)
            features[actual.quarter] = two_features(x)
            paths_by_quarter[actual.quarter] = records
        except WeeklyError as exc:
            exclusions.append({'quarter': actual.quarter, 'reason': str(exc)})
    predictions, blocked = {}, []
    for q in sorted(q for q in baseline if q >= '2021Q1'):
        try:
            if q not in features:
                raise ValueError('MISSING_WEEKLY_FEATURES')
            model, training = fit_at(q, targets, features)
            predictions[q] = {'quarter': q, 'prediction_cpg': model.predict(features[q]),
                              'training_quarters': training, 'calibration': model.export()}
        except ValueError as exc:
            blocked.append({'quarter': q, 'reason': str(exc)})
    save(output/'frozen_unscored_predictions.json', {'rows': list(predictions.values()), 'blocked': blocked})
    for q,r in predictions.items():
        b = baseline[q]
        r.update(actual_cpg=b['actual_cpg'], production_prediction_cpg=b['prediction_cpg'],
                 direction_correct=NowcastEngine._direction(r['prediction_cpg']-b['seasonal_cpg']) == NowcastEngine._direction(b['actual_cpg']-b['seasonal_cpg']))
    common = sorted(predictions)
    large = [q for q in common if abs(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg']) >= 5]
    ordinary = [q for q in common if q not in large]
    x, records = quarterly_path(market, weights, demand, date(2026,7,1), date(2026,9,30))
    model, training = fit_at('2026Q3', targets, features)
    point = model.predict(two_features(x))
    allocations = [r | {'inferred_margin_cpg': model.predict(two_features(r['features']))} for r in records]
    if abs(sum(r['gallon_weight_proxy']*r['inferred_margin_cpg'] for r in allocations)-point) > 1e-9:
        raise ValueError('weekly allocations do not reconcile')
    save(output/'q3_2026_weekly.json', {'weekly_company_margins_observed': False, 'rows': allocations})
    result = {'created_at': now(), 'role': 'DEVELOPMENTAL_CURRENT_VINTAGE_NOT_PIT_VALIDATION',
              'production_changed': False, 'automatic_promotion': False,
              'metrics': _metrics(baseline,predictions,common), 'tail_metrics': tail_metrics(baseline,predictions,common),
              'large_group': tail_metrics(baseline,predictions,large), 'ordinary_group': tail_metrics(baseline,predictions,ordinary),
              'original_large_error_quarters': large, 'rows': list(predictions.values()), 'blocked': blocked, 'feature_exclusions': exclusions,
              'q3_2026': {'role': 'Q3_2026_POST_PATH_RESEARCH_SHADOW', 'retail_margin_cpg': point,
                          'eventual_actual_margin_cpg': None, 'training_quarters': training, 'calibration': model.export(),
                          'gallon_basis': 'NATIONAL_DEMAND_AND_REGIONAL_STORE_WEIGHT_PROXY'},
              'disclosure_example': disclosure_example()}
    save(output/'results.json', result)
    print(json.dumps({k:result[k] for k in ['metrics','tail_metrics','large_group','ordinary_group','q3_2026']},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    evaluate(parser.parse_args().out)
