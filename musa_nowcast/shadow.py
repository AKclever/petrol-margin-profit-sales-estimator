"""Append-only prospective checkpoints and scoring for frozen margin models."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from .data import load_actuals, load_market, load_weights
from .model import NowcastEngine
from .timing import CANDIDATES, SPEC_ID as TIMING_SPEC_ID, transform_market


MODELS = ("PRODUCTION", *CANDIDATES)


class ShadowError(RuntimeError):
    """Raised when prospective evidence cannot be preserved safely."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _append_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            existing_fields = next(csv.reader(handle), [])
        if existing_fields != fields:
            raise ShadowError(f"Append-only schema changed for {path}")
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if handle.tell() == 0:
            writer.writeheader()
        writer.writerows(rows)


def _forecasts(
    market_path: Path,
    weights_path: Path,
    actuals_path: Path,
    quarter: str,
    start: date,
    end: date,
    as_of: date,
) -> tuple[dict[str, dict[str, object]], str]:
    market = load_market(market_path)
    weights = load_weights(weights_path)
    actuals = load_actuals(actuals_path)
    if any(item.quarter == quarter for item in actuals):
        raise ShadowError(f"Refusing a pre-result checkpoint after {quarter} actual is present")
    engines = {
        "PRODUCTION": NowcastEngine(market, weights, actuals),
        **{
            name: NowcastEngine(transform_market(market, name), weights, actuals)
            for name in CANDIDATES
        },
    }
    forecasts: dict[str, dict[str, object]] = {}
    for name, engine in engines.items():
        forecast = engine.forecast(quarter, start, end, as_of).as_dict()
        forecasts[name] = {
            "retail_margin_cpg": forecast["retail_margin_cpg"],
            "retail_low_cpg": forecast["retail_low_cpg"],
            "retail_high_cpg": forecast["retail_high_cpg"],
            "coverage": forecast["coverage"],
            "observed_weeks": forecast["observed_weeks"],
            "expected_weeks": forecast["expected_weeks"],
        }
    latest_week = max(item.week for item in market).isoformat()
    return forecasts, latest_week


def checkpoint(
    market_path: Path,
    weights_path: Path,
    actuals_path: Path,
    root: Path,
    quarter: str,
    start: date,
    end: date,
    as_of: date,
    captured_at: datetime | None = None,
) -> dict[str, object]:
    captured = (captured_at or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(
        microsecond=0
    )
    forecasts, latest_week = _forecasts(
        market_path, weights_path, actuals_path, quarter, start, end, as_of
    )
    values = [float(forecasts[name]["retail_margin_cpg"]) for name in MODELS]
    capture_id = captured.strftime("%Y%m%dT%H%M%SZ")
    checkpoint_id = f"{quarter}_{as_of.isoformat()}_{capture_id}"
    payload: dict[str, object] = {
        "schema_version": 1,
        "checkpoint_id": checkpoint_id,
        "captured_at": captured.isoformat().replace("+00:00", "Z"),
        "as_of": as_of.isoformat(),
        "quarter": quarter,
        "quarter_start": start.isoformat(),
        "quarter_end": end.isoformat(),
        "result_known_at_capture": False,
        "timing_spec_id": TIMING_SPEC_ID,
        "models_frozen": list(MODELS),
        "forecasts": forecasts,
        "max_dispersion_cpg": round(max(values) - min(values), 2),
        "latest_market_week": latest_week,
        "inputs": {
            str(path): _sha256(path) for path in (market_path, weights_path, actuals_path)
        },
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    payload["checkpoint_sha256_without_self_hash"] = hashlib.sha256(encoded).hexdigest()
    output = root / "checkpoints" / f"{checkpoint_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ShadowError(f"Refusing to overwrite prospective checkpoint: {output}")
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ledger_rows = []
    for name in MODELS:
        forecast = forecasts[name]
        ledger_rows.append({
            "checkpoint_id": checkpoint_id,
            "captured_at": payload["captured_at"],
            "as_of": as_of.isoformat(),
            "quarter": quarter,
            "model": name,
            "retail_margin_cpg": forecast["retail_margin_cpg"],
            "retail_low_cpg": forecast["retail_low_cpg"],
            "retail_high_cpg": forecast["retail_high_cpg"],
            "coverage": forecast["coverage"],
            "latest_market_week": latest_week,
            "checkpoint_path": output.as_posix(),
            "checkpoint_file_sha256": _sha256(output),
        })
    _append_csv(root / "checkpoint_ledger.csv", ledger_rows)
    return payload


def score(
    checkpoint_path: Path,
    actuals_path: Path,
    root: Path,
    actual_cpg: float,
    reported_at: date,
    source_url: str,
) -> dict[str, object]:
    if not source_url.strip():
        raise ShadowError("A reported-result source URL is required")
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if date.fromisoformat(str(payload["as_of"])) >= reported_at:
        raise ShadowError("Checkpoint must predate the reported result")
    quarter = str(payload["quarter"])
    actuals = load_actuals(actuals_path)
    current = next((item for item in actuals if item.quarter == quarter), None)
    if current is not None and abs(current.retail_margin_cpg - actual_cpg) > 1e-9:
        raise ShadowError("Provided actual conflicts with actuals.csv")
    start = date.fromisoformat(str(payload["quarter_start"]))
    prior_key = (start.year - 1, (start.month - 1) // 3 + 1)
    prior = next(
        (item for item in actuals if (item.start.year, (item.start.month - 1) // 3 + 1) == prior_key),
        None,
    )
    if prior is None:
        raise ShadowError("Prior-year actual is required for directional scoring")
    scorecard = root / "scorecard.csv"
    checkpoint_id = str(payload["checkpoint_id"])
    if scorecard.exists():
        with scorecard.open(newline="", encoding="utf-8") as handle:
            if any(row["checkpoint_id"] == checkpoint_id for row in csv.DictReader(handle)):
                raise ShadowError(f"Checkpoint is already scored: {checkpoint_id}")
    actual_direction = (actual_cpg > prior.retail_margin_cpg) - (actual_cpg < prior.retail_margin_cpg)
    rows = []
    for name in MODELS:
        prediction = float(payload["forecasts"][name]["retail_margin_cpg"])
        predicted_direction = (prediction > prior.retail_margin_cpg) - (
            prediction < prior.retail_margin_cpg
        )
        rows.append({
            "checkpoint_id": checkpoint_id,
            "quarter": quarter,
            "as_of": payload["as_of"],
            "reported_at": reported_at.isoformat(),
            "model": name,
            "prediction_cpg": prediction,
            "actual_cpg": actual_cpg,
            "absolute_error_cpg": abs(actual_cpg - prediction),
            "prior_year_actual_cpg": prior.retail_margin_cpg,
            "direction_correct": predicted_direction == actual_direction,
            "source_url": source_url,
        })
    _append_csv(scorecard, rows)
    return {"checkpoint_id": checkpoint_id, "quarter": quarter, "scores": rows}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Archive and score prospective MUSA margin forecasts")
    commands = result.add_subparsers(dest="command", required=True)
    create = commands.add_parser("checkpoint")
    create.add_argument("--market", type=Path, default=Path("data/market.csv"))
    create.add_argument("--weights", type=Path, default=Path("data/weights.csv"))
    create.add_argument("--actuals", type=Path, default=Path("data/actuals.csv"))
    create.add_argument("--root", type=Path, default=Path("data/shadow"))
    create.add_argument("--quarter", default="2026Q3")
    create.add_argument("--start", type=date.fromisoformat, default=date(2026, 7, 1))
    create.add_argument("--end", type=date.fromisoformat, default=date(2026, 9, 30))
    create.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    scoring = commands.add_parser("score")
    scoring.add_argument("--checkpoint", type=Path, required=True)
    scoring.add_argument("--actuals", type=Path, default=Path("data/actuals.csv"))
    scoring.add_argument("--root", type=Path, default=Path("data/shadow"))
    scoring.add_argument("--actual-cpg", type=float, required=True)
    scoring.add_argument("--reported-at", type=date.fromisoformat, required=True)
    scoring.add_argument("--source-url", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "checkpoint":
            result = checkpoint(
                args.market, args.weights, args.actuals, args.root, args.quarter,
                args.start, args.end, args.as_of,
            )
        else:
            result = score(
                args.checkpoint, args.actuals, args.root, args.actual_cpg,
                args.reported_at, args.source_url,
            )
    except (ShadowError, ValueError, OSError, json.JSONDecodeError) as exc:
        parser().error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
