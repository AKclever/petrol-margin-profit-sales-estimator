from dataclasses import replace
import json
import math

import pytest

from musa_nowcast.constrained_market import ConstrainedRidge, SIGNS, predict_at
from musa_nowcast.data import load_actuals, load_market, load_weights
from musa_nowcast.mathutils import RidgeModel
from musa_nowcast.model import NowcastEngine


def test_constraints_and_monotonicity():
    rows = [[math.sin(i), math.cos(i), i/5, (-1)**i] for i in range(20)]
    targets = [-r[0]-2*r[1]+3*r[2]+r[3] for r in rows]
    model = ConstrainedRidge().fit(rows, targets)
    assert all(not sign or slope*sign >= 0 for sign, slope in zip(SIGNS, model.raw_slopes))
    for i, sign in enumerate(SIGNS[:3]):
        before = [0., 0., 0., 0.]; after = before.copy(); after[i] = 1.
        assert sign*(model.predict(after)-model.predict(before)) >= -1e-12


def test_feasible_unconstrained_solution_is_unchanged():
    rows = [[math.sin(i), math.cos(i), math.sin(i/3), math.cos(i/4)] for i in range(30)]
    targets = [2*r[0]+3*r[1]-4*r[2]+r[3] for r in rows]
    unconstrained = RidgeModel(2).fit(rows, targets)
    assert all(c*s >= 0 for c,s in zip(unconstrained.coefficients[1:3+1], SIGNS[:3]))
    constrained = ConstrainedRidge().fit(rows, targets)
    for row in rows:
        assert constrained.predict(row) == pytest.approx(unconstrained.predict_one(row))


def test_held_out_and_future_targets_cannot_change_prediction():
    engine = NowcastEngine(load_market('data/market.csv'), load_weights('data/weights.csv'), load_actuals('data/actuals.csv'))
    index = next(i for i,a in enumerate(engine.actuals) if a.quarter == '2022Q1')
    before = predict_at(engine, index)
    for i in range(index, len(engine.actuals)):
        engine.actuals[i] = replace(engine.actuals[i], retail_margin_cpg=1000.)
    after = predict_at(engine, index)
    assert before == after


def test_invalid_inputs_block():
    for rows, targets in [([], []), ([[1,2]], [1]), ([[1,2,3,float('nan')]], [1]), ([[1,2,3,4]], [])]:
        with pytest.raises(ValueError):
            ConstrainedRidge().fit(rows, targets)


def test_all_archived_quarters_and_no_promotion():
    result = json.loads(open('data/constrained_market/2026-10-08_v1/results.json').read())
    assert len(result['rows']) == 44
    modern = result['by_regime']['later_regime']
    assert len(modern['quarters']) == 22
    assert len(modern['original_large_quarters']) == 6
    assert modern['new_large_errors'] == []
    assert not modern['metrics']['passes_pre_registered_gate']
    assert not result['production_changed'] and not result['current_forecast_changed']
    for r in result['rows']:
        assert all(q < r['quarter'] for q in r['training_quarters'])
        assert r['reconstructed_production_cpg'] == pytest.approx(r['production_prediction_cpg'], abs=1e-8)
        assert r['fit']['raw_slopes']['spread'] >= 0
        assert r['fit']['raw_slopes']['falling_capture'] >= 0
        assert r['fit']['raw_slopes']['rising_squeeze'] <= 0
