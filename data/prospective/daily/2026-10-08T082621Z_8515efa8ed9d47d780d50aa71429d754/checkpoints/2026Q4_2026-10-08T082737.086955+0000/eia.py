"""Download and align official EIA weekly series into the nowcast schema."""

from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import xlrd


API_ROOT = "https://api.eia.gov/v2/seriesid/"
XLS_ROOT = "https://www.eia.gov/dnav/pet/hist_xls"


@dataclass(frozen=True)
class RegionSeries:
    region: str
    retail: str
    wholesale: str


# EIA retail series are regular all-formulations gasoline including taxes. Spot series
# exclude taxes. The generated spread is therefore a calibration feature, not margin.
DEFAULT_SERIES = (
    RegionSeries("Gulf Coast", "PET.EMM_EPMR_PTE_R30_DPG.W", "PET.EER_EPMRU_PF4_RGC_DPG.W"),
    RegionSeries("Midwest", "PET.EMM_EPMR_PTE_R20_DPG.W", "PET.EER_EPMRU_PF4_RGC_DPG.W"),
    RegionSeries("East Coast", "PET.EMM_EPMR_PTE_R10_DPG.W", "PET.EER_EPMRU_PF4_Y35NY_DPG.W"),
)


class DownloadError(RuntimeError):
    """Raised when EIA data cannot be downloaded or interpreted."""


def _url(series_id: str, api_key: str, start: date, end: date) -> str:
    query = urllib.parse.urlencode({"api_key": api_key, "start": start.isoformat(),
                                    "end": end.isoformat(), "length": 5000})
    return f"{API_ROOT}{urllib.parse.quote(series_id, safe='.') }?{query}"


def fetch_series(series_id: str, api_key: str, start: date, end: date,
                 opener: Callable[..., object] = urllib.request.urlopen) -> list[tuple[date, float]]:
    request = urllib.request.Request(_url(series_id, api_key, start, end),
                                     headers={"User-Agent": "musa-margin-nowcast/0.1"})
    try:
        with opener(request, timeout=30) as response:  # type: ignore[attr-defined]
            payload = json.load(response)
    except Exception as exc:
        raise DownloadError(f"Unable to download EIA series {series_id}: {exc}") from exc
    if payload.get("response", {}).get("warnings"):
        raise DownloadError(f"EIA returned warnings for {series_id}: {payload['response']['warnings']}")
    records = payload.get("response", {}).get("data")
    if not isinstance(records, list):
        raise DownloadError(f"EIA response for {series_id} has no data array")
    result = []
    seen_weeks: set[date] = set()
    for record in records:
        try:
            period = date.fromisoformat(str(record["period"]))
            value = float(record["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DownloadError(f"Malformed EIA observation in {series_id}: {record!r}") from exc
        # The seriesid endpoint can ignore start/end parameters and return its full
        # history. Enforce the caller's requested observation range locally before
        # normalizing differing EIA week-ending conventions.
        if not start <= period <= end:
            continue
        # Normalize all observations to ISO-week Monday. EIA retail and spot weekly
        # observations can carry different week-ending conventions.
        week = period - timedelta(days=period.weekday())
        if week in seen_weeks:
            raise DownloadError(f"EIA series {series_id} contains multiple observations for ISO week {week}")
        seen_weeks.add(week)
        result.append((week, value * 100.0))  # EIA dollars/gallon -> cents/gallon
    if not result:
        raise DownloadError(
            f"EIA returned no observations for {series_id} between {start} and {end}"
        )
    return sorted(result)


def _xls_url(series_id: str) -> str:
    core = series_id.removeprefix("PET.").removesuffix(".W")
    return f"{XLS_ROOT}/{core}w.xls"


def fetch_series_xls(series_id: str, api_key: str, start: date, end: date,
                     opener: Callable[..., object] = urllib.request.urlopen) -> list[tuple[date, float]]:
    """Download an official EIA historical workbook without requiring an API key."""
    del api_key
    request = urllib.request.Request(_xls_url(series_id),
                                     headers={"User-Agent": "musa-margin-nowcast/0.1"})
    try:
        with opener(request, timeout=30) as response:  # type: ignore[attr-defined]
            raw = response.read()  # type: ignore[attr-defined]
        workbook = xlrd.open_workbook(file_contents=raw)
        sheet = workbook.sheet_by_name("Data 1")
    except Exception as exc:
        raise DownloadError(f"Unable to download EIA workbook {series_id}: {exc}") from exc
    expected = series_id.removeprefix("PET.").removesuffix(".W")
    if sheet.nrows < 4 or str(sheet.cell_value(1, 1)).strip() != expected:
        raise DownloadError(f"EIA workbook has an unexpected source key for {series_id}")
    result = []
    seen_weeks: set[date] = set()
    for row in range(3, sheet.nrows):
        try:
            period = xlrd.xldate_as_datetime(
                float(sheet.cell_value(row, 0)), workbook.datemode
            ).date()
            value = float(sheet.cell_value(row, 1))
        except (TypeError, ValueError, xlrd.XLDateError) as exc:
            raise DownloadError(f"Malformed EIA workbook row {row + 1} in {series_id}") from exc
        if not start <= period <= end:
            continue
        week = period - timedelta(days=period.weekday())
        if week in seen_weeks:
            raise DownloadError(f"EIA series {series_id} contains multiple observations for ISO week {week}")
        seen_weeks.add(week)
        result.append((week, value * 100.0))
    if not result:
        raise DownloadError(
            f"EIA workbook returned no observations for {series_id} between {start} and {end}"
        )
    return sorted(result)


def download_market(output: str | Path, provenance: str | Path, api_key: str,
                    start: date, end: date,
                    series: tuple[RegionSeries, ...] = DEFAULT_SERIES,
                    fetcher: Callable[[str, str, date, date], list[tuple[date, float]]] = fetch_series,
                    source: str = "api") -> int:
    cache: dict[str, dict[date, float]] = {}
    rows: list[dict[str, object]] = []
    metadata = {"retrieved_at": date.today().isoformat(), "start": start.isoformat(),
                "end": end.isoformat(), "source": source,
                "source_root": XLS_ROOT if source == "official_xls" else API_ROOT,
                "range_enforcement": (
                    "Requested observation range enforced locally."
                    if source == "official_xls"
                    else "Requested observation range enforced locally because the seriesid endpoint may return full history."
                ),
                "series": []}
    for spec in series:
        for series_id in (spec.retail, spec.wholesale):
            if series_id not in cache:
                cache[series_id] = dict(fetcher(series_id, api_key, start, end))
        common = sorted(set(cache[spec.retail]) & set(cache[spec.wholesale]))
        for week in common:
            rows.append({"week": week.isoformat(), "region": spec.region,
                         "retail_cpg": f"{cache[spec.retail][week]:.4f}",
                         "wholesale_cpg": f"{cache[spec.wholesale][week]:.4f}"})
        metadata["series"].append({"region": spec.region, "retail": spec.retail,
                                   "wholesale": spec.wholesale, "matched_weeks": len(common),
                                   "first_week": common[0].isoformat() if common else None,
                                   "last_week": common[-1].isoformat() if common else None,
                                   "retail_last_week": max(cache[spec.retail]).isoformat(),
                                   "wholesale_last_week": max(cache[spec.wholesale]).isoformat(),
                                   "retail_weeks_without_wholesale": [
                                       week.isoformat() for week in sorted(
                                           set(cache[spec.retail]) - set(cache[spec.wholesale])
                                       )
                                   ],
                                   "wholesale_weeks_without_retail": [
                                       week.isoformat() for week in sorted(
                                           set(cache[spec.wholesale]) - set(cache[spec.retail])
                                       )
                                   ]})
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("week", "region", "retail_cpg", "wholesale_cpg"))
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: (str(row["week"]), str(row["region"]))))
    metadata["rows_written"] = len(rows)
    Path(provenance).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download official EIA inputs for the MUSA nowcast")
    parser.add_argument("--source", choices=("xls", "api"), default="xls",
                        help="official XLS workbooks (default) or EIA API")
    parser.add_argument("--api-key", help="required only with --source api")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--output", default="data/market.csv")
    parser.add_argument("--provenance", default="data/market.provenance.json")
    args = parser.parse_args(argv)
    if args.end < args.start:
        parser.error("end must not precede start")
    if args.source == "api" and not args.api_key:
        parser.error("--api-key is required with --source api")
    try:
        fetcher = fetch_series_xls if args.source == "xls" else fetch_series
        count = download_market(
            args.output, args.provenance, args.api_key or "", args.start, args.end,
            fetcher=fetcher, source="official_xls" if args.source == "xls" else "api",
        )
    except DownloadError as exc:
        parser.error(str(exc))
    print(f"Wrote {count} aligned regional observations to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
