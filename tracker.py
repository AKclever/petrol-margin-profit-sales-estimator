#!/usr/bin/env python3
"""Auditable regional rack proxy and historical spot validation (stdlib only)."""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from datetime import date, timedelta

REQUIRED_BASIS = {"product_grade", "ethanol_spec", "tax_treatment", "geography", "observation_time", "delivery_basis"}


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def catalog(path):
    rows = read_csv(path)
    for row in rows:
        missing = [key for key in REQUIRED_BASIS if not row.get(key, "").strip()]
        if missing:
            raise ValueError(f"{row.get('series_id', '<unknown>')} missing basis: {', '.join(missing)}")
    return {row["series_id"]: row for row in rows}


def _num(row, key):
    value = row.get(key, "").strip()
    return None if value == "" else float(value)


def build(prices_path, catalog_path, output_path):
    specs = catalog(catalog_path)
    rows = read_csv(prices_path)
    parsed = []
    for row in rows:
        if row["series_id"] not in specs:
            raise ValueError(f"unregistered series: {row['series_id']}")
        row["_date"] = date.fromisoformat(row["date"])
        row["_value"] = float(row["value_usd_per_gallon"])
        parsed.append(row)
    by_region = defaultdict(list)
    for row in parsed:
        by_region[row["region"]].append(row)
    output = []
    for region, region_rows in sorted(by_region.items()):
        latest = max(r["_date"] for r in region_rows)
        window_start = latest - timedelta(days=89)
        racks = [r for r in region_rows if specs[r["series_id"]]["role"] == "rack" and specs[r["series_id"]]["reliable"].lower() == "true"]
        rack_dates = {r["_date"] for r in racks if r["_date"] >= window_start}
        expected_dates = sum(1 for offset in range(90) if (window_start + timedelta(days=offset)).weekday() < 5)
        completeness = len(rack_dates) / expected_dates
        candidates = [r for r in racks if r["_date"] == latest] if completeness >= .80 else []
        if not candidates:
            candidates = [r for r in region_rows if r["_date"] == latest and specs[r["series_id"]]["role"] == "spot_fallback"]
        for row in candidates:
            spec = specs[row["series_id"]]
            adjustments = {key: _num(row, key) for key in ("terminal_basis", "freight", "ethanol", "tax")}
            missing = []
            if spec["role"] == "spot_fallback":
                missing = [k for k in ("terminal_basis", "freight", "ethanol") if adjustments[k] is None]
            if missing:
                proxy, status = "", "withheld_missing_" + "_".join(missing)
            elif spec["role"] == "spot_fallback":
                proxy = .9 * row["_value"] + .1 * adjustments["ethanol"] + adjustments["terminal_basis"] + adjustments["freight"] + (adjustments["tax"] or 0)
                status = "spot_fallback_explanatory"
            else:
                proxy, status = row["_value"] + sum(v or 0 for v in (adjustments["freight"], adjustments["tax"])), "rack_anchor"
            output.append({"date": row["date"], "region": region, "series_id": row["series_id"], "source_role": spec["role"], "rack_90d_completeness": f"{completeness:.3f}", "proxy_usd_per_gallon": "" if proxy == "" else f"{proxy:.4f}", "terminal_basis": row.get("terminal_basis", ""), "freight": row.get("freight", ""), "ethanol": row.get("ethanol", ""), "tax": row.get("tax", ""), "status": status})
    fields = ["date", "region", "series_id", "source_role", "rack_90d_completeness", "proxy_usd_per_gallon", "terminal_basis", "freight", "ethanol", "tax", "status"]
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(output)


def solve(matrix, vector):
    a = [list(row) + [value] for row, value in zip(matrix, vector)]
    for col in range(len(vector)):
        pivot = max(range(col, len(a)), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12: raise ValueError("singular regression; series lack independent variation")
        a[col], a[pivot] = a[pivot], a[col]
        divisor = a[col][col]; a[col] = [v / divisor for v in a[col]]
        for r in range(len(a)):
            if r != col:
                factor = a[r][col]; a[r] = [x - factor*y for x, y in zip(a[r], a[col])]
    return [row[-1] for row in a]


def ols(x, y):
    p = len(x[0]); xtx = [[sum(r[i]*r[j] for r in x) for j in range(p)] for i in range(p)]
    xty = [sum(r[i]*v for r, v in zip(x, y)) for i in range(p)]
    return solve(xtx, xty)


def validation(path):
    raw = read_csv(path)
    if len(raw) < 21: raise ValueError("at least 21 level quarters are required to produce 20 changes")
    vals = [[float(r[k]) for k in ("musa_reported_margin_cpg", "gulf_coast_spot_usd_per_gallon", "nyh_spot_usd_per_gallon")] for r in raw]
    y = [vals[i][0] - vals[i-1][0] for i in range(1, len(vals))]
    x = [[1, vals[i][1] - vals[i-1][1], vals[i][2] - vals[i-1][2]] for i in range(1, len(vals))]
    beta = ols(x, y); pred = [sum(a*b for a, b in zip(r, beta)) for r in x]
    mean = sum(y)/len(y); sst = sum((v-mean)**2 for v in y); sse = sum((v-p)**2 for v,p in zip(y,pred))
    r2 = 1-sse/sst; adj = 1-(1-r2)*(len(y)-1)/(len(y)-len(beta))
    loo = []
    for i, row in enumerate(x):
        b = ols(x[:i]+x[i+1:], y[:i]+y[i+1:]); loo.append(sum(a*c for a,c in zip(row,b)))
    cv_r2 = 1-sum((v-p)**2 for v,p in zip(y,loo))/sst
    direction = sum((v >= 0) == (p >= 0) for v,p in zip(y,pred))/len(y)
    passed = len(y) >= 20 and adj >= .10 and cv_r2 > 0 and direction >= .55
    return {"n_changes": len(y), "intercept": beta[0], "gulf_beta": beta[1], "nyh_beta": beta[2], "r2": r2, "adjusted_r2": adj, "loo_cv_r2": cv_r2, "directional_accuracy": direction, "gate": "PASS" if passed else "FAIL_EXPLANATORY_ONLY"}


def main():
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build"); b.add_argument("--prices", required=True); b.add_argument("--config", required=True); b.add_argument("--output", required=True)
    v = sub.add_parser("validate-spots"); v.add_argument("--history", required=True)
    args = parser.parse_args()
    if args.command == "build": build(args.prices, args.config, args.output)
    else:
        for key, value in validation(args.history).items(): print(f"{key}: {value:.4f}" if isinstance(value, float) else f"{key}: {value}")

if __name__ == "__main__": main()
