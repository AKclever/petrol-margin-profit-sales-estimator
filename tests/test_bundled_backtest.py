from pathlib import Path

import pytest

from musa_nowcast.data import load_actuals, load_market, load_weights
from musa_nowcast.model import NowcastEngine


ROOT = Path(__file__).parents[1]


def test_bundled_history_has_reproducible_leakage_safe_result():
    engine = NowcastEngine(
        load_market(ROOT / "data" / "market.csv"),
        load_weights(ROOT / "data" / "weights.csv"),
        load_actuals(ROOT / "data" / "actuals.csv"),
    )

    result = engine.backtest()

    assert result["backtest_quarters"] == 22
    assert result["mae"] == pytest.approx(3.1325856676)
    assert result["seasonal_baseline_mae"] == pytest.approx(4.8363636364)
    assert result["historical_mean_mae"] == pytest.approx(5.6832857992)
    assert result["directional_accuracy"] == pytest.approx(10 / 11)
    assert result["recent_mae"] == pytest.approx(2.1535152256)
    assert result["recent_baseline_mae"] == pytest.approx(2.65)
    assert result["recent_directional_accuracy"] == pytest.approx(0.75)
    assert result["mae_improvement"] == pytest.approx(1.7037779687)
    assert result["mae_improvement_ci_low"] == pytest.approx(0.6216937556)
    assert result["beats_baseline"] is True
    assert result["validated"] is True
