from datetime import date
from pathlib import Path

from musa_nowcast.data import load_actuals, load_market, load_weights
from musa_nowcast.model import NowcastEngine
from musa_nowcast.risk import SPEC_ID, assess


ROOT = Path(__file__).parents[1]


def test_risk_monitor_is_diagnostic_only():
    engine = NowcastEngine(
        load_market(ROOT / "data" / "market.csv"),
        load_weights(ROOT / "data" / "weights.csv"),
        load_actuals(ROOT / "data" / "actuals.csv"),
    )

    result = assess(engine, date(2026, 7, 1), date(2026, 9, 30), date(2026, 9, 30))

    assert result["spec_id"] == SPEC_ID
    assert result["point_forecast_changed"] is False
    assert result["overall_risk"] in {"NORMAL", "ELEVATED"}
    assert set(result["risks"]) == {
        "rising_squeeze_risk", "falling_capture_expansion", "anchor_reversal_risk",
        "structural_capture_uncertainty",
    }
    assert result["risks"]["rising_squeeze_risk"]["orientation"] == "OVER_ESTIMATE_RISK"
    assert result["risks"]["falling_capture_expansion"]["orientation"] == "UNDER_ESTIMATE_RISK"
