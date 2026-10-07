"""Append-only prospective scoring for the frozen regime-risk monitor."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from .data import load_actuals, load_market, load_weights
from .risk import SPEC_ID, assess
from .model import NowcastEngine


LEDGER_SCHEMA_VERSION = 1
EXPECTED_ERROR_RULE = "ELEVATED=>ABOVE_NORMAL_RISK; NORMAL=>TYPICAL_RISK"


class RiskLedgerError(RuntimeError):
    """Raised when a risk checkpoint or score would no longer be auditable."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _append(path: Path, row: dict[str, object]) -> None:
    fields = list(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            existing = next(csv.reader(handle), [])
        if existing != fields:
            raise RiskLedgerError(f"Append-only schema changed for {path}")
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if handle.tell() == 0:
            writer.writeheader()
        writer.writerow(row)


def checkpoint(
    market_path: Path, weights_path: Path, actuals_path: Path, root: Path,
    quarter: str, start: date, end: date, as_of: date, production_forecast_cpg: float,
    created_at: datetime | None = None,
) -> dict[str, object]:
    actuals = load_actuals(actuals_path)
    if any(item.quarter == quarter for item in actuals):
        raise RiskLedgerError(f"Refusing a pre-result risk checkpoint after {quarter} actual is present")
    engine = NowcastEngine(load_market(market_path), load_weights(weights_path), actuals)
    risk = assess(engine, start, end, as_of)
    captured = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    checkpoint_id = f"{quarter}_{as_of.isoformat()}_{captured.strftime('%Y%m%dT%H%M%SZ')}"
    path = root / "checkpoints" / f"{checkpoint_id}.json"
    if path.exists():
        raise RiskLedgerError(f"Refusing to overwrite risk checkpoint: {path}")
    payload: dict[str, object] = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "checkpoint_id": checkpoint_id,
        "created_at": captured.isoformat().replace("+00:00", "Z"),
        "quarter": quarter,
        "as_of": as_of.isoformat(),
        "result_known_at_capture": False,
        "production_forecast_cpg": production_forecast_cpg,
        "production_historical_mae_cpg": round(float(engine.backtest()["mae"]), 2),
        "expected_error_rule": EXPECTED_ERROR_RULE,
        "expected_error_class": (
            "ABOVE_NORMAL_RISK" if risk["overall_risk"] == "ELEVATED" else "TYPICAL_RISK"
        ),
        "risk": risk,
        "inputs": {str(path): _sha256(path) for path in (market_path, weights_path, actuals_path)},
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    payload["checkpoint_sha256_without_self_hash"] = hashlib.sha256(encoded).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def score(checkpoint_path: Path, root: Path, actual_margin_cpg: float,
          reported_at: date, source_url: str) -> dict[str, object]:
    if not source_url.strip():
        raise RiskLedgerError("A reported-result source URL is required")
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if date.fromisoformat(str(payload["as_of"])) >= reported_at:
        raise RiskLedgerError("Risk checkpoint must predate the reported result")
    risk = payload["risk"]
    if not isinstance(risk, dict):
        raise RiskLedgerError("Malformed risk checkpoint")
    risks = risk["risks"]
    if not isinstance(risks, dict):
        raise RiskLedgerError("Malformed risk mechanisms")
    forecast = float(payload["production_forecast_cpg"])
    error = actual_margin_cpg - forecast
    high = {name for name, value in risks.items()
            if isinstance(value, dict) and value.get("level") == "HIGH"}
    mechanisms: list[str] = []
    if error < 0 and "rising_squeeze_risk" in high:
        mechanisms.append("RISING_SQUEEZE")
    if error > 0 and "falling_capture_expansion" in high:
        mechanisms.append("FALLING_CAPTURE_EXPANSION")
    if not mechanisms:
        mechanisms.append("NONE_OR_BIDIRECTIONAL")
    absolute_error = abs(error)
    row = {
        "checkpoint_id": payload["checkpoint_id"],
        "quarter": payload["quarter"],
        "forecast_created_at": payload["created_at"],
        "reported_at": reported_at.isoformat(),
        "production_forecast_cpg": forecast,
        "actual_margin_cpg": actual_margin_cpg,
        "production_error_cpg": round(error, 4),
        "absolute_error_cpg": round(absolute_error, 4),
        "risk_level": risk["overall_risk"],
        "risk_orientation": risk["risk_orientation"],
        "rising_squeeze_level": risks["rising_squeeze_risk"]["level"],
        "falling_capture_level": risks["falling_capture_expansion"]["level"],
        "anchor_reversal_level": risks["anchor_reversal_risk"]["level"],
        "structural_ood_level": risks["structural_capture_uncertainty"]["level"],
        "ood_distance_z": risks["structural_capture_uncertainty"]["feature_distance_z"],
        "historical_support": risks["structural_capture_uncertainty"]["historical_regime_support"],
        "expected_error_class": payload["expected_error_class"],
        "realized_error_class": (
            "ABOVE_HISTORICAL_MAE" if absolute_error > float(payload["production_historical_mae_cpg"])
            else "WITHIN_HISTORICAL_MAE"
        ),
        "directional_mechanism_that_matched": ";".join(mechanisms),
        "source_url": source_url,
    }
    ledger = root / "scorecard.csv"
    if ledger.exists():
        with ledger.open(newline="", encoding="utf-8") as handle:
            if any(existing["checkpoint_id"] == row["checkpoint_id"]
                   for existing in csv.DictReader(handle)):
                raise RiskLedgerError(f"Risk checkpoint is already scored: {row['checkpoint_id']}")
    _append(ledger, row)
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Checkpoint and score MUSA regime-risk diagnostics")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("checkpoint")
    create.add_argument("--market", type=Path, default=Path("data/market.csv"))
    create.add_argument("--weights", type=Path, default=Path("data/weights.csv"))
    create.add_argument("--actuals", type=Path, default=Path("data/actuals.csv"))
    create.add_argument("--root", type=Path, default=Path("data/risk_research"))
    create.add_argument("--quarter", required=True)
    create.add_argument("--start", required=True, type=date.fromisoformat)
    create.add_argument("--end", required=True, type=date.fromisoformat)
    create.add_argument("--as-of", required=True, type=date.fromisoformat)
    create.add_argument("--production-forecast-cpg", required=True, type=float)
    score_parser = commands.add_parser("score")
    score_parser.add_argument("--checkpoint", required=True, type=Path)
    score_parser.add_argument("--root", type=Path, default=Path("data/risk_research"))
    score_parser.add_argument("--actual-margin-cpg", required=True, type=float)
    score_parser.add_argument("--reported-at", required=True, type=date.fromisoformat)
    score_parser.add_argument("--source-url", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "checkpoint":
            result = checkpoint(args.market, args.weights, args.actuals, args.root, args.quarter,
                                args.start, args.end, args.as_of, args.production_forecast_cpg)
        else:
            result = score(args.checkpoint, args.root, args.actual_margin_cpg,
                           args.reported_at, args.source_url)
    except (RiskLedgerError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
