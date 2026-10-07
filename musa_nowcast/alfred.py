"""Validate the Q2 2025 ALFRED acquisition kit and align its five exact series."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path


CUTOFF = "2025-06-16"
SERIES = {
    "GASREGECW": (0, "2025-06-09", "PET.EMM_EPMR_PTE_R10_DPG.W"),
    "GASREGMWW": (0, "2025-06-09", "PET.EMM_EPMR_PTE_R20_DPG.W"),
    "GASREGGCW": (0, "2025-06-09", "PET.EMM_EPMR_PTE_R30_DPG.W"),
    "WGASNYH": (4, "2025-06-06", "PET.EER_EPMRU_PF4_Y35NY_DPG.W"),
    "WGASUSGULF": (4, "2025-06-06", "PET.EER_EPMRU_PF4_RGC_DPG.W"),
}
REGIONS = {
    "East Coast": ("GASREGECW", "WGASNYH"),
    "Midwest": ("GASREGMWW", "WGASUSGULF"),
    "Gulf Coast": ("GASREGGCW", "WGASUSGULF"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_snapshot(payload: dict, sid: str, start: str) -> list[dict]:
    if payload.get("realtime_start") != CUTOFF or payload.get("realtime_end") != CUTOFF:
        raise ValueError(f"{sid}: response has wrong vintage")
    observations = payload.get("observations", [])
    if not observations or payload.get("count") != len(observations) or payload.get("offset") != 0:
        raise ValueError(f"{sid}: empty or truncated observations")
    if payload.get("units") != "lin":
        raise ValueError(f"{sid}: observations must be untransformed levels")
    weekday, ceiling, _ = SERIES[sid]
    seen = set()
    result = []
    for item in observations:
        observed = date.fromisoformat(item["date"])
        if item["date"] in seen:
            raise ValueError(f"{sid}: duplicate observation")
        seen.add(item["date"])
        if not start <= item["date"] <= ceiling or observed.weekday() != weekday:
            raise ValueError(f"{sid}: observation outside PIT window or wrong weekday")
        if item.get("realtime_start") != CUTOFF or item.get("realtime_end") != CUTOFF:
            raise ValueError(f"{sid}: observation has wrong vintage")
        if item["value"] == ".":
            continue
        value = float(item["value"])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{sid}: invalid price")
        result.append(item)
    if not result or max(row["date"] for row in result) != ceiling:
        raise ValueError(f"{sid}: snapshot does not reach independently expected latest observation")
    return result


def validate_archive(manifest_path: Path, output: Path) -> dict:
    source = json.loads(manifest_path.read_text())
    if source["cutoff_date"] != CUTOFF:
        raise ValueError("this validator is specific to the June 16, 2025 replay")
    if {item["series_id"] for item in source["series"]} != set(SERIES) or len(source["series"]) != 5:
        raise ValueError("expected the five exact production series")
    baskets = {}
    summaries = []
    for item in source["series"]:
        sid = item["series_id"]
        path = manifest_path.parent / "raw" / Path(item["raw_path"]).name
        if sha(path) != item["raw_sha256"]:
            raise ValueError(f"{sid}: raw response hash mismatch")
        vintages = manifest_path.parent / "raw" / Path(item["vintage_dates_raw_path"]).name
        if sha(vintages) != item["vintage_dates_raw_sha256"]:
            raise ValueError(f"{sid}: vintage-date provenance hash mismatch")
        rows = validate_snapshot(json.loads(path.read_text()), sid, item["observation_window"][0])
        normalized = manifest_path.parent / "normalized" / Path(item["normalized_path"]).name
        with normalized.open(newline="") as handle:
            normalized_rows = list(csv.DictReader(handle))
        expected = [(row["date"], row["value"]) for row in rows]
        if [(row["observation_date"], row["value_usd_per_gallon"]) for row in normalized_rows] != expected:
            raise ValueError(f"{sid}: normalized values do not match raw response")
        for row in normalized_rows:
            if (row["source_raw_sha256"] != item["raw_sha256"] or row["series_id"] != sid
                    or row["requested_vintage_date"] != CUTOFF):
                raise ValueError(f"{sid}: normalized provenance mismatch")
        baskets[sid] = {
            date.fromisoformat(row["date"]) - timedelta(days=date.fromisoformat(row["date"]).weekday()):
            float(row["value"]) * 100 for row in rows
        }
        summaries.append({
            "series_id": sid, "eia_series_id": SERIES[sid][2], "status": "VERIFIED_ALFRED_DATE_LEVEL_SNAPSHOT",
            "latest_observation": max(row["date"] for row in rows), "observation_count": len(rows),
            "raw_sha256": item["raw_sha256"], "normalized_sha256": sha(normalized),
            "intraday_available_at": None,
        })
    common = set.intersection(*(set(values) for values in baskets.values()))
    if not common:
        raise ValueError("no complete three-region market weeks")
    output.mkdir(parents=True, exist_ok=False)
    market = output / "market.csv"
    with market.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("week", "region", "retail_cpg", "wholesale_cpg"))
        writer.writeheader()
        for week in sorted(common):
            for region, (retail, wholesale) in sorted(REGIONS.items()):
                writer.writerow({"week": week.isoformat(), "region": region,
                                 "retail_cpg": f"{baskets[retail][week]:.4f}",
                                 "wholesale_cpg": f"{baskets[wholesale][week]:.4f}"})
    report = {
        "evaluation_role": "RETROSPECTIVE_PIT_VINTAGE_RECONSTRUCTION",
        "cutoff_date": CUTOFF, "captured_at": source["captured_at"],
        "market_vintage_status": "VERIFIED_ALFRED_DATE_LEVEL_SNAPSHOT",
        "source_manifest_sha256": sha(manifest_path), "series": summaries,
        "aligned_market_sha256": sha(market), "aligned_complete_weeks": len(common),
        "latest_complete_market_week": max(common).isoformat(),
        "retail_week_without_matching_wholesale": "2025-06-09",
        "alignment_rule": "Original retail Monday and wholesale Friday normalized to ISO Monday; complete regions only",
        "remaining_replay_blockers": [
            "PIT_GALLON_SHARE_METHODOLOGY_UNREGISTERED",
            "REMAINING_PERIOD_MARGIN_METHODOLOGY_UNREGISTERED",
            "HISTORICAL_COMPANY_TRAINING_ACTUALS_AND_WEIGHT_AVAILABILITY_REQUIRE_VERIFICATION",
        ],
        "production_forecast_same_as_of": None, "shadow_forecast": None,
        "scoring_status": "BLOCKED_NO_FROZEN_REPLAY_INPUTS",
    }
    with (output / "validation.json").open("x") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = validate_archive(args.manifest, args.output)
    print(json.dumps({"market_status": report["market_vintage_status"],
                      "latest_complete_week": report["latest_complete_market_week"],
                      "remaining_blockers": report["remaining_replay_blockers"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
