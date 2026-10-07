"""Pre-registered market-to-margin regime-risk diagnostics.

This module deliberately does not alter the production margin forecast. It records possible
failure modes that must accumulate prospective evidence before they can influence a point
estimate.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .data import RegionWeight, load_actuals, load_market, load_weights
from .mathutils import percentile
from .model import AdaptiveNowcastEngine, NowcastEngine, QuarterFeatures


SPEC_ID = "MUSA_MARGIN_REGIME_RISK_V1"
WEEKLY_MOVE_CPG = 5.0
CAPTURE_GAP_CPG = 4.0
ANCHOR_EXTREME_PERCENTILE = 0.80
ANCHOR_REVERSAL_CPG = 25.0
STRUCTURAL_MARGIN_SHIFT_CPG = 5.0
OOD_HIGH_Z = 2.0


def _level(value: float, medium: float, high: float) -> str:
    if value >= high:
        return "HIGH"
    if value >= medium:
        return "MEDIUM"
    return "LOW"


def _moves(engine: NowcastEngine, start: date, end: date, as_of: date) -> list[tuple[float, float]]:
    basket = engine._weekly_basket(start, end, as_of)
    return [(retail - old_retail, wholesale - old_wholesale)
            for (_, old_retail, old_wholesale), (_, retail, wholesale) in zip(basket, basket[1:])]


def _anchor_risk(
    engine: NowcastEngine, features: QuarterFeatures, start: date
) -> dict[str, object]:
    prior = engine._seasonal_margin(start)
    history = [item.retail_margin_cpg for item in engine.actuals if item.start < start]
    anchor_percentile = sum(value <= prior for value in history) / len(history)
    prior_start = date(start.year - 1, start.month, start.day)
    # Use the company-reported prior quarter dates, not an assumed calendar length.
    prior_actual = next(item for item in engine.actuals if item.start == prior_start)
    prior_features = engine.features(prior_actual.start, prior_actual.end)
    change_difference = features.wholesale_change - prior_features.wholesale_change
    high_anchor = anchor_percentile >= ANCHOR_EXTREME_PERCENTILE
    low_anchor = anchor_percentile <= 1.0 - ANCHOR_EXTREME_PERCENTILE
    opposite = ((high_anchor and change_difference <= -ANCHOR_REVERSAL_CPG)
                or (low_anchor and change_difference >= ANCHOR_REVERSAL_CPG))
    level = "HIGH" if opposite else ("MEDIUM" if high_anchor or low_anchor else "LOW")
    return {
        "level": level,
        "orientation": "BIDIRECTIONAL",
        "prior_year_margin_cpg": round(prior, 2),
        "prior_year_margin_percentile": round(anchor_percentile, 3),
        "wholesale_change_difference_cpg": round(change_difference, 2),
        "triggered": opposite,
        "reason": "Extreme same-quarter prior-year anchor with an opposite market move.",
    }


def assess(engine: NowcastEngine, start: date, end: date, as_of: date) -> dict[str, object]:
    """Return a risk-only diagnostic; production prediction is never adjusted."""
    features = engine.features(start, end, as_of)
    moves = _moves(engine, start, end, as_of)
    rising = [wholesale - retail for retail, wholesale in moves if wholesale >= WEEKLY_MOVE_CPG]
    falling = [(-wholesale) - (-retail) for retail, wholesale in moves if wholesale <= -WEEKLY_MOVE_CPG]
    rising_gap = sum(max(0.0, value) for value in rising) / max(1, len(rising))
    falling_gap = sum(max(0.0, value) for value in falling) / max(1, len(falling))
    squeeze_level = _level(rising_gap, CAPTURE_GAP_CPG / 2, CAPTURE_GAP_CPG)
    capture_level = _level(falling_gap, CAPTURE_GAP_CPG / 2, CAPTURE_GAP_CPG)
    adaptive = AdaptiveNowcastEngine(
        engine.market,
        [RegionWeight(region, weight) for region, weight in engine.weights.items()],
        engine.actuals,
        alpha=engine.alpha,
    )
    adaptive_forecast = adaptive.forecast("risk", start, end, as_of).as_dict()
    trailing = [item.retail_margin_cpg for item in engine.actuals[-4:]]
    older = [item.retail_margin_cpg for item in engine.actuals[:-4]]
    structural_shift = percentile(trailing, 0.50) - percentile(older, 0.50)
    structural_level = "HIGH" if (float(adaptive_forecast["feature_distance_z"]) >= OOD_HIGH_Z
                                   or abs(structural_shift) >= STRUCTURAL_MARGIN_SHIFT_CPG) else "LOW"
    risks = {
        "rising_squeeze_risk": {
            "level": squeeze_level,
            "orientation": "OVER_ESTIMATE_RISK",
            "qualifying_weeks": len(rising),
            "mean_capture_gap_cpg": round(rising_gap, 2),
            "reason": "Wholesale rises faster than retail during qualifying weekly increases.",
        },
        "falling_capture_expansion": {
            "level": capture_level,
            "orientation": "UNDER_ESTIMATE_RISK",
            "qualifying_weeks": len(falling),
            "mean_capture_gap_cpg": round(falling_gap, 2),
            "reason": "Retail falls more slowly than wholesale during qualifying weekly declines.",
        },
        "anchor_reversal_risk": _anchor_risk(engine, features, start),
        "structural_capture_uncertainty": {
            "level": structural_level,
            "orientation": "BIDIRECTIONAL",
            "feature_distance_z": adaptive_forecast["feature_distance_z"],
            "adaptive_regime": adaptive_forecast["regime"],
            "historical_regime_support": adaptive_forecast["historical_regime_support"],
            "trailing_four_reported_margin_shift_cpg": round(structural_shift, 2),
            "reason": "Unusual market features or a material shift in the reported margin floor.",
        },
    }
    active = [item for item in risks.values() if item["level"] != "LOW"]
    orientations = {str(item["orientation"]) for item in active}
    overall = "ELEVATED" if any(item["level"] == "HIGH" for item in active) or len(active) >= 2 else "NORMAL"
    orientation = ("BIDIRECTIONAL" if "BIDIRECTIONAL" in orientations or len(orientations) > 1
                   else next(iter(orientations), "NONE"))
    return {
        "spec_id": SPEC_ID,
        "forecast_type": "production_model_risk_diagnostic",
        "as_of": as_of.isoformat(),
        "quarter_start": start.isoformat(),
        "quarter_end": end.isoformat(),
        "point_forecast_changed": False,
        "overall_risk": overall,
        "risk_orientation": orientation,
        "risks": risks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assess MUSA production-model regime risk")
    parser.add_argument("--market", type=Path, default=Path("data/market.csv"))
    parser.add_argument("--weights", type=Path, default=Path("data/weights.csv"))
    parser.add_argument("--actuals", type=Path, default=Path("data/actuals.csv"))
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    engine = NowcastEngine(load_market(args.market), load_weights(args.weights), load_actuals(args.actuals))
    result = assess(engine, args.start, args.end, args.as_of)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
