from datetime import date
from pathlib import Path

import pytest

from musa_nowcast.data import load_actuals, load_market, load_weights
from musa_nowcast.model import NowcastEngine


ROOT = Path(__file__).parents[1]


def test_caseys_history_is_reproducible_and_fails_the_trust_gate():
    engine = NowcastEngine(
        load_market(ROOT / "data" / "market.csv"),
        load_weights(ROOT / "data" / "caseys" / "weights.csv"),
        load_actuals(ROOT / "data" / "caseys" / "actuals.csv"),
    )

    result = engine.backtest()

    assert result["backtest_quarters"] == 20
    assert result["mae"] == pytest.approx(3.1176297668)
    assert result["seasonal_baseline_mae"] == pytest.approx(3.125)
    assert result["historical_mean_mae"] == pytest.approx(4.7899648118)
    assert result["directional_accuracy"] == pytest.approx(0.5)
    assert result["recent_mae"] == pytest.approx(2.5304679642)
    assert result["recent_baseline_mae"] == pytest.approx(2.575)
    assert result["recent_directional_accuracy"] == pytest.approx(0.5)
    assert result["mae_improvement"] == pytest.approx(0.0073702332)
    assert result["mae_improvement_ci_low"] == pytest.approx(-1.1536067184)
    assert result["beats_baseline"] is True
    assert result["validated"] is False


def test_caseys_does_not_invent_a_supply_rin_series():
    actuals = load_actuals(ROOT / "data" / "caseys" / "actuals.csv")

    assert all(item.supply_rin_cpg is None for item in actuals)


def test_caseys_f2027_q1_signal_is_explicitly_unvalidated():
    engine = NowcastEngine(
        load_market(ROOT / "data" / "market.csv"),
        load_weights(ROOT / "data" / "caseys" / "weights.csv"),
        load_actuals(ROOT / "data" / "caseys" / "actuals.csv"),
    )

    result = engine.forecast(
        "F2027Q1",
        date(2026, 5, 1),
        date(2026, 7, 31),
        date(2026, 8, 11),
    )

    assert result.observed_weeks == result.expected_weeks == 13
    assert result.retail_margin_cpg == pytest.approx(42.70)
    assert result.retail_low_cpg == pytest.approx(36.34)
    assert result.supply_rin_base_cpg is None
    assert result.all_in_base_cpg is None
    assert result.validated is False
    assert result.warning and "fails" in result.warning
