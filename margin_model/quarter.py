"""MUSA fiscal-quarter calendar and overlap-weighted weekly aggregation."""

from dataclasses import dataclass
from datetime import date, timedelta
from csv import DictReader
from pathlib import Path


@dataclass(frozen=True)
class FiscalQuarter:
    label: str
    start: date
    end: date  # inclusive


def load_fiscal_quarters(path: str | Path) -> dict[str, FiscalQuarter]:
    """Load explicitly reported quarter boundaries from the maintained calendar."""
    with Path(path).open(newline="", encoding="utf-8") as stream:
        quarters = {
            row["fiscal_quarter"]: FiscalQuarter(
                row["fiscal_quarter"], date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"])
            )
            for row in DictReader(stream)
        }
    if not quarters:
        raise ValueError("fiscal-quarter calendar is empty")
    return quarters


def weighted_quarter_average(
    weekly_rows: list[tuple[date, float]], quarter: FiscalQuarter
) -> float:
    """Average weekly levels using calendar-day overlap with a fiscal quarter."""
    rows = sorted(weekly_rows)
    weighted_sum = 0.0
    covered_days = 0
    quarter_stop = quarter.end + timedelta(days=1)
    for index, (start, value) in enumerate(rows):
        stop = rows[index + 1][0] if index + 1 < len(rows) else start + timedelta(days=7)
        overlap_start, overlap_stop = max(start, quarter.start), min(stop, quarter_stop)
        days = max(0, (overlap_stop - overlap_start).days)
        weighted_sum += days * float(value)
        covered_days += days
    expected = (quarter_stop - quarter.start).days
    if covered_days != expected:
        raise ValueError(f"weekly observations cover {covered_days} of {expected} fiscal-quarter days")
    return weighted_sum / covered_days
