"""Wholesale feature construction with explicit point-in-time semantics."""

from bisect import bisect_right
from collections.abc import Iterable
from datetime import date, timedelta


def _normalize(rows: Iterable[tuple[date, float]]) -> tuple[list[date], list[float]]:
    grouped: dict[date, list[float]] = {}
    for day, value in rows:
        grouped.setdefault(day, []).append(float(value))
    days = sorted(grouped)
    # Equal averaging is the documented fallback when quote volume is absent.
    values = [sum(grouped[d]) / len(grouped[d]) for d in days]
    if not days:
        raise ValueError("at least one wholesale observation is required")
    return days, values


def _asof(days: list[date], values: list[float], target: date) -> tuple[int, float]:
    index = bisect_right(days, target) - 1
    if index < 0:
        raise ValueError(f"no wholesale observation known by {target.isoformat()}")
    return index, values[index]


def build_candidates(
    retail_dates: Iterable[date], wholesale_rows: Iterable[tuple[date, float]]
) -> list[dict[str, float | date]]:
    """Return point-in-time wholesale candidates for every retail observation.

    Trailing windows count available observations (trading days), while weekly
    lags use calendar days and an as-of lookup.  No future quote is ever used.
    """
    days, values = _normalize(wholesale_rows)
    output: list[dict[str, float | date]] = []
    for retail_day in retail_dates:
        index, same_day = _asof(days, values, retail_day)
        if index < 6:
            raise ValueError(f"seven prior observations required by {retail_day.isoformat()}")
        _, lag_1w = _asof(days, values, retail_day - timedelta(days=7))
        _, lag_2w = _asof(days, values, retail_day - timedelta(days=14))
        output.append(
            {
                "date": retail_day,
                "same_day": same_day,
                "trailing_3d": sum(values[index - 2 : index + 1]) / 3,
                "trailing_7d": sum(values[index - 6 : index + 1]) / 7,
                "lag_1w": lag_1w,
                "lag_2w": lag_2w,
            }
        )
    return output

