#!/usr/bin/env python3
"""Fetch PIT ALFRED/FRED vintages for the MUSA Q2 2025 margin replay.

Requires a free FRED API key in FRED_API_KEY.

The script deliberately stores raw responses before normalization, hashes them,
and does NOT infer an intraday availability timestamp from ALFRED's date-level
real-time metadata.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.stlouisfed.org/fred/series/observations"
VINTAGE_API = "https://api.stlouisfed.org/fred/series/vintagedates"

SERIES = {
    "GASREGECW": {
        "role": "retail_east_coast",
        "title": "PADD I (East Coast District) Regular All Formulations Gas Price",
        "frequency": "weekly_ending_monday",
        "expected_latest_obs_by_cutoff": "2025-06-09",
        "alfred_url": "https://alfred.stlouisfed.org/series?seid=GASREGECW",
    },
    "GASREGMWW": {
        "role": "retail_midwest",
        "title": "PADD II (Midwest District) Regular All Formulations Gas Price",
        "frequency": "weekly_ending_monday",
        "expected_latest_obs_by_cutoff": "2025-06-09",
        "alfred_url": "https://alfred.stlouisfed.org/series?seid=GASREGMWW",
    },
    "GASREGGCW": {
        "role": "retail_gulf_coast",
        "title": "PADD III (Gulf Coast District) Regular All Formulations Gas Price",
        "frequency": "weekly_ending_monday",
        "expected_latest_obs_by_cutoff": "2025-06-09",
        "alfred_url": "https://alfred.stlouisfed.org/series?seid=GASREGGCW",
    },
    "WGASNYH": {
        "role": "wholesale_new_york_harbor",
        "title": "Conventional Gasoline Prices: New York Harbor, Regular",
        "frequency": "weekly_ending_friday",
        "expected_latest_obs_by_cutoff": "2025-06-06",
        "alfred_url": "https://alfred.stlouisfed.org/series?seid=WGASNYH",
    },
    "WGASUSGULF": {
        "role": "wholesale_us_gulf_coast",
        "title": "Conventional Gasoline Prices: U.S. Gulf Coast, Regular",
        "frequency": "weekly_ending_friday",
        "expected_latest_obs_by_cutoff": "2025-06-06",
        "alfred_url": "https://alfred.stlouisfed.org/series?seid=WGASUSGULF",
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> tuple[bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "musa-pit-research/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
        headers = {k.lower(): v for k, v in resp.headers.items()}
    return data, headers


def build_url(endpoint: str, params: dict[str, str]) -> str:
    return endpoint + "?" + urllib.parse.urlencode(params)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cutoff", default="2025-06-16")
    p.add_argument("--observation-start", default="2019-01-01")
    p.add_argument("--observation-end", default="2025-06-16")
    p.add_argument("--out", default="alfred_q2_2025_vintage")
    args = p.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("ERROR: set FRED_API_KEY to a free FRED API key.", file=sys.stderr)
        return 2

    if args.cutoff != "2025-06-16":
        p.error("This acquisition kit has June 16, 2025-specific availability ceilings")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    raw_dir = out / "raw"
    norm_dir = out / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    norm_dir.mkdir(parents=True, exist_ok=True)

    captured_at = datetime.now(timezone.utc).isoformat()
    manifest: dict = {
        "schema_version": "1.0.0",
        "research_role": "RETROSPECTIVE_PIT_VINTAGE_RECONSTRUCTION",
        "target_replay": "MUSA_Q2_2025_UNCERTAIN_QUARTER",
        "cutoff_date": args.cutoff,
        "availability_granularity": "DATE_ONLY_FROM_ALFRED_REALTIME",
        "intraday_available_at": None,
        "intraday_rule": (
            "Do not infer an intraday publication timestamp from ALFRED vintage dates. "
            "If a required release occurred on the cutoff date, separate release-time evidence is required."
        ),
        "captured_at": captured_at,
        "series": [],
    }

    violations = []

    for sid, spec in SERIES.items():
        params = {
            "series_id": sid,
            "api_key": api_key,
            "file_type": "json",
            "realtime_start": args.cutoff,
            "realtime_end": args.cutoff,
            "observation_start": args.observation_start,
            "observation_end": args.observation_end,
            "sort_order": "asc",
        }
        url = build_url(API, params)
        raw, headers = fetch(url)
        raw_path = raw_dir / f"{sid}__vintage_{args.cutoff}.json"
        raw_path.write_bytes(raw)
        digest = sha256_bytes(raw)
        payload = json.loads(raw)
        observations = payload.get("observations", [])
        if not observations or payload.get("count") != len(observations) or payload.get("offset") != 0:
            raise ValueError(f"{sid}: empty or truncated observations response")
        if payload.get("realtime_start") != args.cutoff or payload.get("realtime_end") != args.cutoff:
            raise ValueError(f"{sid}: response vintage differs from requested cutoff")

        normalized = []
        for obs in observations:
            v = obs.get("value")
            if v in (None, "."):
                continue
            normalized.append({
                "series_id": sid,
                "role": spec["role"],
                "observation_date": obs["date"],
                "value_usd_per_gallon": v,
                "realtime_start": obs.get("realtime_start"),
                "realtime_end": obs.get("realtime_end"),
                "requested_vintage_date": args.cutoff,
                "source_raw_sha256": digest,
            })

        csv_path = norm_dir / f"{sid}__vintage_{args.cutoff}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            fields = [
                "series_id", "role", "observation_date", "value_usd_per_gallon",
                "realtime_start", "realtime_end", "requested_vintage_date", "source_raw_sha256",
            ]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(normalized)

        max_obs = max((r["observation_date"] for r in normalized), default=None)
        expected_max = spec["expected_latest_obs_by_cutoff"]
        if max_obs and max_obs > expected_max:
            violations.append(
                f"{sid}: latest observation {max_obs} exceeds expected PIT ceiling {expected_max}"
            )

        # Also capture the series' published vintage-date list as provenance.
        vparams = {
            "series_id": sid,
            "api_key": api_key,
            "file_type": "json",
        }
        vurl = build_url(VINTAGE_API, vparams)
        vraw, vheaders = fetch(vurl)
        vpath = raw_dir / f"{sid}__vintage_dates.json"
        vpath.write_bytes(vraw)
        vdigest = sha256_bytes(vraw)
        vintages = json.loads(vraw).get("vintage_dates", [])

        manifest["series"].append({
            "series_id": sid,
            **spec,
            "requested_vintage_date": args.cutoff,
            "observation_window": [args.observation_start, args.observation_end],
            "latest_observation_in_snapshot": max_obs,
            "raw_path": str(raw_path),
            "raw_sha256": digest,
            "normalized_path": str(csv_path),
            "http_last_modified": headers.get("last-modified"),
            "http_etag": headers.get("etag"),
            "vintage_dates_raw_path": str(vpath),
            "vintage_dates_raw_sha256": vdigest,
            "has_cutoff_in_vintage_dates": args.cutoff in vintages,
            "source_api_url_redacted": url.replace(api_key, "<REDACTED_API_KEY>"),
        })

    manifest["validation"] = {
        "status": "FAIL" if violations else "PASS",
        "violations": violations,
        "important_note": (
            "PASS only confirms that the ALFRED snapshot does not contain observations beyond the "
            "expected calendar-date PIT ceiling. It does not by itself prove exact intraday availability."
        ),
    }

    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": manifest["validation"]["status"],
        "out": str(out),
        "manifest": str(manifest_path),
        "violations": violations,
    }, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Request URLs contain the credential; never print exception URLs or tracebacks.
        print(f"FETCH_FAILED: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1)
