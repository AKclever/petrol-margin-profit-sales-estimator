"""Command-line interface for repeatable fuel-margin backtests and nowcasts."""

from __future__ import annotations

import argparse
import json
from datetime import date

from .data import DataError, load_actuals, load_market, load_weights
from .model import AdaptiveNowcastEngine, NowcastEngine


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Calibrate and run a retail fuel-margin nowcast")
    result.add_argument("--market", required=True, help="Weekly regional market CSV")
    result.add_argument("--weights", required=True, help="Region weight CSV")
    result.add_argument("--actuals", required=True, help="Historical company quarter CSV")
    result.add_argument("--company", default="MUSA", help="Company name used in output")
    result.add_argument("--backtest", action="store_true",
                        help="Report leakage-safe historical validation without forecasting")
    result.add_argument("--quarter", help="Forecast label, e.g. 2026Q3")
    result.add_argument("--start", type=date.fromisoformat)
    result.add_argument("--end", type=date.fromisoformat)
    result.add_argument("--as-of", type=date.fromisoformat)
    result.add_argument("--gallons-million", type=float)
    result.add_argument("--alpha", type=float, default=2.0, help="Ridge penalty (default: 2.0)")
    result.add_argument("--adaptive", action="store_true",
                        help="Run the shadow adaptive challenger; never the production default")
    result.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return result


def _backtest_markdown(data: dict[str, object], company: str) -> str:
    return f"""# {company} fuel-margin backtest

Leakage-safe expanding-window backtest over **{data['backtest_quarters']} quarters**:

| Measure | Result |
|---|---:|
| Model MAE | {data['mae']:.2f} cents/gal |
| Seasonal baseline MAE | {data['seasonal_baseline_mae']:.2f} cents/gal |
| Historical-mean baseline MAE | {data['historical_mean_mae']:.2f} cents/gal |
| Directional accuracy | {float(data['directional_accuracy']) * 100:.1f}% |
| Recent-eight model MAE | {data['recent_mae']:.2f} cents/gal |
| Recent-eight strongest baseline MAE | {data['recent_baseline_mae']:.2f} cents/gal |
| Recent-eight directional accuracy | {float(data['recent_directional_accuracy']) * 100:.1f}% |
| Mean MAE improvement | {data['mae_improvement']:.2f} cents/gal |
| Approx. 95% lower bound | {data['mae_improvement_ci_low']:.2f} cents/gal |
| Trust gate passed | **{str(data['validated']).lower()}** |
"""


def _markdown(data: dict[str, object], company: str) -> str:
    warning = f"\n> **Warning:** {data['warning']}\n" if data["warning"] else ""
    gallons = ""
    if data["estimated_gallons_million"] is not None:
        gallons = (f"\n- Estimated gallons: **{data['estimated_gallons_million']:.1f} million**"
                   f"\n- Estimated fuel contribution: "
                   f"**${data['estimated_fuel_contribution_million']:.2f} million**")
    supply_rows = ""
    if data["supply_rin_base_cpg"] is not None:
        supply_rows = (
            f"\n| Supply/RIN scenario (cents/gal) | {data['supply_rin_low_cpg']:.2f} | "
            f"{data['supply_rin_base_cpg']:.2f} | {data['supply_rin_high_cpg']:.2f} |"
            f"\n| All-in contribution (cents/gal) | {data['all_in_low_cpg']:.2f} | "
            f"{data['all_in_base_cpg']:.2f} | {data['all_in_high_cpg']:.2f} |"
        )
    return f"""# {data['quarter']} {company} fuel-margin nowcast

As of **{data['as_of']}**, the tracker has {data['observed_weeks']} of approximately
{data['expected_weeks']} quarter-weeks ({float(data['coverage']) * 100:.1f}% coverage).
Forecast type: **{data['forecast_type']}**. Regime: **{data['regime']}**
({data['historical_regime_support']} historical comparable quarters; maximum feature distance
{data['feature_distance_z']:.2f}σ; interval multiplier {data['regime_penalty']:.2f}×).

| Measure | Low | Base | High |
|---|---:|---:|---:|
| Retail margin (cents/gal) | {data['retail_low_cpg']:.2f} | {data['retail_margin_cpg']:.2f} | {data['retail_high_cpg']:.2f} |{supply_rows}

Unshrunk market-change estimate: **{data['market_model_cpg']:.2f} cents**; same-quarter
prior-year baseline: **{data['seasonal_baseline_cpg']:.2f} cents**.

Leakage-safe walk-forward backtest ({data['backtest_quarters']} quarters): model MAE
**{data['backtest_mae_cpg']:.2f} cents**, seasonal baseline MAE
**{data['seasonal_baseline_mae_cpg']:.2f} cents**, historical-mean baseline MAE
**{data['historical_mean_mae_cpg']:.2f} cents**, directional accuracy
**{float(data['backtest_directional_accuracy']) * 100:.1f}%**, validated:
**{str(data['validated']).lower()}**.{gallons}

Mean MAE improvement over the strongest baseline: **{data['mae_improvement_cpg']:.2f} cents**;
approximate 95% lower bound: **{data['mae_improvement_ci_low_cpg']:.2f} cents**.

Latest eight test quarters: model MAE **{data['recent_backtest_mae_cpg']:.2f} cents**,
strongest baseline MAE **{data['recent_baseline_mae_cpg']:.2f} cents**, directional accuracy
**{float(data['recent_directional_accuracy']) * 100:.1f}%**.
{warning}"""


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        engine_class = AdaptiveNowcastEngine if args.adaptive else NowcastEngine
        engine = engine_class(load_market(args.market), load_weights(args.weights),
                              load_actuals(args.actuals), alpha=args.alpha)
        if args.backtest:
            data = engine.backtest()
            print(json.dumps(data, indent=2, sort_keys=True) if args.json
                  else _backtest_markdown(data, args.company))
            return 0
        missing = [name for name in ("quarter", "start", "end", "as_of")
                   if getattr(args, name) is None]
        if missing:
            raise DataError("Forecast requires: " + ", ".join(
                "--" + name.replace("_", "-") for name in missing
            ))
        forecast = engine.forecast(args.quarter, args.start, args.end, args.as_of,
                                   args.gallons_million)
    except (DataError, ValueError) as exc:
        parser().error(str(exc))
    data = forecast.as_dict()
    print(json.dumps(data, indent=2, sort_keys=True) if args.json
          else _markdown(data, args.company))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
