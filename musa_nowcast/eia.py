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


API_ROOT = "https://api.eia.gov/v2/seriesid/"


@dataclass(frozen=True)
class RegionSeries:
    region: str
    retail: str
    wholesale: str


# EIA retail series are regular conventional gasoline including taxes. Spot series
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
        # Normalize all observations to ISO-week Monday. EIA retail and spot weekly
        # observations can carry different week-ending conventions.
        week = period - timedelta(days=period.weekday())
        if week in seen_weeks:
            raise DownloadError(f"EIA series {series_id} contains multiple observations for ISO week {week}")
        seen_weeks.add(week)
        result.append((week, value * 100.0))  # EIA dollars/gallon -> cents/gallon
    if not result:
        raise DownloadError(f"EIA returned no observations for {series_id}")
    return sorted(result)


def download_market(output: str | Path, provenance: str | Path, api_key: str,
                    start: date, end: date,
                    series: tuple[RegionSeries, ...] = DEFAULT_SERIES,
                    fetcher: Callable[[str, str, date, date], list[tuple[date, float]]] = fetch_series) -> int:
    cache: dict[str, dict[date, float]] = {}
    rows: list[dict[str, object]] = []
    metadata = {"retrieved_at": date.today().isoformat(), "start": start.isoformat(),
                "end": end.isoformat(), "api": API_ROOT, "series": []}
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
                                   "wholesale": spec.wholesale, "matched_weeks": len(common)})
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("week", "region", "retail_cpg", "wholesale_cpg"))
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: (str(row["week"]), str(row["region"]))))
    Path(provenance).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download official EIA inputs for the MUSA nowcast")
    parser.add_argument("--api-key", required=True, help="EIA API key (use DEMO_KEY only for testing)")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--output", default="data/market.csv")
    parser.add_argument("--provenance", default="data/market.provenance.json")
    args = parser.parse_args(argv)
    if args.end < args.start:
        parser.error("end must not precede start")
    try:
        count = download_market(args.output, args.provenance, args.api_key, args.start, args.end)
    except DownloadError as exc:
        parser.error(str(exc))
    print(f"Wrote {count} aligned regional observations to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
