"""CSV loading and validation for the nowcast model."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path


class DataError(ValueError):
    """Raised when an input cannot be used safely by the model."""


@dataclass(frozen=True)
class MarketWeek:
    week: date
    region: str
    retail_cpg: float
    wholesale_cpg: float


@dataclass(frozen=True)
class RegionWeight:
    region: str
    weight: float


@dataclass(frozen=True)
class QuarterActual:
    quarter: str
    start: date
    end: date
    retail_margin_cpg: float
    supply_rin_cpg: float
    gallons_million: float | None = None


def _rows(path: str | Path, required: set[str]) -> list[dict[str, str]]:
    path = Path(path)
    if not path.exists():
        raise DataError(f"Input file does not exist: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise DataError(f"{path} is missing columns: {', '.join(sorted(missing))}")
        return list(reader)


def _date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise DataError(f"Invalid {field} date {value!r}; expected YYYY-MM-DD") from exc


def _number(value: str, field: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise DataError(f"Invalid number for {field}: {value!r}") from exc
    if result != result or result in (float("inf"), float("-inf")):
        raise DataError(f"{field} must be finite")
    return result


def load_market(path: str | Path) -> list[MarketWeek]:
    required = {"week", "region", "retail_cpg", "wholesale_cpg"}
    result: list[MarketWeek] = []
    seen: set[tuple[date, str]] = set()
    for row in _rows(path, required):
        week = _date(row["week"], "week")
        region = row["region"].strip()
        if not region:
            raise DataError("region may not be blank")
        key = (week, region)
        if key in seen:
            raise DataError(f"Duplicate market observation for {week} / {region}")
        seen.add(key)
        result.append(MarketWeek(week, region, _number(row["retail_cpg"], "retail_cpg"),
                                 _number(row["wholesale_cpg"], "wholesale_cpg")))
    if not result:
        raise DataError("Market input is empty")
    return sorted(result, key=lambda item: (item.week, item.region))


def load_weights(path: str | Path) -> list[RegionWeight]:
    required = {"region", "weight"}
    result = [RegionWeight(row["region"].strip(), _number(row["weight"], "weight"))
              for row in _rows(path, required)]
    if not result or any(not item.region or item.weight <= 0 for item in result):
        raise DataError("Weights require nonblank regions and positive values")
    if len({item.region for item in result}) != len(result):
        raise DataError("Each region may appear only once in weights")
    total = sum(item.weight for item in result)
    if abs(total - 1.0) > 0.001:
        raise DataError(f"Region weights must sum to 1.0 (found {total:.6f})")
    return result


def load_actuals(path: str | Path) -> list[QuarterActual]:
    required = {"quarter", "start", "end", "retail_margin_cpg", "supply_rin_cpg"}
    result: list[QuarterActual] = []
    for row in _rows(path, required):
        start, end = _date(row["start"], "start"), _date(row["end"], "end")
        if end < start:
            raise DataError(f"Quarter {row['quarter']} ends before it starts")
        gallons = row.get("gallons_million", "").strip()
        result.append(QuarterActual(
            row["quarter"].strip(), start, end,
            _number(row["retail_margin_cpg"], "retail_margin_cpg"),
            _number(row["supply_rin_cpg"], "supply_rin_cpg"),
            _number(gallons, "gallons_million") if gallons else None,
        ))
    if len(result) < 6:
        raise DataError("At least six historical quarters are required for calibration")
    if len({item.quarter for item in result}) != len(result):
        raise DataError("Quarter labels must be unique")
    return sorted(result, key=lambda item: item.start)

