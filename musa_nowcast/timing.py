"""Pre-registered wholesale-cost timing challengers for the MUSA model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .data import MarketWeek, load_actuals, load_market, load_weights
from .geo import _predictions
from .model import (
    MIN_BACKTEST_QUARTERS,
    MIN_BASELINE_IMPROVEMENT,
    NORMAL_95_Z,
    RECENT_BACKTEST_QUARTERS,
    NowcastEngine,
)


SPEC_ID = "MUSA_WHOLESALE_TIMING_CHALLENGER_V1"
CANDIDATES = {
    "A_LAG_1_WEEK": "wholesale proxy lagged exactly one week",
    "B_CURRENT_PRIOR_50_50": "50% current-week plus 50% prior-week wholesale",
    "C_TRAILING_3_WEEK_EQUAL": "equal-weight current and prior two wholesale weeks",
}
RESEARCH_CLASSIFICATIONS = {
    "A_LAG_1_WEEK": "FAILED_GATE",
    "B_CURRENT_PRIOR_50_50": "PROMISING_NOT_SECURE",
    "C_TRAILING_3_WEEK_EQUAL": "PROMISING_RECENTLY_NOT_SECURE",
}


class TimingError(RuntimeError):
    """Raised when the frozen timing experiment cannot be evaluated safely."""


def research_spec() -> dict[str, object]:
    return {
        "id": SPEC_ID,
        "status": "FROZEN_BEFORE_EVALUATION",
        "purpose": "test fixed wholesale-cost timing against the validated MUSA champion",
        "target": "MUSA reported retail fuel margin cpg",
        "retail_input": "unchanged production retail basket",
        "weights": "unchanged production geographic weights",
        "features": ["spread", "falling_capture", "rising_squeeze", "volatility"],
        "fit": "unchanged ridge, 50% market-change shrinkage, expanding window",
        "candidates": CANDIDATES,
        "selection_rule": "evaluate separately; do not combine or tune from results",
        "q3_2026_actual": "NOT_AVAILABLE_AND_NOT_USED",
        "comparison": "production model on identical eligible quarters",
        "automatic_promotion": False,
        "gate": {
            "minimum_mae_improvement": MIN_BASELINE_IMPROVEMENT,
            "directional_accuracy_not_worse": True,
            "paired_95pct_lower_bound_positive": True,
            "recent_eight_minimum_mae_improvement": MIN_BASELINE_IMPROVEMENT,
            "recent_eight_directional_accuracy_not_worse": True,
        },
    }


def _spec_hash() -> str:
    encoded = json.dumps(research_spec(), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def transform_market(market: list[MarketWeek], candidate: str) -> list[MarketWeek]:
    """Apply one fixed timing mechanism without filling missing calendar weeks."""
    if candidate not in CANDIDATES:
        raise TimingError(f"Unknown timing candidate: {candidate}")
    grouped: dict[str, dict[date, MarketWeek]] = defaultdict(dict)
    for row in market:
        grouped[row.region][row.week] = row
    result: list[MarketWeek] = []
    for region, by_week in grouped.items():
        for week, row in sorted(by_week.items()):
            prior = by_week.get(week - timedelta(days=7))
            prior_two = by_week.get(week - timedelta(days=14))
            if candidate == "A_LAG_1_WEEK":
                if prior is None:
                    continue
                wholesale = prior.wholesale_cpg
            elif candidate == "B_CURRENT_PRIOR_50_50":
                if prior is None:
                    continue
                wholesale = 0.5 * row.wholesale_cpg + 0.5 * prior.wholesale_cpg
            else:
                if prior is None or prior_two is None:
                    continue
                wholesale = (row.wholesale_cpg + prior.wholesale_cpg + prior_two.wholesale_cpg) / 3.0
            result.append(MarketWeek(week, region, row.retail_cpg, wholesale))
    if not result:
        raise TimingError(f"Timing transformation produced no rows: {candidate}")
    return sorted(result, key=lambda row: (row.week, row.region))


def _metrics(
    champion_rows: dict[str, dict[str, object]],
    challenger_rows: dict[str, dict[str, object]],
    quarters: list[str],
) -> dict[str, object]:
    production_errors, challenger_errors, improvements = [], [], []
    production_direction, challenger_direction = [], []
    for quarter in quarters:
        champion, challenger = champion_rows[quarter], challenger_rows[quarter]
        actual = float(champion["actual_cpg"])
        production_error = actual - float(champion["prediction_cpg"])
        challenger_error = actual - float(challenger["prediction_cpg"])
        production_errors.append(production_error)
        challenger_errors.append(challenger_error)
        improvements.append(abs(production_error) - abs(challenger_error))
        production_direction.append(bool(champion["direction_correct"]))
        challenger_direction.append(bool(challenger["direction_correct"]))
    count = len(quarters)
    mean_improvement = sum(improvements) / count
    variance = sum((value - mean_improvement) ** 2 for value in improvements) / max(1, count - 1)
    ci_low = mean_improvement - NORMAL_95_Z * math.sqrt(variance / count)
    production_mae = sum(abs(value) for value in production_errors) / count
    challenger_mae = sum(abs(value) for value in challenger_errors) / count
    production_rmse = math.sqrt(sum(value * value for value in production_errors) / count)
    challenger_rmse = math.sqrt(sum(value * value for value in challenger_errors) / count)
    recent_count = min(RECENT_BACKTEST_QUARTERS, count)
    recent_production_mae = sum(abs(value) for value in production_errors[-recent_count:]) / recent_count
    recent_challenger_mae = sum(abs(value) for value in challenger_errors[-recent_count:]) / recent_count
    production_accuracy = sum(production_direction) / count
    challenger_accuracy = sum(challenger_direction) / count
    recent_production_accuracy = sum(production_direction[-recent_count:]) / recent_count
    recent_challenger_accuracy = sum(challenger_direction[-recent_count:]) / recent_count
    passes = (
        count >= MIN_BACKTEST_QUARTERS
        and challenger_mae <= production_mae * (1.0 - MIN_BASELINE_IMPROVEMENT)
        and challenger_accuracy >= production_accuracy
        and ci_low > 0
        and recent_challenger_mae
        <= recent_production_mae * (1.0 - MIN_BASELINE_IMPROVEMENT)
        and recent_challenger_accuracy >= recent_production_accuracy
    )
    return {
        "identical_backtest_rows": count,
        "production_mae_cpg": production_mae,
        "challenger_mae_cpg": challenger_mae,
        "production_rmse_cpg": production_rmse,
        "challenger_rmse_cpg": challenger_rmse,
        "production_directional_accuracy": production_accuracy,
        "challenger_directional_accuracy": challenger_accuracy,
        "recent_eight_production_mae_cpg": recent_production_mae,
        "recent_eight_challenger_mae_cpg": recent_challenger_mae,
        "recent_eight_production_directional_accuracy": recent_production_accuracy,
        "recent_eight_challenger_directional_accuracy": recent_challenger_accuracy,
        "mean_paired_improvement_cpg": mean_improvement,
        "paired_improvement_ci_low_cpg": ci_low,
        "passes_pre_registered_gate": passes,
        "production_status": "UNCHANGED",
        "promotion_status": "NOT_AUTOMATICALLY_PROMOTED",
    }


def _write_market(path: Path, rows: list[MarketWeek]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["week", "region", "retail_cpg", "wholesale_cpg"])
        for row in rows:
            writer.writerow([
                row.week.isoformat(), row.region, f"{row.retail_cpg:.4f}",
                f"{row.wholesale_cpg:.4f}",
            ])


def evaluate(
    market_path: Path,
    weights_path: Path,
    actuals_path: Path,
    output_dir: Path,
    quarter: str,
    start: date,
    end: date,
    as_of: date,
) -> dict[str, object]:
    market = load_market(market_path)
    weights = load_weights(weights_path)
    actuals = load_actuals(actuals_path)
    if any(item.quarter == quarter for item in actuals):
        raise TimingError(f"Refusing to evaluate current quarter with an available actual: {quarter}")
    champion = NowcastEngine(market, weights, actuals)
    engines = {
        name: NowcastEngine(transform_market(market, name), weights, actuals)
        for name in CANDIDATES
    }
    prediction_maps = {
        "PRODUCTION": {str(row["quarter"]): row for row in _predictions(champion)},
        **{
            name: {str(row["quarter"]): row for row in _predictions(engine)}
            for name, engine in engines.items()
        },
    }
    common_quarters = sorted(set.intersection(*(set(rows) for rows in prediction_maps.values())))
    if not common_quarters:
        raise TimingError("No identical backtest rows across production and all challengers")
    results = {
        name: _metrics(prediction_maps["PRODUCTION"], prediction_maps[name], common_quarters)
        for name in CANDIDATES
    }
    for name, metrics in results.items():
        metrics["research_classification"] = RESEARCH_CLASSIFICATIONS[name]
    evaluation_rows: list[dict[str, object]] = []
    for historical_quarter in common_quarters:
        champion_row = prediction_maps["PRODUCTION"][historical_quarter]
        row: dict[str, object] = {
            "quarter": historical_quarter,
            "actual_cpg": champion_row["actual_cpg"],
            "production_prediction_cpg": champion_row["prediction_cpg"],
            "production_direction_correct": champion_row["direction_correct"],
        }
        actual = float(champion_row["actual_cpg"])
        production_error = abs(actual - float(champion_row["prediction_cpg"]))
        for name in CANDIDATES:
            challenger = prediction_maps[name][historical_quarter]
            prediction = float(challenger["prediction_cpg"])
            row[f"{name}_prediction_cpg"] = prediction
            row[f"{name}_abs_error_cpg"] = abs(actual - prediction)
            row[f"{name}_paired_improvement_cpg"] = production_error - abs(actual - prediction)
            row[f"{name}_direction_correct"] = challenger["direction_correct"]
        evaluation_rows.append(row)

    production_forecast = champion.forecast(quarter, start, end, as_of).as_dict()
    forecasts: dict[str, object] = {
        "quarter": quarter,
        "as_of": as_of.isoformat(),
        "q3_2026_actual_used": False,
        "PRODUCTION": {
            "retail_margin_cpg": production_forecast["retail_margin_cpg"],
            "retail_low_cpg": production_forecast["retail_low_cpg"],
            "retail_high_cpg": production_forecast["retail_high_cpg"],
            "coverage": production_forecast["coverage"],
        },
    }
    for name, engine in engines.items():
        forecast = engine.forecast(quarter, start, end, as_of).as_dict()
        forecasts[name] = {
            "retail_margin_cpg": forecast["retail_margin_cpg"],
            "retail_low_cpg": forecast["retail_low_cpg"],
            "retail_high_cpg": forecast["retail_high_cpg"],
            "coverage": forecast["coverage"],
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    spec_payload = {"research_spec": research_spec(), "research_spec_hash": _spec_hash()}
    (output_dir / "research_spec.json").write_text(
        json.dumps(spec_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for name, engine in engines.items():
        _write_market(output_dir / f"market_{name}.csv", engine.market)
    with (output_dir / "evaluation.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(evaluation_rows[0]))
        writer.writeheader()
        writer.writerows(evaluation_rows)
    result_payload = {
        "spec_id": SPEC_ID,
        "research_spec_status": "FROZEN",
        "production_model_unchanged": True,
        "automatic_promotion": False,
        "results": results,
    }
    (output_dir / "results.json").write_text(
        json.dumps(result_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "current_forecasts.json").write_text(
        json.dumps(forecasts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifacts = [
        output_dir / "research_spec.json", output_dir / "evaluation.csv",
        output_dir / "results.json", output_dir / "current_forecasts.json",
        *(output_dir / f"market_{name}.csv" for name in CANDIDATES),
    ]
    manifest = {
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        "research_spec_hash": _spec_hash(),
        "inputs": {
            str(path): _sha256(path) for path in (market_path, weights_path, actuals_path)
        },
        "artifacts": {str(path): _sha256(path) for path in artifacts},
        "identical_backtest_rows": len(common_quarters),
        "production_model_unchanged": True,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"results": results, "current_forecasts": forecasts}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Evaluate fixed MUSA wholesale timing challengers")
    result.add_argument("--market", type=Path, default=Path("data/market.csv"))
    result.add_argument("--weights", type=Path, default=Path("data/weights.csv"))
    result.add_argument("--actuals", type=Path, default=Path("data/actuals.csv"))
    result.add_argument("--output-dir", type=Path, default=Path("data/timing_research"))
    result.add_argument("--quarter", default="2026Q3")
    result.add_argument("--start", type=date.fromisoformat, default=date(2026, 7, 1))
    result.add_argument("--end", type=date.fromisoformat, default=date(2026, 9, 30))
    result.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = evaluate(
            args.market, args.weights, args.actuals, args.output_dir,
            args.quarter, args.start, args.end, args.as_of,
        )
    except (TimingError, ValueError, OSError) as exc:
        parser().error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
