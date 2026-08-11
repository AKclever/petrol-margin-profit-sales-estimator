import pytest

from musa_nowcast.mathutils import RidgeModel, percentile


def test_ridge_model_finds_simple_relationship():
    rows = [[value] for value in range(10)]
    targets = [10 + value * 2 for value in range(10)]
    model = RidgeModel(alpha=0.01).fit(rows, targets)
    assert model.predict_one([5]) == pytest.approx(20, abs=0.05)


def test_percentile_interpolates():
    assert percentile([1, 2, 3, 4, 5], 0.25) == 2
    assert percentile([1, 3], 0.5) == 2

