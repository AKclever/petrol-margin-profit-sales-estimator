"""Command-line interface for repeatable weekly nowcasts."""

from __future__ import annotations

import argparse
import json
from datetime import date

from .data import DataError, load_actuals, load_market, load_weights
from .model import NowcastEngine


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Calibrate and run a MUSA fuel-margin nowcast")
    result.add_argument("--market", required=True, help="Weekly regional market CSV")
    result.add_argument("--weights", required=True, help="Region weight CSV")
    result.add_argument("--actuals", required=True, help="Historical MUSA quarter CSV")
    result.add_argument("--quarter", required=True, help="Forecast label, e.g. 2026Q3")
    result.add_argument("--start", required=True, type=date.fromisoformat)
    result.add_argument("--end", required=True, type=date.fromisoformat)
    result.add_argument("--as-of", required=True, type=date.fromisoformat)
    result.add_argument("--gallons-million", type=float)
    result.add_argument("--alpha", type=float, default=2.0, help="Ridge penalty (default: 2.0)")
    result.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return result


def _markdown(data: dict[str, object]) -> str:
    warning = f"\n> **Warning:** {data['warning']}\n" if data["warning"] else ""
    gallons = ""
    if data["estimated_gallons_million"] is not None:
        gallons = (f"\n- Estimated gallons: **{data['estimated_gallons_million']:.1f} million**"
                   f"\n- Estimated fuel contribution: **${data['estimated_fuel_contribution_million']:.2f} million**")
    return f"""# {data['quarter']} MUSA fuel-margin nowcast

As of **{data['as_of']}**, the tracker has {data['observed_weeks']} of approximately
{data['expected_weeks']} quarter-weeks ({float(data['coverage']) * 100:.1f}% coverage).

| Measure | Low | Base | High |
|---|---:|---:|---:|
| Retail margin (¢/gal) | {data['retail_low_cpg']:.2f} | {data['retail_margin_cpg']:.2f} | {data['retail_high_cpg']:.2f} |
| Supply/RIN scenario (¢/gal) | {data['supply_rin_low_cpg']:.2f} | {data['supply_rin_base_cpg']:.2f} | {data['supply_rin_high_cpg']:.2f} |
| All-in contribution (¢/gal) | {data['all_in_low_cpg']:.2f} | {data['all_in_base_cpg']:.2f} | {data['all_in_high_cpg']:.2f} |

Backtest MAE: **{data['backtest_mae_cpg']:.2f}¢**; historical-mean baseline MAE:
**{data['baseline_mae_cpg']:.2f}¢**.{gallons}
{warning}"""


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        engine = NowcastEngine(load_market(args.market), load_weights(args.weights),
                               load_actuals(args.actuals), alpha=args.alpha)
        forecast = engine.forecast(args.quarter, args.start, args.end, args.as_of,
                                   args.gallons_million)
    except (DataError, ValueError) as exc:
        parser().error(str(exc))
    data = forecast.as_dict()
    print(json.dumps(data, indent=2, sort_keys=True) if args.json else _markdown(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
