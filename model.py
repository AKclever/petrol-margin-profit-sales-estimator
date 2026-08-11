#!/usr/bin/env python3
"""Geographic weighting sensitivity for the MUSA fuel-margin estimate."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
INPUT = ROOT / "data" / "geographic_exposure.csv"
RESULTS = ROOT / "outputs" / "geographic_sensitivity.csv"
SUMMARY = ROOT / "outputs" / "geographic_uncertainty.json"

SCHEMES = {
    "store_only": (0.0, 0.0, 0.0, 0.0),
    "traffic_adjusted": (1.0, 0.0, 0.0, 0.0),
    "format_adjusted": (1.0, 1.0, 0.0, 0.0),
    "full_adjusted": (1.0, 1.0, 1.0, 1.0),
    "regional_tilt": (0.5, 0.5, 0.5, 1.5),
}


def load_exposure(path: Path = INPUT) -> list[dict[str, object]]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    numeric = ("store_count", "traffic_index", "express_share", "metro_share",
               "regional_volume_index", "state_margin_cpg")
    for row in rows:
        for field in numeric:
            row[field] = float(row[field])
        if row["store_count"] < 0:
            raise ValueError("store_count cannot be negative")
    return rows


def weight(row: dict[str, object], exponents: tuple[float, ...]) -> float:
    traffic, format_, metro, regional = exponents
    # Format and metro multipliers are deliberately modest to avoid false precision.
    return (float(row["store_count"]) * float(row["traffic_index"]) ** traffic
            * (1 + 0.12 * (float(row["express_share"]) - 0.5)) ** format_
            * (1 + 0.08 * (float(row["metro_share"]) - 0.5)) ** metro
            * float(row["regional_volume_index"]) ** regional)


def run(base_margin_cpg: float = 30.0) -> tuple[list[dict[str, object]], dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in load_exposure():
        grouped[str(row["quarter"])].append(row)

    results: list[dict[str, object]] = []
    for quarter, rows in sorted(grouped.items()):
        store_denominator = sum(float(r["store_count"]) for r in rows)
        store_reference = sum(float(r["store_count"]) * float(r["state_margin_cpg"])
                              for r in rows) / store_denominator
        for name, exponents in SCHEMES.items():
            weights = [weight(r, exponents) for r in rows]
            geographic_margin = sum(w * float(r["state_margin_cpg"])
                                    for w, r in zip(weights, rows)) / sum(weights)
            results.append({
                "quarter": quarter,
                "scheme": name,
                "weighted_state_margin_cpg": round(geographic_margin, 4),
                "final_margin_estimate_cpg": round(base_margin_cpg + geographic_margin - store_reference, 4),
            })

    scheme_final = {}
    for name in SCHEMES:
        values = [float(r["final_margin_estimate_cpg"]) for r in results if r["scheme"] == name]
        scheme_final[name] = round(sum(values) / len(values), 4)
    low, high = min(scheme_final.values()), max(scheme_final.values())
    summary = {
        "base_margin_cpg": base_margin_cpg,
        "periods": sorted(grouped),
        "final_margin_by_scheme_cpg": scheme_final,
        "geographic_weight_uncertainty_cpg": round(high - low, 4),
        "geographic_weight_range_cpg": [low, high],
        "interpretation": "Spread (maximum less minimum) across plausible geographic weighting schemes.",
    }
    return results, summary


def main() -> None:
    results, summary = run()
    RESULTS.parent.mkdir(exist_ok=True)
    with RESULTS.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=results[0])
        writer.writeheader()
        writer.writerows(results)
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
