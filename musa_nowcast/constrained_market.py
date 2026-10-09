"""One sign-constrained production-form research challenger; no live writes."""
import argparse
import itertools
import json
import math
from pathlib import Path

from .anchor_reliability import ROOT, tail_metrics
from .data import QuarterActual, load_actuals, load_market, load_weights
from .history_floor_basis import bounds, regime
from .joint_all_features import market_from_json
from .mathutils import RidgeModel
from .model import FEATURE_NAMES, MARKET_CHANGE_SHRINKAGE, NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

SPEC = Path('data/constrained_market_spec_v1.json')
SIGNS = (1, 1, -1, 0)


class ConstrainedRidge:
    """Enumerate active faces of a convex ridge problem, not model candidates."""
    def fit(self, rows, targets):
        if not rows or len(rows) != len(targets) or any(len(r) != 4 for r in rows):
            raise ValueError('four features and matching nonempty targets required')
        if not all(math.isfinite(v) for r in rows for v in r) or not all(math.isfinite(v) for v in targets):
            raise ValueError('finite inputs required')
        best = None
        for count in range(4):
            for subset in itertools.combinations(range(3), count):
                active = tuple(sorted(subset + (3,)))
                x = [[r[i] for i in active] for r in rows]
                model = RidgeModel(2).fit(x, targets)
                if any(SIGNS[i] and c * SIGNS[i] < 0 for i, c in zip(active, model.coefficients[1:])):
                    continue
                loss = sum((y - model.predict_one(r)) ** 2 for r, y in zip(x, targets)) + 2 * sum(c*c for c in model.coefficients[1:])
                if best is None or loss < best[0]:
                    best = (loss, active, model)
        self.loss, self.active, self.model = best
        self.raw_slopes = [0.0] * 4
        for i, c, scale in zip(self.active, self.model.coefficients[1:], self.model.scales):
            self.raw_slopes[i] = c / scale
        return self

    def predict(self, row):
        return self.model.predict_one([row[i] for i in self.active])

    def export(self):
        return {'active_features': [FEATURE_NAMES[i] for i in self.active],
                'raw_slopes': dict(zip(FEATURE_NAMES, self.raw_slopes)),
                'intercept': self.model.coefficients[0], 'means': self.model.means,
                'scales': self.model.scales, 'standardized_coefficients': self.model.coefficients,
                'penalized_training_loss': self.loss, 'alpha': 2}


def predict_at(engine, index):
    rows, targets = engine._training()
    prior = engine._prior_year_index(index)
    if prior is None:
        raise ValueError('missing prior-year anchor')
    x, y = engine._change_training(rows, targets, index)
    delta = engine._changes(rows[index], rows[prior])
    model = ConstrainedRidge().fit(x, y)
    unconstrained = RidgeModel(2).fit(x, y)
    return {'prediction_cpg': targets[prior] + MARKET_CHANGE_SHRINKAGE * model.predict(delta),
            'reconstructed_production_cpg': targets[prior] + MARKET_CHANGE_SHRINKAGE * unconstrained.predict_one(delta),
            'seasonal_cpg': targets[prior], 'feature_delta': dict(zip(FEATURE_NAMES, delta)),
            'fit': model.export(), 'training_quarters': [a.quarter for a in engine.actuals[:index]],
            'yoy_training_rows': len(x)}


def evaluate(output):
    output.mkdir(parents=True, exist_ok=False)
    files = [SPEC, Path(__file__), Path('musa_nowcast/model.py'), Path('musa_nowcast/mathutils.py'),
             Path('musa_nowcast/timing.py'), Path('musa_nowcast/anchor_reliability.py'),
             Path('data/actuals.csv'), Path('data/weights.csv'), Path('data/market.csv'),
             ROOT/'historical_targets.json', ROOT/'normalized_market.json', ROOT/'results.json']
    (output/'inputs').mkdir()
    for i, p in enumerate(files):
        with (output/'inputs'/f'{i}_{p.name}').open('xb') as handle:
            handle.write(p.read_bytes())
    save(output/'frozen_inputs.json', {'frozen_at': now(), 'files': [{'path': str(p), 'sha256': sha(p)} for p in files]})
    targets = {r['quarter']: r for r in json.loads((ROOT/'historical_targets.json').read_text())['quarters']}
    baseline = {r['quarter']: r for r in json.loads((ROOT/'results.json').read_text())['baseline_rows']}
    modern = load_actuals('data/actuals.csv')
    old = [QuarterActual(q, *bounds(q), r['retail_margin_cpg']) for q, r in sorted(targets.items()) if q < '2019Q1']
    weights = load_weights('data/weights.csv')
    market = market_from_json(json.loads((ROOT/'normalized_market.json').read_text())['regular'])
    engines = [NowcastEngine(market, weights, old+modern), NowcastEngine(load_market('data/market.csv'), weights, modern)]
    frozen = {}
    for engine, modern_only in zip(engines, [False, True]):
        for i, actual in enumerate(engine.actuals):
            q = actual.quarter
            if q not in baseline or (q >= '2021Q1') != modern_only:
                continue
            for earlier in engine.actuals[:i]:
                if targets[earlier.quarter]['available_at'] >= str(actual.end):
                    raise ValueError('training target unavailable at target quarter-end')
            features = engine.features(actual.start, actual.end)
            if features.coverage != 1:
                raise ValueError('incomplete market quarter')
            result = predict_at(engine, i)
            if abs(result['reconstructed_production_cpg'] - baseline[q]['prediction_cpg']) > 1e-8:
                raise ValueError('production reproduction mismatch')
            frozen[q] = result
    if set(frozen) != set(baseline):
        raise ValueError('not all eligible quarters reconstructed')
    # Archive every prediction before calculating held-out errors.
    save(output/'frozen_predictions.json', {'frozen_at': now(), 'rows': frozen})
    shadow = {}; seasonal = {}
    for q, r in frozen.items():
        b = baseline[q]
        shadow[q] = b | r | {'production_prediction_cpg': b['prediction_cpg'],
            'direction_correct': NowcastEngine._direction(r['prediction_cpg']-r['seasonal_cpg']) == NowcastEngine._direction(b['actual_cpg']-r['seasonal_cpg']),
            'absolute_error_improvement_cpg': abs(b['actual_cpg']-b['prediction_cpg'])-abs(b['actual_cpg']-r['prediction_cpg'])}
        seasonal[q] = b | {'prediction_cpg': r['seasonal_cpg']}
    results = {}
    for era in ['earlier_low_margin', 'transition', 'later_regime']:
        qs = sorted(q for q in shadow if regime(q) == era)
        large = [q for q in qs if abs(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg']) >= 5]
        ordinary = [q for q in qs if q not in large]
        results[era] = {'quarters': qs, 'metrics': _metrics(baseline, shadow, qs),
            'tail_metrics': tail_metrics(baseline, shadow, qs), 'seasonal_baseline_comparison': tail_metrics(seasonal, shadow, qs),
            'original_large_quarters': large, 'large_group': tail_metrics(baseline, shadow, large),
            'ordinary_group': tail_metrics(baseline, shadow, ordinary),
            'new_large_errors': [q for q in ordinary if abs(shadow[q]['actual_cpg']-shadow[q]['prediction_cpg']) >= 5]}
    save(output/'results.json', {'created_at': now(), 'role': 'DEVELOPMENTAL_CURRENT_VINTAGE_NOT_PIT_VALIDATION',
        'production_changed': False, 'current_forecast_changed': False, 'automatic_promotion': False,
        'by_regime': results, 'rows': [shadow[q] for q in sorted(shadow)]})
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    evaluate(parser.parse_args().out)
