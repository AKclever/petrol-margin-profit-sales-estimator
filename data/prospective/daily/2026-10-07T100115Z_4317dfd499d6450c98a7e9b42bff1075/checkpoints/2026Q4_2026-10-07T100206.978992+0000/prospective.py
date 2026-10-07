"""Append-only evidence capture from Q4 2026 onward.

Availability without historical publication proof is conservatively first capture time.
Gallons and remaining-period estimates require their own registered methodologies.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .data import load_actuals, load_market, load_weights
from .eia import download_market, fetch_series_xls
from .model import NowcastEngine
from .risk import assess
from .uncertain_quarter import assimilate


SPEC_ID = "PROSPECTIVE_INFORMATION_CAPTURE_V1"
FIRST_QUARTER_START = date(2026, 10, 1)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamps must include timezone")
    return result.astimezone(timezone.utc)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return path


def capture_market(root: Path, start: date) -> Path:
    """Fetch exact EIA XLS bytes and retain each normalized observation's provenance."""
    captured = now()
    directory = root / "market" / captured.replace(":", "")
    directory.mkdir(parents=True, exist_ok=False)
    raw_sources = {}

    def opener(request, timeout=30):
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
        filename = request.full_url.rsplit("/", 1)[-1]
        target = directory / filename
        with target.open("xb") as handle:
            handle.write(raw)
        raw_sources[filename] = {"url": request.full_url, "sha256": sha(target)}
        return io.BytesIO(raw)

    def fetch(series, key, begin, end):
        return fetch_series_xls(series, key, begin, end, opener=opener)

    market = directory / "market.csv"
    provenance = directory / "download.json"
    download_market(market, provenance, "", start, timestamp(captured).date(),
                    fetcher=fetch, source="official_xls")
    completed = now()
    observation_records = []
    # Preserve the original EIA period as well as the aligned ISO-week Monday.
    import xlrd
    for filename, source in raw_sources.items():
        book = xlrd.open_workbook(str(directory / filename))
        sheet = book.sheet_by_name("Data 1")
        for row in range(3, sheet.nrows):
            observed = xlrd.xldate_as_datetime(float(sheet.cell_value(row, 0)), book.datemode).date()
            if not start <= observed <= timestamp(completed).date():
                continue
            observation_records.append({
                "series": filename, "observed_at": observed.isoformat(),
                "value_usd_per_gallon": float(sheet.cell_value(row, 1)),
                "available_at": completed, "captured_at": completed,
                "availability_method": "FIRST_CAPTURE_CONSERVATIVE",
                "raw_file": filename, "raw_sha256": source["sha256"],
            })
    return save(directory / "manifest.json", {
        "spec_id": SPEC_ID, "captured_at": completed, "information_cutoff": completed,
        "market_file": "market.csv", "market_sha256": sha(market),
        "raw_sources": raw_sources, "observations": observation_records,
        "historical_training_vintage": "CURRENT_CAPTURE_HISTORY_NOT_HISTORICAL_PIT_VALIDATION",
    })


def freeze_gallons(root: Path, input_path: Path) -> Path:
    record = json.loads(input_path.read_text())
    created = now()
    start = date.fromisoformat(record["quarter_start"])
    if start < FIRST_QUARTER_START:
        raise ValueError("historical quarters belong in the historical evidence bucket")
    if timestamp(record["information_cutoff"]) > timestamp(created):
        raise ValueError("gallons information cutoff is in the future")
    for field in ("methodology_version", "update_rule", "input_hashes"):
        if not record.get(field):
            raise ValueError(f"missing registered gallons {field}")
    months = record["expected_gallon_share_by_month"]
    expected = {f"{start.year}-{start.month + i:02d}" for i in range(3)}
    if set(months) != expected or any(not math.isfinite(v) or not 0 <= v <= 1 for v in months.values()):
        raise ValueError("provide finite gallon shares for exactly the quarter's three months")
    if abs(sum(months.values()) - 1) > 1e-9:
        raise ValueError("monthly gallon shares must sum to one")
    record.update({
        "spec_id": SPEC_ID, "forecast_created_at": created,
        "gallon_share_evidence_type": "PIT_MODELLED_GALLON_SHARE",
        "freeze_timing": "LATE_INITIAL_FREEZE" if timestamp(created).date() > start else "QUARTER_START_FREEZE",
        "source_file_sha256": sha(input_path),
    })
    # A quarter's initial shares cannot silently be replaced by a later estimate.
    return save(root / "gallons" / f"{record['quarter']}_initial.json", record)


def checkpoint(root: Path, manifest_path: Path, weights: Path, actuals: Path,
               quarter: str, start: date, end: date,
               gallons: Path | None = None, remaining: Path | None = None,
               disclosure: Path | None = None) -> Path:
    created = now()
    if start < FIRST_QUARTER_START or timestamp(created).date() < start:
        raise ValueError("prospective capture is restricted to live Q4 2026 onward quarters")
    manifest = json.loads(manifest_path.read_text())
    cutoff = manifest["information_cutoff"]
    if timestamp(cutoff) > timestamp(created):
        raise ValueError("market cutoff is in the future")
    market = manifest_path.parent / manifest["market_file"]
    if sha(market) != manifest["market_sha256"]:
        raise ValueError("market vintage hash mismatch")
    for filename, source in manifest["raw_sources"].items():
        if sha(manifest_path.parent / filename) != source["sha256"]:
            raise ValueError("raw market vintage hash mismatch")
    if any(timestamp(row["available_at"]) > timestamp(cutoff) for row in manifest["observations"]):
        raise ValueError("market observations exceed information cutoff")
    history = load_actuals(actuals)
    if any(row.end >= start for row in history):
        raise ValueError("training actuals include the forecast quarter or a future quarter")
    engine = NowcastEngine(load_market(market), load_weights(weights), history)
    inputs = {"market_manifest": manifest_path, "weights": weights, "actuals": actuals}
    payload = {
        "spec_id": SPEC_ID, "evaluation_role": "PROSPECTIVE_CAPTURE",
        "quarter": quarter, "quarter_start": start.isoformat(), "quarter_end": end.isoformat(),
        "forecast_created_at": created, "information_cutoff": cutoff,
        "production_forecast": None, "regime_risk_state": None,
        "gallons_state": {"status": "BLOCKED_NO_REGISTERED_GALLONS_METHODOLOGY"},
        "remaining_period_forecast": {"status": "BLOCKED_NO_REGISTERED_REMAINING_PERIOD_METHODOLOGY",
                                      "period_start": (timestamp(cutoff).date() + timedelta(days=1)).isoformat(),
                                      "period_end": end.isoformat()},
        "disclosure_state": {"status": "NOT_CHECKED"},
        "partial_quarter_shadow": None, "eventual_actual_margin_cpg": None,
    }
    try:
        payload["production_forecast"] = engine.forecast(quarter, start, end, timestamp(cutoff).date()).as_dict()
        payload["regime_risk_state"] = assess(engine, start, end, timestamp(cutoff).date())
    except ValueError as exc:
        payload["market_forecast_status"] = f"BLOCKED: {exc}"
    records = {}
    for kind, path in (("gallons", gallons), ("remaining", remaining), ("disclosure", disclosure)):
        if path is None:
            continue
        item = json.loads(path.read_text())
        if item["quarter"] != quarter:
            raise ValueError(f"{kind} quarter mismatch")
        if timestamp(item["information_cutoff"]) > timestamp(cutoff):
            raise ValueError(f"{kind} evidence exceeds market information cutoff")
        inputs[kind] = path
        records[kind] = item
    if gallons:
        item = records["gallons"]
        if item.get("gallon_share_evidence_type") != "PIT_MODELLED_GALLON_SHARE":
            raise ValueError("gallons must be a frozen modelled-share artifact")
        if timestamp(item["forecast_created_at"]) > timestamp(cutoff):
            raise ValueError("gallons forecast did not exist at information cutoff")
        shares = item["expected_gallon_share_by_month"]
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in shares.values()) or abs(sum(shares.values()) - 1) > 1e-9:
            raise ValueError("invalid archived gallon shares")
        payload["gallons_state"] = item
    if remaining:
        item = records["remaining"]
        if not all(item.get(key) for key in ("methodology_version", "forecast_created_at", "input_hashes")):
            raise ValueError("remaining-period forecast needs registered methodology and input hashes")
        if timestamp(item["forecast_created_at"]) > timestamp(created):
            raise ValueError("remaining-period creation timestamp is in the future")
        if timestamp(item["information_cutoff"]) != timestamp(cutoff):
            raise ValueError("remaining forecast must use the same information cutoff as production")
        if not math.isfinite(item["margin_cpg"]):
            raise ValueError("remaining margin must be finite")
        payload["remaining_period_forecast"] = item
    if disclosure:
        item = records["disclosure"]
        if timestamp(item["available_at"]) > timestamp(cutoff):
            raise ValueError("disclosure was unavailable at checkpoint cutoff")
        raw_path = Path(item["raw_path"])
        if sha(raw_path) != item["raw_sha256"]:
            raise ValueError("disclosure raw evidence hash mismatch")
        inputs["disclosure_raw"] = raw_path
        payload["disclosure_state"] = item
    if all(key in records for key in ("gallons", "remaining", "disclosure")) and payload["production_forecast"]:
        d, r, g = records["disclosure"], records["remaining"], records["gallons"]
        if d.get("target") != "retail_margin" or d.get("margin_low_cpg") is None:
            payload["assimilation_status"] = "CONTEXT_ONLY_OR_INCOMPATIBLE_TARGET"
        else:
            # Monthly shares only support disclosures ending on a month boundary.
            period_end = date.fromisoformat(d["period_end"])
            next_day = period_end + timedelta(days=1)
            if d["period_start"] != start.isoformat() or next_day.day != 1:
                raise ValueError("monthly gallon forecast cannot weight a partial-month disclosure")
            if period_end < start or period_end >= end:
                raise ValueError("disclosure period must be inside the forecast quarter")
            if r["period_start"] != next_day.isoformat() or r["period_end"] != end.isoformat():
                raise ValueError("remaining forecast must cover exactly the undisclosed quarter portion")
            if r["target"] != "retail_margin":
                raise ValueError("remaining target differs from retail disclosure")
            share = sum(v for month, v in g["expected_gallon_share_by_month"].items()
                        if month <= period_end.strftime("%Y-%m"))
            result = assimilate(payload["production_forecast"]["retail_margin_cpg"], share,
                                d["margin_low_cpg"], d.get("margin_high_cpg", d["margin_low_cpg"]),
                                r["margin_cpg"])
            payload["partial_quarter_shadow"] = {**result.as_dict(),
                "full_quarter_central_cpg": result.full_quarter_central_cpg,
                "remaining_gallon_share": 1 - share,
                "gallon_share_evidence_type": "PIT_MODELLED_GALLON_SHARE"}
    payload["input_hashes"] = {name: sha(path) for name, path in inputs.items()}
    payload["model_source_hashes"] = {name: sha(Path(__file__).with_name(name))
                                      for name in ("model.py", "risk.py", "prospective.py", "mathutils.py",
                                                   "data.py", "uncertain_quarter.py", "eia.py")}
    destination = root / "checkpoints" / f"{quarter}_{created.replace(':', '')}"
    destination.mkdir(parents=True, exist_ok=False)
    # Keep exact input bytes, not just hashes referring to mutable live files.
    for name, path in inputs.items():
        with (destination / f"{name}{path.suffix}").open("xb") as handle:
            handle.write(path.read_bytes())
    for name in payload["model_source_hashes"]:
        with (destination / name).open("xb") as handle:
            handle.write(Path(__file__).with_name(name).read_bytes())
    return save(destination / "checkpoint.json", payload)


def score(root: Path, checkpoint_path: Path, actual: float, reported_at: str,
          source: Path, source_url: str) -> Path:
    """Publish a separate score artifact; never edit the frozen checkpoint."""
    payload = json.loads(checkpoint_path.read_text())
    if payload.get("evaluation_role") != "PROSPECTIVE_CAPTURE":
        raise ValueError("only prospective checkpoints can enter the prospective score bucket")
    if not math.isfinite(actual) or not source_url.strip():
        raise ValueError("scoring requires a finite retail-margin actual and source URL")
    if not timestamp(payload["forecast_created_at"]) < timestamp(reported_at) <= timestamp(now()):
        raise ValueError("earnings must be reported after capture and before scoring")
    predictions = {
        "production": (payload.get("production_forecast") or {}).get("retail_margin_cpg"),
        "shadow": (payload.get("partial_quarter_shadow") or {}).get("full_quarter_central_cpg"),
    }
    errors = {name: None if value is None else abs(value - actual)
              for name, value in predictions.items()}
    identity = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    destination = root / "scores" / identity
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / "actual_source").open("xb") as handle:
        handle.write(source.read_bytes())
    return save(destination / "score.json", {
        "evaluation_role": "PROSPECTIVE_SCORE", "quarter": payload["quarter"],
        "checkpoint_sha256": identity, "scored_at": now(), "reported_at": reported_at,
        "actual_margin_cpg": actual, "actual_source_url": source_url, "actual_source_sha256": sha(source),
        "forecasts": predictions, "absolute_errors_cpg": errors,
        "incremental_abs_error_improvement_cpg": (
            None if any(v is None for v in errors.values()) else errors["production"] - errors["shadow"]),
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=SPEC_ID)
    parser.add_argument("--root", type=Path, default=Path("data/prospective"))
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture-market")
    capture.add_argument("--start", type=date.fromisoformat, default=date(2019, 1, 1))
    freeze = commands.add_parser("freeze-gallons")
    freeze.add_argument("--input", required=True, type=Path)
    create = commands.add_parser("checkpoint")
    create.add_argument("--market-manifest", required=True, type=Path)
    create.add_argument("--weights", type=Path, default=Path("data/weights.csv"))
    create.add_argument("--actuals", type=Path, default=Path("data/actuals.csv"))
    create.add_argument("--quarter", required=True)
    create.add_argument("--start", required=True, type=date.fromisoformat)
    create.add_argument("--end", required=True, type=date.fromisoformat)
    for key in ("gallons", "remaining", "disclosure"):
        create.add_argument(f"--{key}", type=Path)
    scoring = commands.add_parser("score")
    scoring.add_argument("--checkpoint", type=Path, required=True)
    scoring.add_argument("--actual-cpg", type=float, required=True)
    scoring.add_argument("--reported-at", required=True)
    scoring.add_argument("--source", type=Path, required=True)
    scoring.add_argument("--source-url", required=True)
    args = parser.parse_args(argv)
    if args.command == "capture-market":
        path = capture_market(args.root, args.start)
    elif args.command == "freeze-gallons":
        path = freeze_gallons(args.root, args.input)
    elif args.command == "score":
        path = score(args.root, args.checkpoint, args.actual_cpg, args.reported_at, args.source, args.source_url)
    else:
        path = checkpoint(args.root, args.market_manifest, args.weights, args.actuals,
                          args.quarter, args.start, args.end, args.gallons, args.remaining, args.disclosure)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
