"""Point-in-time geographic retail challenger for the MUSA margin model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
import xlrd
from lxml import html

from .data import MarketWeek, RegionWeight, load_actuals, load_market, load_weights
from .mathutils import RidgeModel
from .model import (
    MARKET_CHANGE_SHRINKAGE,
    MIN_BACKTEST_QUARTERS,
    MIN_BASELINE_IMPROVEMENT,
    MIN_DIRECTIONAL_ACCURACY,
    MIN_TRAINING_QUARTERS,
    NORMAL_95_Z,
    RECENT_BACKTEST_QUARTERS,
    NowcastEngine,
)


EIA_XLS_ROOT = "https://www.eia.gov/dnav/pet/hist_xls"
EIA_SOURCE_PAGE = "https://www.eia.gov/dnav/pet/PET_PRI_GND_A_EPMR_PTE_DPGAL_W.htm"
SEC_ARCHIVES_ROOT = "https://www.sec.gov/Archives/edgar/data/1573516"
SEC_USER_AGENT = "OpenAI Codex research contact@openai.com"
SPEC_ID = "MUSA_GEO_RETAIL_CHALLENGER_V1"
GEO_REGION = "MUSA GEO-A"


@dataclass(frozen=True)
class Filing:
    report_year: int
    filed_at: date
    accession: str
    document: str

    @property
    def url(self) -> str:
        accession = self.accession.replace("-", "")
        return f"{SEC_ARCHIVES_ROOT}/{accession}/{self.document}"


SEC_FILINGS = (
    Filing(2017, date(2018, 2, 20), "0001573516-18-000010", "musa_12312017x10-kxdoc.htm"),
    Filing(2018, date(2019, 2, 19), "0001573516-19-000012", "musa_12312018x10-kxdoc.htm"),
    Filing(2019, date(2020, 2, 18), "0001573516-20-000007", "musa1231201910-kdoc.htm"),
    Filing(2020, date(2021, 2, 19), "0001573516-21-000017", "musa-20201231.htm"),
    Filing(2021, date(2022, 2, 17), "0001573516-22-000006", "musa-20211231.htm"),
    Filing(2022, date(2023, 2, 15), "0001573516-23-000011", "musa-20221231.htm"),
    Filing(2023, date(2024, 2, 16), "0001573516-24-000007", "musa-20231231.htm"),
    Filing(2024, date(2025, 2, 20), "0001573516-25-000010", "musa-20241231.htm"),
    Filing(2025, date(2026, 2, 18), "0001573516-26-000090", "musa-20251231.htm"),
)


STATE_SERIES = {
    "Colorado": "PET.EMM_EPMR_PTE_SCO_DPG.W",
    "Florida": "PET.EMM_EPMR_PTE_SFL_DPG.W",
    "Minnesota": "PET.EMM_EPMR_PTE_SMN_DPG.W",
    "New York": "PET.EMM_EPMR_PTE_SNY_DPG.W",
    "Ohio": "PET.EMM_EPMR_PTE_SOH_DPG.W",
    "Texas": "PET.EMM_EPMR_PTE_STX_DPG.W",
}
PADD_RETAIL_SERIES = {
    "PADD1B": "PET.EMM_EPMR_PTE_R1Y_DPG.W",
    "PADD1C": "PET.EMM_EPMR_PTE_R1Z_DPG.W",
    "PADD2": "PET.EMM_EPMR_PTE_R20_DPG.W",
    "PADD3": "PET.EMM_EPMR_PTE_R30_DPG.W",
    "PADD4": "PET.EMM_EPMR_PTE_R40_DPG.W",
    "PADD5": "PET.EMM_EPMR_PTE_R50_DPG.W",
}
WHOLESALE_SERIES = {
    "NYH": "PET.EER_EPMRU_PF4_Y35NY_DPG.W",
    "USGC": "PET.EER_EPMRU_PF4_RGC_DPG.W",
}

STATE_PADD = {
    "Alabama": "PADD3", "Arkansas": "PADD3", "Colorado": "PADD4",
    "Florida": "PADD1C", "Georgia": "PADD1C", "Iowa": "PADD2",
    "Illinois": "PADD2", "Indiana": "PADD2", "Kansas": "PADD2",
    "Kentucky": "PADD2", "Louisiana": "PADD3", "Michigan": "PADD2",
    "Minnesota": "PADD2", "Mississippi": "PADD3", "Missouri": "PADD2",
    "Nebraska": "PADD2", "Nevada": "PADD5", "New Jersey": "PADD1B",
    "New Mexico": "PADD3", "New York": "PADD1B", "North Carolina": "PADD1C",
    "Ohio": "PADD2", "Oklahoma": "PADD2", "South Carolina": "PADD1C",
    "Tennessee": "PADD2", "Texas": "PADD3", "Utah": "PADD4",
    "Virginia": "PADD1C",
}


class GeoError(RuntimeError):
    """Raised when geographic source data cannot be used safely."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _clean(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").replace("�", " ").split())


def extract_state_counts(raw_html: bytes) -> tuple[dict[str, int], int]:
    """Extract and validate the state-store table from a MUSA Form 10-K."""
    tree = html.fromstring(raw_html)
    candidate = None
    for table in tree.xpath("//table"):
        text = _clean(table.text_content())
        if "Alabama" in text and "Texas" in text and "Total" in text:
            candidate = table
            break
    if candidate is None:
        raise GeoError("Could not find the state-store table in the SEC filing")
    counts: dict[str, int] = {}
    reported_total = None
    for row in candidate.xpath(".//tr"):
        cells = [_clean(cell.text_content()) for cell in row.xpath("./th|./td")]
        for index, cell in enumerate(cells):
            state = next((name for name in STATE_PADD if cell == name), None)
            if state:
                for following in cells[index + 1:]:
                    if following in STATE_PADD or following == "Total":
                        break
                    match = re.fullmatch(r"([0-9][0-9,]*)", following)
                    if match:
                        counts[state] = int(match.group(1).replace(",", ""))
                        break
            if cell == "Total":
                for following in cells[index + 1:]:
                    match = re.fullmatch(r"([0-9][0-9,]*)", following)
                    if match:
                        reported_total = int(match.group(1).replace(",", ""))
                        break
    if reported_total is None or not counts:
        raise GeoError("SEC state-store table is missing its total or state observations")
    if sum(counts.values()) != reported_total:
        raise GeoError(
            f"SEC state-store table does not reconcile: states={sum(counts.values())}, "
            f"reported={reported_total}"
        )
    return counts, reported_total


def _write_immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise GeoError(f"Refusing to overwrite immutable evidence: {path}")
        return
    path.write_bytes(data)


def _eia_xls_url(series_id: str) -> str:
    core = series_id.removeprefix("PET.").removesuffix(".W")
    return f"{EIA_XLS_ROOT}/{core}w.xls"


def parse_eia(raw: bytes, series_id: str, start: date, end: date) -> dict[date, float]:
    try:
        payload = json.loads(raw)
        records = payload["response"]["data"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise GeoError(f"Malformed EIA response for {series_id}") from exc
    result: dict[date, float] = {}
    for record in records:
        try:
            observed = date.fromisoformat(str(record["period"]))
            value = float(record["value"]) * 100.0
        except (KeyError, TypeError, ValueError) as exc:
            raise GeoError(f"Malformed EIA observation for {series_id}: {record!r}") from exc
        if not start <= observed <= end:
            continue
        week = observed - timedelta(days=observed.weekday())
        if week in result:
            raise GeoError(f"Duplicate EIA week for {series_id}: {week}")
        result[week] = value
    if not result:
        raise GeoError(f"EIA returned no observations for {series_id}")
    return result


def parse_eia_xls(raw: bytes, series_id: str, start: date, end: date) -> dict[date, float]:
    try:
        workbook = xlrd.open_workbook(file_contents=raw)
        sheet = workbook.sheet_by_name("Data 1")
    except (xlrd.XLRDError, IndexError) as exc:
        raise GeoError(f"Malformed EIA XLS workbook for {series_id}") from exc
    expected_key = series_id.removeprefix("PET.").removesuffix(".W")
    if sheet.nrows < 4 or _clean(str(sheet.cell_value(1, 1))) != expected_key:
        raise GeoError(f"Unexpected EIA source key for {series_id}")
    result: dict[date, float] = {}
    for row_index in range(3, sheet.nrows):
        try:
            observed = xlrd.xldate_as_datetime(
                float(sheet.cell_value(row_index, 0)), workbook.datemode
            ).date()
            value = float(sheet.cell_value(row_index, 1)) * 100.0
        except (TypeError, ValueError, xlrd.XLDateError) as exc:
            raise GeoError(f"Malformed EIA XLS row {row_index + 1} for {series_id}") from exc
        if not start <= observed <= end:
            continue
        week = observed - timedelta(days=observed.weekday())
        if week in result:
            raise GeoError(f"Duplicate EIA week for {series_id}: {week}")
        result[week] = value
    if not result:
        raise GeoError(f"EIA XLS returned no observations for {series_id}")
    return result


def _retail_mapping(state: str) -> tuple[str, str]:
    if state in STATE_SERIES:
        return STATE_SERIES[state], "STATE"
    padd = STATE_PADD[state]
    return PADD_RETAIL_SERIES[padd], "PADD_SUBDIVISION" if padd in {"PADD1B", "PADD1C"} else "PADD"


def _wholesale_mapping(state: str) -> str | None:
    padd = STATE_PADD[state]
    if padd in {"PADD1B", "PADD1C"}:
        return WHOLESALE_SERIES["NYH"]
    if padd in {"PADD2", "PADD3"}:
        return WHOLESALE_SERIES["USGC"]
    return None


def research_spec() -> dict[str, object]:
    return {
        "id": SPEC_ID,
        "target": "MUSA reported retail fuel margin cpg",
        "features": ["spread", "falling_capture", "rising_squeeze", "volatility"],
        "retail_hierarchy": ["STATE", "PADD1_SUBDIVISION", "PADD"],
        "wholesale": "unchanged production proxy mapping",
        "weights": "latest SEC state-store table available at each weekly checkpoint",
        "missingness": "no silent geography substitution",
        "excluded_geographies": {
            "PADD4": "no validated production wholesale proxy",
            "PADD5": "no validated production wholesale proxy",
        },
        "fit": "same ridge alpha and market-change shrinkage as production",
        "comparator": "validated production model on identical quarters",
        "promotion_gate": {
            "minimum_mae_improvement": MIN_BASELINE_IMPROVEMENT,
            "paired_95pct_lower_bound_positive": True,
            "directional_accuracy_not_worse": True,
            "recent_eight_mae_improvement": MIN_BASELINE_IMPROVEMENT,
        },
        "city_series": "OUT_OF_SCOPE",
        "fuel_formulation": "OUT_OF_SCOPE",
    }


def _spec_hash() -> str:
    return _sha256(json.dumps(research_spec(), sort_keys=True, separators=(",", ":")).encode())


def fetch(
    start: date, end: date, output_dir: Path, raw_root: Path,
    captured_at: datetime | None = None,
) -> dict[str, object]:
    if end < start:
        raise GeoError("end must not precede start")
    captured = (captured_at or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    capture_id = captured.strftime("%Y-%m-%dT%H%M%SZ")
    raw_dir = raw_root / capture_id
    session = requests.Session()
    session.headers.update({"User-Agent": SEC_USER_AGENT})
    state_snapshots: list[dict[str, object]] = []
    raw_manifest: list[dict[str, object]] = []
    try:
        for filing in SEC_FILINGS:
            response = session.get(filing.url, timeout=60)
            response.raise_for_status()
            raw = response.content
            path = raw_dir / "sec" / f"{filing.report_year}-{filing.document}"
            _write_immutable(path, raw)
            digest = _sha256(raw)
            counts, total = extract_state_counts(raw)
            for state, count in sorted(counts.items()):
                state_snapshots.append({
                    "report_date": f"{filing.report_year}-12-31",
                    "available_at": filing.filed_at.isoformat(), "state": state,
                    "store_count": count, "reported_total": total,
                    "source_url": filing.url, "raw_sha256": digest,
                })
            raw_manifest.append({
                "kind": "SEC_10-K", "report_year": filing.report_year,
                "available_at": filing.filed_at.isoformat(), "source_url": filing.url,
                "path": str(path), "sha256": digest, "bytes": len(raw),
            })

        series_ids = sorted(
            set(STATE_SERIES.values()) | set(PADD_RETAIL_SERIES.values())
            | set(WHOLESALE_SERIES.values())
        )
        series_data: dict[str, dict[date, float]] = {}
        for series_id in series_ids:
            source_url = _eia_xls_url(series_id)
            response = session.get(source_url, timeout=60)
            response.raise_for_status()
            raw = response.content
            path = raw_dir / "eia" / f"{series_id.replace('.', '_')}.xls"
            _write_immutable(path, raw)
            digest = _sha256(raw)
            series_data[series_id] = parse_eia_xls(raw, series_id, start, end)
            raw_manifest.append({
                "kind": "EIA_SERIES", "series_id": series_id,
                "source_url": source_url,
                "path": str(path), "sha256": digest, "bytes": len(raw),
                "first_week": min(series_data[series_id]).isoformat(),
                "last_week": max(series_data[series_id]).isoformat(),
            })
    except (requests.RequestException, OSError) as exc:
        raise GeoError(f"Unable to download geographic source data: {exc}") from exc
    finally:
        session.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    counts_path = output_dir / "state_store_counts.csv"
    _write_csv(counts_path, state_snapshots)
    mapping_rows = []
    for state, padd in sorted(STATE_PADD.items()):
        retail, level = _retail_mapping(state)
        wholesale = _wholesale_mapping(state)
        mapping_rows.append({
            "state": state, "padd": padd, "retail_series_id": retail,
            "retail_geography_level": level,
            "wholesale_proxy_series_id": wholesale or "",
            "included_in_geo_a": wholesale is not None,
            "missing_rule": "" if wholesale else "EXCLUDED_NO_VALIDATED_WHOLESALE_PROXY",
        })
    mapping_path = output_dir / "state_series_map.csv"
    _write_csv(mapping_path, mapping_rows)

    by_available: dict[date, dict[str, int]] = defaultdict(dict)
    report_for_available: dict[date, str] = {}
    for row in state_snapshots:
        available = date.fromisoformat(str(row["available_at"]))
        by_available[available][str(row["state"])] = int(row["store_count"])
        report_for_available[available] = str(row["report_date"])
    all_weeks = sorted(set.intersection(*(set(values) for values in series_data.values())))
    detail_rows: list[dict[str, object]] = []
    basket_rows: list[dict[str, object]] = []
    source_hash = _sha256("\n".join(sorted(str(item["sha256"]) for item in raw_manifest)).encode())
    for week in all_weeks:
        eligible_snapshots = [available for available in by_available if available <= week]
        if not eligible_snapshots:
            continue
        available = max(eligible_snapshots)
        counts = by_available[available]
        included_states = [state for state in counts if _wholesale_mapping(state) is not None]
        included_total = sum(counts[state] for state in included_states)
        full_total = sum(counts.values())
        retail_basket = wholesale_basket = 0.0
        for state, count in sorted(counts.items()):
            retail_id, level = _retail_mapping(state)
            wholesale_id = _wholesale_mapping(state)
            included = wholesale_id is not None
            model_weight = count / included_total if included else 0.0
            footprint_weight = count / full_total
            retail = series_data[retail_id][week]
            wholesale = series_data[wholesale_id][week] if wholesale_id else None
            if included:
                retail_basket += model_weight * retail
                wholesale_basket += model_weight * float(wholesale)
            detail_rows.append({
                "week": week.isoformat(), "state": state,
                "store_weight": f"{model_weight:.9f}",
                "full_footprint_weight": f"{footprint_weight:.9f}",
                "store_count": count, "weight_report_date": report_for_available[available],
                "weight_available_at": available.isoformat(),
                "retail_series_id": retail_id, "retail_geography_level": level,
                "retail_cpg": f"{retail:.4f}",
                "wholesale_proxy_series_id": wholesale_id or "",
                "wholesale_proxy_cpg": f"{wholesale:.4f}" if wholesale is not None else "",
                "raw_spread_cpg": f"{retail - wholesale:.4f}" if wholesale is not None else "",
                "included_in_geo_a": included,
                "missing_rule": "" if included else "EXCLUDED_NO_VALIDATED_WHOLESALE_PROXY",
                "available_at": week.isoformat(),
                "captured_at": captured.isoformat().replace("+00:00", "Z"),
                "source_hash": source_hash,
            })
        basket_rows.append({
            "week": week.isoformat(), "region": GEO_REGION,
            "retail_cpg": f"{retail_basket:.4f}",
            "wholesale_cpg": f"{wholesale_basket:.4f}",
        })

    detail_path = output_dir / "geo_state_weekly.csv"
    basket_path = output_dir / "geo_basket.csv"
    _write_csv(detail_path, detail_rows)
    _write_csv(basket_path, basket_rows)
    normalized_hashes = {
        path.name: _sha256(path.read_bytes())
        for path in (counts_path, mapping_path, detail_path, basket_path)
    }
    metadata: dict[str, object] = {
        "status": "CHALLENGER_ONLY", "spec": research_spec(),
        "research_spec_hash": _spec_hash(),
        "build_id": f"geo-v1-{capture_id}-{_spec_hash()[:12]}",
        "captured_at": captured.isoformat().replace("+00:00", "Z"),
        "requested_range": {"start": start.isoformat(), "end": end.isoformat()},
        "eia_source_page": EIA_SOURCE_PAGE,
        "raw_manifest": raw_manifest, "combined_raw_sha256": source_hash,
        "normalized_hashes": normalized_hashes,
        "rows": {
            "state_store_counts": len(state_snapshots),
            "state_weekly": len(detail_rows), "weekly_basket": len(basket_rows),
        },
        "first_week": basket_rows[0]["week"], "last_week": basket_rows[-1]["week"],
        "availability": (
            "SEC weights use filing dates. EIA observations use their published weekly period; "
            "the current EIA export does not preserve historical revision vintages."
        ),
    }
    provenance = output_dir / "geo.provenance.json"
    provenance.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    archived = raw_dir / "normalized"
    for path in (counts_path, mapping_path, detail_path, basket_path, provenance):
        _write_immutable(archived / path.name, path.read_bytes())
    return metadata


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise GeoError(f"Refusing to write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _predictions(engine: NowcastEngine) -> list[dict[str, object]]:
    rows, targets = engine._training()
    result = []
    for held_out in range(MIN_TRAINING_QUARTERS, len(rows)):
        prior_year = engine._prior_year_index(held_out)
        if prior_year is None:
            continue
        seasonal = targets[prior_year]
        change_rows, change_targets = engine._change_training(rows, targets, held_out)
        market_change = RidgeModel(engine.alpha).fit(change_rows, change_targets).predict_one(
            engine._changes(rows[held_out], rows[prior_year])
        )
        prediction = seasonal + MARKET_CHANGE_SHRINKAGE * market_change
        result.append({
            "quarter": engine.actuals[held_out].quarter, "actual_cpg": targets[held_out],
            "prediction_cpg": prediction, "seasonal_cpg": seasonal,
            "direction_correct": engine._direction(targets[held_out] - seasonal)
            == engine._direction(prediction - seasonal),
        })
    return result


def compare(champion: NowcastEngine, challenger: NowcastEngine) -> tuple[list[dict[str, object]], dict[str, object]]:
    champion_rows = {str(row["quarter"]): row for row in _predictions(champion)}
    challenger_rows = {str(row["quarter"]): row for row in _predictions(challenger)}
    quarters = sorted(set(champion_rows) & set(challenger_rows))
    paired = []
    for quarter in quarters:
        champ, chall = champion_rows[quarter], challenger_rows[quarter]
        actual = float(champ["actual_cpg"])
        champ_error = abs(actual - float(champ["prediction_cpg"]))
        chall_error = abs(actual - float(chall["prediction_cpg"]))
        paired.append({
            "quarter": quarter, "actual_cpg": actual,
            "production_prediction_cpg": champ["prediction_cpg"],
            "geo_a_prediction_cpg": chall["prediction_cpg"],
            "production_abs_error_cpg": champ_error,
            "geo_a_abs_error_cpg": chall_error,
            "paired_improvement_cpg": champ_error - chall_error,
            "production_direction_correct": champ["direction_correct"],
            "geo_a_direction_correct": chall["direction_correct"],
        })
    if not paired:
        raise GeoError("No identical champion/challenger backtest rows")
    improvements = [float(row["paired_improvement_cpg"]) for row in paired]
    mean_improvement = sum(improvements) / len(improvements)
    variance = sum((value - mean_improvement) ** 2 for value in improvements) / max(1, len(improvements) - 1)
    ci_low = mean_improvement - NORMAL_95_Z * math.sqrt(variance / len(improvements))
    production_mae = sum(float(row["production_abs_error_cpg"]) for row in paired) / len(paired)
    challenger_mae = sum(float(row["geo_a_abs_error_cpg"]) for row in paired) / len(paired)
    production_direction = sum(bool(row["production_direction_correct"]) for row in paired) / len(paired)
    challenger_direction = sum(bool(row["geo_a_direction_correct"]) for row in paired) / len(paired)
    recent = paired[-min(RECENT_BACKTEST_QUARTERS, len(paired)):]
    recent_prod = sum(float(row["production_abs_error_cpg"]) for row in recent) / len(recent)
    recent_geo = sum(float(row["geo_a_abs_error_cpg"]) for row in recent) / len(recent)
    recent_prod_direction = sum(bool(row["production_direction_correct"]) for row in recent) / len(recent)
    recent_geo_direction = sum(bool(row["geo_a_direction_correct"]) for row in recent) / len(recent)
    promoted = (
        len(paired) >= MIN_BACKTEST_QUARTERS
        and challenger_mae <= production_mae * (1.0 - MIN_BASELINE_IMPROVEMENT)
        and challenger_direction >= production_direction
        and challenger_direction >= MIN_DIRECTIONAL_ACCURACY
        and ci_low > 0
        and recent_geo <= recent_prod * (1.0 - MIN_BASELINE_IMPROVEMENT)
        and recent_geo_direction >= recent_prod_direction
    )
    gate = {
        "spec_id": SPEC_ID, "status": "PROMOTED" if promoted else "NOT_PROMOTED",
        "research_spec_status": "FROZEN",
        "research_result": "PROMOTED" if promoted else "NO_INCREMENTAL_VALUE",
        "promote_to_production": promoted, "identical_backtest_rows": len(paired),
        "production_mae_cpg": production_mae, "geo_a_mae_cpg": challenger_mae,
        "mean_paired_improvement_cpg": mean_improvement,
        "paired_improvement_ci_low_cpg": ci_low,
        "production_directional_accuracy": production_direction,
        "geo_a_directional_accuracy": challenger_direction,
        "recent_eight_production_mae_cpg": recent_prod,
        "recent_eight_geo_a_mae_cpg": recent_geo,
        "recent_eight_production_directional_accuracy": recent_prod_direction,
        "recent_eight_geo_a_directional_accuracy": recent_geo_direction,
        "production_model_unchanged": True,
        "reason": (
            "GEO-A must beat the production model by at least 10%, preserve directional "
            "accuracy, have a positive paired 95% lower bound, and repeat the improvement "
            "over the latest eight quarters."
        ),
    }
    return paired, gate


def evaluate(
    geo_dir: Path, market_path: Path, weights_path: Path, actuals_path: Path,
    output_dir: Path, quarter: str, start: date, end: date, as_of: date,
) -> dict[str, object]:
    actuals = load_actuals(actuals_path)
    production = NowcastEngine(load_market(market_path), load_weights(weights_path), actuals)
    challenger = NowcastEngine(
        load_market(geo_dir / "geo_basket.csv"), [RegionWeight(GEO_REGION, 1.0)], actuals
    )
    paired, gate = compare(production, challenger)
    production_forecast = production.forecast(quarter, start, end, as_of).as_dict()
    challenger_forecast = challenger.forecast(quarter, start, end, as_of).as_dict()
    forecast = {
        "quarter": quarter, "as_of": as_of.isoformat(),
        "production_retail_margin_cpg": production_forecast["retail_margin_cpg"],
        "geo_a_retail_margin_cpg": challenger_forecast["retail_margin_cpg"],
        "production_retail_low_cpg": production_forecast["retail_low_cpg"],
        "production_retail_high_cpg": production_forecast["retail_high_cpg"],
        "geo_a_retail_low_cpg": challenger_forecast["retail_low_cpg"],
        "geo_a_retail_high_cpg": challenger_forecast["retail_high_cpg"],
        "production_coverage": production_forecast["coverage"],
        "geo_a_coverage": challenger_forecast["coverage"],
        "status": "PRODUCTION" if gate["promote_to_production"] else "EXPERIMENTAL_ONLY",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "evaluation.csv", paired)
    (output_dir / "gate_status.json").write_text(
        json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "current_forecast.json").write_text(
        json.dumps(forecast, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "research_spec": research_spec(), "research_spec_hash": _spec_hash(),
        "inputs": {
            str(path): _sha256(path.read_bytes()) for path in (
                geo_dir / "geo_basket.csv", geo_dir / "geo_state_weekly.csv",
                geo_dir / "state_store_counts.csv", geo_dir / "state_series_map.csv",
                market_path, weights_path, actuals_path,
            )
        },
        "gate_status": gate["status"], "research_spec_status": "FROZEN",
        "research_result": gate["research_result"], "production_model_unchanged": True,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"gate": gate, "forecast": forecast}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Build and test MUSA geographic retail challenger V1")
    commands = result.add_subparsers(dest="command", required=True)
    fetch_parser = commands.add_parser("fetch")
    fetch_parser.add_argument("--start", type=date.fromisoformat, default=date(2019, 1, 1))
    fetch_parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    fetch_parser.add_argument("--output-dir", type=Path, default=Path("data/geo"))
    fetch_parser.add_argument("--raw-root", type=Path, default=Path("data/raw/geo"))
    eval_parser = commands.add_parser("evaluate")
    eval_parser.add_argument("--geo-dir", type=Path, default=Path("data/geo"))
    eval_parser.add_argument("--market", type=Path, default=Path("data/market.csv"))
    eval_parser.add_argument("--weights", type=Path, default=Path("data/weights.csv"))
    eval_parser.add_argument("--actuals", type=Path, default=Path("data/actuals.csv"))
    eval_parser.add_argument("--output-dir", type=Path, default=Path("data/geo_research"))
    eval_parser.add_argument("--quarter", default="2026Q3")
    eval_parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 7, 1))
    eval_parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 9, 30))
    eval_parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "fetch":
            data = fetch(args.start, args.end, args.output_dir, args.raw_root)
        else:
            data = evaluate(
                args.geo_dir, args.market, args.weights, args.actuals, args.output_dir,
                args.quarter, args.start, args.end, args.as_of,
            )
    except (GeoError, ValueError, OSError) as exc:
        parser().error(str(exc))
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
