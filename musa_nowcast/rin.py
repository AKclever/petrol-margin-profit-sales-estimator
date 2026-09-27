"""Official EPA RIN ingestion and a separately gated MUSA supply/RIN challenger."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests
import websocket

from .data import QuarterActual, load_actuals


SOURCE_PAGE = (
    "https://www.epa.gov/fuels-registration-reporting-and-compliance-help/"
    "rin-trades-and-price-information"
)
QLIK_HOST = "edap.epa.gov"
QLIK_APP_ID = "73b2b6a5-70c6-4820-b3fa-186ac094f10d"
PRICE_OBJECT_ID = "302609e3-8b43-4ff5-ad9b-ebd53778889b"
VOLUME_OBJECT_ID = "679e0428-fa34-49ea-8e34-0d1457ca9f77"
SCHEMA_VERSION = "1.1"
MIN_TRAINING_CHANGES = 8
NORMALIZED_FILENAME = "d6-weekly-normalized.csv"
RESEARCH_SPEC = {
    "id": "MUSA_RIN_D6_CHALLENGER_V1",
    "role": "PROSPECTIVE_CANDIDATE_FEATURE",
    "d_code": "D6",
    "price_population": "separated transactions",
    "weekly_transform": "volume-weighted across QAP types; RIN vintages retained",
    "quarterly_feature": "arithmetic mean of weekly same-year-vintage D6 VWAP",
    "change_feature": "current quarter divided by prior-year same quarter minus one",
    "target": "company-reported quarterly supply/RIN contribution in cents per gallon",
    "baseline": "prior-year same-quarter supply/RIN contribution",
    "coefficient": "single zero-intercept coefficient fitted in expanding window",
    "minimum_training_changes": MIN_TRAINING_CHANGES,
    "transaction_volume_role": "CONTEXT_ONLY_WEIGHTING_INPUT",
}


def research_spec_hash() -> str:
    payload = json.dumps(RESEARCH_SPEC, sort_keys=True, separators=(",", ":")).encode()
    return _sha256(payload)


class RinDownloadError(RuntimeError):
    """Raised when the official EPA export cannot be downloaded safely."""


@dataclass(frozen=True)
class RinWeek:
    transfer_week: date
    rin_year: int
    weekly_vwap_usd_per_rin: float
    transaction_volume_rins: int
    available_at: datetime
    captured_at: datetime


def _utc_timestamp(value: datetime | None = None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValueError("captured_at must include a timezone")
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_date(value: str) -> date:
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            pass
    raise RinDownloadError(f"Invalid EPA transfer week: {value!r}")


def _money(value: str) -> float:
    cleaned = value.strip().replace("$", "").replace(",", "")
    try:
        result = float(cleaned)
    except ValueError as exc:
        raise RinDownloadError(f"Invalid EPA RIN price: {value!r}") from exc
    if not math.isfinite(result) or result < 0:
        raise RinDownloadError(f"EPA RIN price must be finite and nonnegative: {value!r}")
    return result


def _integer(value: str) -> int:
    try:
        result = int(value.strip().replace(",", ""))
    except ValueError as exc:
        raise RinDownloadError(f"Invalid EPA RIN volume: {value!r}") from exc
    if result < 0:
        raise RinDownloadError(f"EPA RIN volume must be nonnegative: {value!r}")
    return result


class _QlikSession:
    """Minimal Qlik Engine client for EPA's anonymous public virtual proxy."""

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.http = requests.Session()
        self.socket = None
        self.request_id = 0

    def __enter__(self) -> "_QlikSession":
        bootstrap = f"https://{QLIK_HOST}/public/single/?appid={QLIK_APP_ID}"
        response = self.http.get(bootstrap, timeout=self.timeout)
        response.raise_for_status()
        cookie = "; ".join(f"{key}={value}" for key, value in self.http.cookies.items())
        if not cookie:
            raise RinDownloadError("EPA Qlik bootstrap returned no anonymous session cookie")
        identity = uuid.uuid4()
        socket_url = (
            f"wss://{QLIK_HOST}/public/app/{QLIK_APP_ID}/identity/{identity}"
        )
        try:
            self.socket = websocket.create_connection(
                socket_url,
                origin=f"https://{QLIK_HOST}",
                cookie=cookie,
                timeout=self.timeout,
                header=["User-Agent: musa-margin-nowcast/0.1"],
            )
            result = self._call(-1, "OpenDoc", [QLIK_APP_ID, "", "", "", False])
        except Exception as exc:  # websocket exposes several transport exception types.
            self.close()
            raise RinDownloadError(f"Could not open the EPA RIN data application: {exc}") from exc
        if result.get("qReturn", {}).get("qHandle") != 1:
            self.close()
            raise RinDownloadError("EPA Qlik application did not return the expected document handle")
        return self

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        self.http.close()

    def __exit__(self, *_: object) -> None:
        self.close()

    def _call(self, handle: int, method: str, params: list[object]) -> dict[str, object]:
        if self.socket is None:
            raise RinDownloadError("EPA Qlik session is not open")
        self.request_id += 1
        request_id = self.request_id
        self.socket.send(json.dumps({
            "jsonrpc": "2.0", "id": request_id, "handle": handle,
            "method": method, "params": params,
        }))
        while True:
            message = json.loads(self.socket.recv())
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RinDownloadError(
                    f"EPA Qlik {method} failed: {json.dumps(message['error'], sort_keys=True)}"
                )
            return message.get("result", {})

    def export_csv(self, object_id: str, filename: str) -> bytes:
        result = self._call(1, "GetObject", [object_id])
        handle = result.get("qReturn", {}).get("qHandle")
        if not isinstance(handle, int):
            raise RinDownloadError(f"EPA Qlik object is unavailable: {object_id}")
        export = self._call(
            handle, "ExportData", ["CSV_C", "/qHyperCubeDef", filename, "A"]
        )
        relative_url = export.get("qUrl")
        if not isinstance(relative_url, str) or not relative_url.startswith("/tempcontent/"):
            raise RinDownloadError("EPA Qlik export returned no temporary download URL")
        response = self.http.get(
            f"https://{QLIK_HOST}/public{relative_url}", timeout=self.timeout
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "csv" not in content_type:
            raise RinDownloadError(
                f"EPA export returned {content_type or 'an unknown content type'} instead of CSV"
            )
        return response.content


def download_epa_exports(timeout: int = 60) -> tuple[bytes, bytes]:
    """Download the official RIN price and transaction-volume tables."""
    try:
        with _QlikSession(timeout) as session:
            prices = session.export_csv(PRICE_OBJECT_ID, "epa-rin-prices.csv")
            volumes = session.export_csv(VOLUME_OBJECT_ID, "epa-rin-volumes.csv")
    except (requests.RequestException, OSError, ValueError) as exc:
        raise RinDownloadError(f"Could not download EPA RIN data: {exc}") from exc
    return prices, volumes


def _csv_rows(data: bytes, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RinDownloadError(f"EPA {label} export is not valid UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    fields = set(reader.fieldnames or ())
    missing = required - fields
    if missing:
        raise RinDownloadError(
            f"EPA {label} export is missing columns: {', '.join(sorted(missing))}"
        )
    rows = list(reader)
    if not rows:
        raise RinDownloadError(f"EPA {label} export is empty")
    return rows


def transform_d6(
    price_csv: bytes, volume_csv: bytes, captured_at: datetime
) -> tuple[list[RinWeek], dict[str, int]]:
    """Join prices to separated volumes and aggregate QAP types for each D6 vintage."""
    price_required = {
        "Transfer Date by Week", "Transfer Year", "RIN Year", "Fuel (D Code)",
        "QAP Service Type", "RIN Price",
    }
    volume_required = {
        "Transfer Date by Week", "Transfer Year", "RIN Year", "Fuel (D Code)", "Assignment",
        "QAP Type", "Total RINs Traded",
    }
    price_rows = _csv_rows(price_csv, price_required, "price")
    volume_rows = _csv_rows(volume_csv, volume_required, "volume")
    volumes: dict[tuple[date, int, int, str], int] = {}
    for row in volume_rows:
        if row["Fuel (D Code)"].strip() != "D6" or row["Assignment"].strip() != "Separated":
            continue
        key = (_parse_date(row["Transfer Date by Week"]), int(row["Transfer Year"]),
               int(row["RIN Year"]), row["QAP Type"].strip())
        if key in volumes:
            raise RinDownloadError(f"Duplicate EPA separated-volume row for {key}")
        volumes[key] = _integer(row["Total RINs Traded"])

    weighted: dict[tuple[date, int], list[float | int]] = defaultdict(lambda: [0.0, 0])
    seen_prices: set[tuple[date, int, int, str]] = set()
    matched = 0
    missing_volume = 0
    for row in price_rows:
        if row["Fuel (D Code)"].strip() != "D6":
            continue
        key = (_parse_date(row["Transfer Date by Week"]), int(row["Transfer Year"]),
               int(row["RIN Year"]), row["QAP Service Type"].strip())
        if key in seen_prices:
            raise RinDownloadError(f"Duplicate EPA price row for {key}")
        seen_prices.add(key)
        volume = volumes.get(key)
        if volume is None or volume == 0:
            missing_volume += 1
            continue
        price = _money(row["RIN Price"])
        bucket = weighted[(key[0], key[2])]
        bucket[0] = float(bucket[0]) + price * volume
        bucket[1] = int(bucket[1]) + volume
        matched += 1

    stamp = _utc_timestamp(captured_at)
    result = [
        RinWeek(week, rin_year, float(total_value) / int(total_volume),
                int(total_volume), stamp, stamp)
        for (week, rin_year), (total_value, total_volume) in sorted(weighted.items())
    ]
    if not result:
        raise RinDownloadError("EPA exports produced no matched D6 price/volume observations")
    return result, {
        "price_rows": len(price_rows), "volume_rows": len(volume_rows),
        "matched_price_volume_rows": matched,
        "price_rows_without_volume": missing_volume, "d6_week_vintage_rows": len(result),
    }


def _write_immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise RinDownloadError(f"Refusing to overwrite immutable raw evidence: {path}")
        return
    path.write_bytes(data)


def _substantive_rows(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "transfer_week", "d_code", "rin_year", "weekly_vwap_usd_per_rin",
            "transaction_volume_rins",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RinDownloadError(
                f"Normalized RIN capture is missing columns: {', '.join(sorted(missing))}"
            )
        result: dict[tuple[str, str, str], dict[str, str]] = {}
        for row in reader:
            key = (row["transfer_week"], row["d_code"], row["rin_year"])
            if key in result:
                raise RinDownloadError(f"Duplicate normalized RIN key in {path}: {key}")
            result[key] = {
                "weekly_vwap_usd_per_rin": row["weekly_vwap_usd_per_rin"],
                "transaction_volume_rins": row["transaction_volume_rins"],
            }
    return result


def build_vintage_diff(
    previous: Path | None, current: Path, previous_capture: str | None,
    current_capture: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    old = _substantive_rows(previous) if previous else {}
    new = _substantive_rows(current)
    old_keys, new_keys = set(old), set(new)
    changed = sorted(key for key in old_keys & new_keys if old[key] != new[key])
    added, deleted = sorted(new_keys - old_keys), sorted(old_keys - new_keys)
    details: list[dict[str, object]] = []
    for status, keys in (("NEW", added), ("CHANGED", changed), ("DELETED", deleted)):
        for key in keys:
            before, after = old.get(key, {}), new.get(key, {})
            details.append({
                "status": status, "transfer_week": key[0], "d_code": key[1],
                "rin_year": key[2],
                "previous_weekly_vwap_usd_per_rin": before.get(
                    "weekly_vwap_usd_per_rin", ""
                ),
                "current_weekly_vwap_usd_per_rin": after.get(
                    "weekly_vwap_usd_per_rin", ""
                ),
                "previous_transaction_volume_rins": before.get(
                    "transaction_volume_rins", ""
                ),
                "current_transaction_volume_rins": after.get(
                    "transaction_volume_rins", ""
                ),
            })
    summary: dict[str, object] = {
        "previous_capture": previous_capture,
        "current_capture": current_capture,
        "new_rows": len(added), "changed_existing_rows": len(changed),
        "deleted_rows": len(deleted),
        "unchanged_rows": len((old_keys & new_keys) - set(changed)),
        "comparison_fields": [
            "weekly_vwap_usd_per_rin", "transaction_volume_rins"
        ],
        "note": (
            "Capture metadata fields are excluded so the diff reports only substantive EPA "
            "observation changes. Transaction volume remains context/weighting input, not a "
            "challenger feature."
        ),
    }
    return summary, details


def write_candidate(
    rows: Iterable[RinWeek], output: Path, combined_hash: str, raw_evidence_id: str
) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "transfer_week", "observed_at", "period_start", "period_end", "d_code",
        "rin_year", "weekly_vwap_usd_per_rin", "transaction_volume_rins",
        "available_at", "captured_at", "source_url", "raw_evidence_id",
        "source_sha256", "schema_version",
    ]
    materialized = list(rows)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in materialized:
            period_end = item.transfer_week + timedelta(days=6)
            writer.writerow({
                "transfer_week": item.transfer_week.isoformat(),
                "observed_at": period_end.isoformat(),
                "period_start": item.transfer_week.isoformat(),
                "period_end": period_end.isoformat(),
                "d_code": "D6", "rin_year": item.rin_year,
                "weekly_vwap_usd_per_rin": f"{item.weekly_vwap_usd_per_rin:.6f}",
                "transaction_volume_rins": item.transaction_volume_rins,
                "available_at": item.available_at.isoformat().replace("+00:00", "Z"),
                "captured_at": item.captured_at.isoformat().replace("+00:00", "Z"),
                "source_url": SOURCE_PAGE, "raw_evidence_id": raw_evidence_id,
                "source_sha256": combined_hash, "schema_version": SCHEMA_VERSION,
            })
    return len(materialized)


def fetch(
    output: Path, provenance: Path, raw_dir: Path,
    captured_at: datetime | None = None, timeout: int = 60,
) -> dict[str, object]:
    captured = _utc_timestamp(captured_at)
    prices, volumes = download_epa_exports(timeout)
    price_hash, volume_hash = _sha256(prices), _sha256(volumes)
    combined_hash = _sha256(f"{price_hash}\n{volume_hash}".encode())
    capture_id = captured.strftime("%Y-%m-%dT%H%M%SZ")
    capture_dir = raw_dir / capture_id
    price_path = capture_dir / "epa-rin-prices.csv"
    volume_path = capture_dir / "epa-rin-volumes.csv"
    _write_immutable(price_path, prices)
    _write_immutable(volume_path, volumes)
    rows, stats = transform_d6(prices, volumes, captured)
    raw_evidence_id = f"epa_rin/{capture_id}"
    count = write_candidate(rows, output, combined_hash, raw_evidence_id)
    normalized_bytes = output.read_bytes()
    normalized_hash = _sha256(normalized_bytes)
    archived_normalized = capture_dir / NORMALIZED_FILENAME
    _write_immutable(archived_normalized, normalized_bytes)
    prior_captures = [
        item for item in raw_dir.iterdir()
        if item.is_dir() and item.name < capture_id and (item / NORMALIZED_FILENAME).exists()
    ]
    previous_dir = max(prior_captures, key=lambda item: item.name) if prior_captures else None
    diff, diff_rows = build_vintage_diff(
        previous_dir / NORMALIZED_FILENAME if previous_dir else None,
        archived_normalized, previous_dir.name if previous_dir else None, capture_id,
    )
    diff_csv = capture_dir / "vintage-diff.csv"
    diff_fields = [
        "status", "transfer_week", "d_code", "rin_year",
        "previous_weekly_vwap_usd_per_rin", "current_weekly_vwap_usd_per_rin",
        "previous_transaction_volume_rins", "current_transaction_volume_rins",
    ]
    _write_dict_csv(diff_csv, diff_rows, diff_fields)
    diff["detail_path"] = str(diff_csv)
    diff["detail_sha256"] = _sha256(diff_csv.read_bytes())
    diff_json = json.dumps(diff, indent=2, sort_keys=True) + "\n"
    (capture_dir / "vintage-diff.json").write_text(diff_json, encoding="utf-8")
    provenance.parent.mkdir(parents=True, exist_ok=True)
    latest_diff_json = provenance.with_name("rin.vintage_diff.json")
    latest_diff_csv = provenance.with_name("rin.vintage_diff.csv")
    latest_diff_json.write_text(diff_json, encoding="utf-8")
    latest_diff_csv.write_bytes(diff_csv.read_bytes())
    spec_hash = research_spec_hash()
    build_id = f"rin-v1-{capture_id}-{spec_hash[:12]}"
    metadata: dict[str, object] = {
        "status": "PROSPECTIVE_CANDIDATE_FEATURE",
        "source": "US EPA EMTS public RIN price and transaction-volume dashboard",
        "source_dataset": "EPA EMTS RIN Price and Transaction Volume Reports",
        "source_url": SOURCE_PAGE,
        "qlik": {
            "host": QLIK_HOST, "application_id": QLIK_APP_ID,
            "price_object_id": PRICE_OBJECT_ID, "volume_object_id": VOLUME_OBJECT_ID,
        },
        "captured_at": captured.isoformat().replace("+00:00", "Z"),
        "availability_policy": (
            "Conservative: every downloaded historical row is marked available only at this "
            "capture timestamp because the live EPA export does not preserve original release "
            "timestamps or revision vintages. It must not be used as historical PIT evidence."
        ),
        "raw": [
            {"path": str(price_path), "sha256": price_hash, "bytes": len(prices)},
            {"path": str(volume_path), "sha256": volume_hash, "bytes": len(volumes)},
        ],
        "combined_sha256": combined_hash, "output": str(output),
        "normalized_capture_path": str(archived_normalized),
        "normalized_file_sha256": normalized_hash,
        "rows_written": count, "first_week": rows[0].transfer_week.isoformat(),
        "last_week": rows[-1].transfer_week.isoformat(), "transform_stats": stats,
        "latest_observation_week": rows[-1].transfer_week.isoformat(),
        "research_spec": RESEARCH_SPEC,
        "research_spec_hash": spec_hash,
        "build_id": build_id,
        "vintage_diff": diff,
        "transform": (
            "D6 only; prices joined to separated transaction volume by week, RIN vintage, "
            "and QAP type; QAP types combined by volume-weighted average; vintages retained."
        ),
        "schema_version": SCHEMA_VERSION,
    }
    provenance.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


def load_rin(path: Path) -> list[RinWeek]:
    required = {
        "transfer_week", "rin_year", "weekly_vwap_usd_per_rin",
        "transaction_volume_rins", "available_at", "captured_at",
    }
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")
        result = []
        for row in reader:
            result.append(RinWeek(
                date.fromisoformat(row["transfer_week"]), int(row["rin_year"]),
                float(row["weekly_vwap_usd_per_rin"]), int(row["transaction_volume_rins"]),
                datetime.fromisoformat(row["available_at"].replace("Z", "+00:00")),
                datetime.fromisoformat(row["captured_at"].replace("Z", "+00:00")),
            ))
    if not result:
        raise ValueError(f"RIN candidate input is empty: {path}")
    return result


def _quarterly_same_vintage(rows: list[RinWeek]) -> dict[str, dict[str, object]]:
    grouped: dict[tuple[int, int], list[RinWeek]] = defaultdict(list)
    for row in rows:
        if row.rin_year != row.transfer_week.year:
            continue
        grouped[(row.transfer_week.year, (row.transfer_week.month - 1) // 3 + 1)].append(row)
    result: dict[str, dict[str, object]] = {}
    for (year, quarter), items in sorted(grouped.items()):
        label = f"{year}Q{quarter}"
        result[label] = {
            "quarter": label,
            "d6_same_vintage_mean_usd_per_rin": sum(
                item.weekly_vwap_usd_per_rin for item in items
            ) / len(items),
            "weeks": len(items),
            "first_week": min(item.transfer_week for item in items).isoformat(),
            "last_week": max(item.transfer_week for item in items).isoformat(),
            "captured_at": max(item.captured_at for item in items),
            "available_at": max(item.available_at for item in items),
        }
    return result


def _quarter_key(actual: QuarterActual) -> tuple[int, int]:
    return actual.start.year, (actual.start.month - 1) // 3 + 1


def _prior_year(actuals: list[QuarterActual], index: int) -> int | None:
    year, quarter = _quarter_key(actuals[index])
    wanted = year - 1, quarter
    return next((i for i, item in enumerate(actuals[:index]) if _quarter_key(item) == wanted), None)


def _fit_beta(xs: list[float], ys: list[float]) -> float:
    denominator = sum(value * value for value in xs)
    return sum(x * y for x, y in zip(xs, ys, strict=True)) / denominator if denominator else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _metric_summary(records: list[dict[str, object]]) -> dict[str, object]:
    model_errors = [float(row["actual_cpg"]) - float(row["challenger_cpg"]) for row in records]
    baseline_errors = [float(row["actual_cpg"]) - float(row["baseline_cpg"]) for row in records]
    model_mae = _mean([abs(value) for value in model_errors])
    baseline_mae = _mean([abs(value) for value in baseline_errors])
    improvements = [abs(base) - abs(model) for base, model in zip(
        baseline_errors, model_errors, strict=True
    )]
    direction = _mean([float(row["direction_correct"]) for row in records])
    mean_improvement = _mean(improvements)
    variance = sum((value - mean_improvement) ** 2 for value in improvements) / max(
        1, len(improvements) - 1
    )
    ci_low = mean_improvement - 1.96 * math.sqrt(variance / len(improvements))
    return {
        "rows": len(records), "challenger_mae_cpg": model_mae,
        "baseline_mae_cpg": baseline_mae,
        "mae_improvement_cpg": mean_improvement,
        "mae_improvement_ci_low_cpg": ci_low,
        "directional_accuracy": direction,
    }


def evaluate(rows: list[RinWeek], actuals: list[QuarterActual]) -> tuple[
    list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, object]
]:
    """Run the preregistered expanding-window challenger and a separate PIT audit."""
    quarters = _quarterly_same_vintage(rows)
    features: list[dict[str, object]] = []
    for label, item in quarters.items():
        year, quarter = int(label[:4]), int(label[-1])
        prior = quarters.get(f"{year - 1}Q{quarter}")
        change = None
        if prior and float(prior["d6_same_vintage_mean_usd_per_rin"]):
            change = (float(item["d6_same_vintage_mean_usd_per_rin"])
                      / float(prior["d6_same_vintage_mean_usd_per_rin"]) - 1.0)
        features.append({
            "quarter": label,
            "d6_same_vintage_mean_usd_per_rin": item["d6_same_vintage_mean_usd_per_rin"],
            "d6_yoy_normalized_change": change,
            "weeks": item["weeks"], "first_week": item["first_week"],
            "last_week": item["last_week"],
            "available_at": item["available_at"].isoformat().replace("+00:00", "Z"),
            "captured_at": item["captured_at"].isoformat().replace("+00:00", "Z"),
        })

    change_training: list[tuple[float, float]] = []
    evaluation: list[dict[str, object]] = []
    checkpoint_ledger: list[dict[str, object]] = []
    for index, actual in enumerate(actuals):
        feature = quarters.get(actual.quarter)
        prior_index = _prior_year(actuals, index)
        prior_feature = quarters.get(actuals[prior_index].quarter) if prior_index is not None else None
        available_weeks = sum(
            1 for row in rows
            if actual.start <= row.transfer_week <= actual.end
            and row.rin_year == row.transfer_week.year
            and row.available_at.date() <= actual.end
        )
        checkpoint_ledger.append({
            "quarter": actual.quarter, "checkpoint": actual.end.isoformat(),
            "candidate_weeks_known_by_checkpoint": available_weeks,
            "pit_eligible": available_weeks > 0,
            "reason": "" if available_weeks else "No historical EPA release/revision timestamp proof",
        })
        if (feature is None or prior_feature is None or prior_index is None
                or actual.supply_rin_cpg is None
                or actuals[prior_index].supply_rin_cpg is None):
            continue
        prior_price = float(prior_feature["d6_same_vintage_mean_usd_per_rin"])
        change = float(feature["d6_same_vintage_mean_usd_per_rin"]) / prior_price - 1.0
        target_change = actual.supply_rin_cpg - actuals[prior_index].supply_rin_cpg
        if len(change_training) >= MIN_TRAINING_CHANGES:
            xs, ys = zip(*change_training, strict=True)
            beta = _fit_beta(list(xs), list(ys))
            baseline = actuals[prior_index].supply_rin_cpg
            challenger = baseline + beta * change
            actual_direction = (target_change > 0) - (target_change < 0)
            predicted_direction = ((challenger - baseline) > 0) - ((challenger - baseline) < 0)
            evaluation.append({
                "quarter": actual.quarter, "actual_cpg": actual.supply_rin_cpg,
                "baseline_cpg": baseline, "challenger_cpg": challenger,
                "d6_yoy_normalized_change": change, "fitted_beta_cpg": beta,
                "training_change_rows": len(change_training),
                "direction_correct": actual_direction == predicted_direction,
                "pit_eligible": False,
            })
        change_training.append((change, target_change))

    exploratory = _metric_summary(evaluation) if evaluation else {"rows": 0}
    prospective = None
    latest_actual = actuals[-1]
    future_labels = sorted(label for label in quarters if label > latest_actual.quarter)
    if future_labels and change_training:
        label = future_labels[0]
        year, quarter_number = int(label[:4]), int(label[-1])
        prior_label = f"{year - 1}Q{quarter_number}"
        prior_actual = next((item for item in actuals if item.quarter == prior_label), None)
        prior_feature = quarters.get(prior_label)
        feature = quarters[label]
        if prior_actual and prior_actual.supply_rin_cpg is not None and prior_feature:
            prior_price = float(prior_feature["d6_same_vintage_mean_usd_per_rin"])
            change = float(feature["d6_same_vintage_mean_usd_per_rin"]) / prior_price - 1.0
            beta = _fit_beta(
                [item[0] for item in change_training], [item[1] for item in change_training]
            )
            start = date(year, 3 * (quarter_number - 1) + 1, 1)
            end_month = 3 * quarter_number
            next_month = date(year + (end_month == 12), end_month % 12 + 1, 1)
            end = next_month - timedelta(days=1)
            first_monday = start + timedelta(days=(-start.weekday()) % 7)
            last_monday = end - timedelta(days=end.weekday())
            expected_weeks = (last_monday - first_monday).days // 7 + 1
            prospective = {
                "quarter": label,
                "baseline_prior_year_supply_rin_cpg": prior_actual.supply_rin_cpg,
                "challenger_supply_rin_cpg": prior_actual.supply_rin_cpg + beta * change,
                "fitted_beta_cpg": beta,
                "d6_same_vintage_mean_usd_per_rin": feature[
                    "d6_same_vintage_mean_usd_per_rin"
                ],
                "d6_yoy_normalized_change": change,
                "observed_weeks": feature["weeks"], "expected_weeks": expected_weeks,
                "coverage": int(feature["weeks"]) / expected_weeks,
                "last_observed_week": feature["last_week"],
                "warning": (
                    "Experimental non-PIT challenger; incomplete EPA quarter and not approved "
                    "for the production all-in margin scenario."
                ),
            }
    gate = {
        "status": "BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF",
        "promote_to_model": False,
        "candidate_state": "PROSPECTIVE_CANDIDATE_FEATURE",
        "pit_evaluation_rows": 0,
        "exploratory_non_pit": exploratory,
        "latest_prospective_read": prospective,
        "reason": (
            "EPA's live export supplies historical observations but not their original release "
            "timestamps or revision vintages. The exploratory result is diagnostic only and "
            "cannot pass a leakage-safe gate. Future captures can build a prospective PIT record."
        ),
        "baseline_unchanged": True,
        "existing_supply_rin_scenario_unchanged": True,
        "preregistered_feature": (
            "same-calendar-quarter change in the arithmetic mean of weekly, same-year-vintage "
            "D6 VWAP; one zero-intercept coefficient fitted in an expanding window"
        ),
    }
    return features, evaluation, checkpoint_ledger, gate


def _write_dict_csv(
    path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fieldnames or (list(rows[0]) if rows else None)
    if fields is None:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def evaluate_to_dir(rin_path: Path, actuals_path: Path, output_dir: Path) -> dict[str, object]:
    rows, actuals = load_rin(rin_path), load_actuals(actuals_path)
    features, evaluation_rows, checkpoint_rows, gate = evaluate(rows, actuals)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_dict_csv(output_dir / "quarter_features.csv", features)
    _write_dict_csv(output_dir / "evaluation.csv", evaluation_rows)
    _write_dict_csv(output_dir / "checkpoint_ledger.csv", checkpoint_rows)
    (output_dir / "gate_status.json").write_text(
        json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        "rin_input": str(rin_path), "rin_input_sha256": _sha256(rin_path.read_bytes()),
        "actuals_input": str(actuals_path),
        "actuals_input_sha256": _sha256(actuals_path.read_bytes()),
        "research_spec": RESEARCH_SPEC,
        "research_spec_hash": research_spec_hash(),
        "outputs": {
            name: _sha256((output_dir / name).read_bytes())
            for name in ("quarter_features.csv", "evaluation.csv", "checkpoint_ledger.csv",
                         "gate_status.json")
        },
        "gate_status": gate["status"],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return gate


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Download EPA D6 RIN data and evaluate the separate MUSA challenger"
    )
    commands = result.add_subparsers(dest="command", required=True)
    fetch_parser = commands.add_parser("fetch", help="Download and transform official EPA data")
    fetch_parser.add_argument("--output", default="data/rin_weekly_candidate.csv", type=Path)
    fetch_parser.add_argument("--provenance", default="data/rin.provenance.json", type=Path)
    fetch_parser.add_argument("--raw-dir", default="data/raw/epa_rin", type=Path)
    fetch_parser.add_argument("--timeout", default=60, type=int)
    evaluate_parser = commands.add_parser("evaluate", help="Run the preregistered research gate")
    evaluate_parser.add_argument("--rin", default="data/rin_weekly_candidate.csv", type=Path)
    evaluate_parser.add_argument("--actuals", default="data/actuals.csv", type=Path)
    evaluate_parser.add_argument("--output-dir", default="data/rin_research", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "fetch":
            metadata = fetch(args.output, args.provenance, args.raw_dir, timeout=args.timeout)
            print(json.dumps(metadata, indent=2, sort_keys=True))
        else:
            gate = evaluate_to_dir(args.rin, args.actuals, args.output_dir)
            print(json.dumps(gate, indent=2, sort_keys=True))
    except (RinDownloadError, ValueError, OSError) as exc:
        parser().error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
