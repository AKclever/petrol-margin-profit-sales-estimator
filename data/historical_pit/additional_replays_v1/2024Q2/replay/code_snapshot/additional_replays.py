"""Fixed-rule additional research replays and a separately labelled early live shadow."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from lxml import html

from .alfred import REGIONS, sha
from .daily_capture import fetch
from .data import MarketWeek, QuarterActual, RegionWeight, load_actuals, load_market, load_weights
from .geo import SEC_FILINGS, STATE_PADD, extract_state_counts
from .mathutils import RidgeModel
from .model import NowcastEngine
from .pit_replay import now, parse_company, parse_demand, save

SPEC = Path("data/historical_pit/additional_replay_spec_v1.json")
BASE = Path("data/historical_pit/2025Q2/2025-06-16/replay_sources_v1")


def bounds(quarter):
    year, number = int(quarter[:4]), int(quarter[-1])
    start = date(year, 3*number-2, 1)
    next_start = date(year+1, 1, 1) if number == 4 else date(year, 3*number+1, 1)
    return start, next_start-timedelta(days=1)


def capture(root: Path):
    root.mkdir(parents=True, exist_ok=False)
    spec = json.loads(SPEC.read_text())
    index_url = "https://www.eia.gov/petroleum/supply/weekly/archive/"
    index = fetch(index_url)
    with (root / "wpsr_index.html").open("xb") as handle:
        handle.write(index)
    release_dates = sorted(set(re.findall(r"/archive/\d{4}/(\d{4}_\d\d_\d\d)/",
                                         index.decode("utf-8", errors="replace"))))
    for case in spec["cases"]:
        directory = root / case["quarter"]
        directory.mkdir()
        cutoff = date.fromisoformat(case["cutoff"])
        start, end = bounds(case["quarter"])
        raw_pdf = fetch(case["source_url"])
        pdf = directory / "disclosure.pdf"
        with pdf.open("xb") as handle:
            handle.write(raw_pdf)
        text = subprocess.check_output(["pdftotext", "-layout", str(pdf), "-"], text=True)
        normalized = " ".join(text.split())
        if case["required_text"] not in normalized:
            raise ValueError(f"disclosure statement not verified: {case['quarter']}")
        event_date = cutoff.strftime("%b %d, %Y").upper()
        if event_date not in normalized.upper():
            raise ValueError("transcript event date does not match cutoff")
        with (directory / "disclosure.txt").open("x") as handle:
            handle.write(text)
        manifest = {"case": case, "captured_at": now(), "spec_sha256": sha(SPEC),
                    "disclosure_sha256": sha(pdf), "disclosure_text_sha256": sha(directory / "disclosure.txt"),
                    "availability_method": "DATE_LEVEL_PUBLIC_CALL_EVENT_NOT_TRANSCRIPT_UPLOAD_DATE",
                    "intraday_available_at": None, "demand": [], "market": []}
        # Original archives, not current revised demand workbooks.
        tasks = []
        prior_start, prior_end = start-timedelta(days=364), end-timedelta(days=364)
        for stem in release_dates:
            released = date.fromisoformat(stem.replace("_", "-"))
            if released <= cutoff and (prior_start <= released <= prior_end+timedelta(days=14)
                                       or start <= released <= cutoff):
                url = f"https://www.eia.gov/petroleum/supply/weekly/archive/{released.year}/{stem}/csv/table1.csv"
                tasks.append((released, url))

        def demand_source(task):
            released, url = task
            path = directory / f"demand_{released}.csv"
            raw = fetch(url)
            ending, rate = parse_demand(raw)
            if not ending < released:
                raise ValueError("weekly demand publication must follow its observation end")
            with path.open("xb") as handle:
                handle.write(raw)
            return {"file": str(path), "sha256": sha(path), "url": url,
                    "available_at": str(released), "observed_at": str(ending), "rate": rate}
        with ThreadPoolExecutor(max_workers=4) as pool:
            manifest["demand"] = list(pool.map(demand_source, tasks))
        key = os.environ.get("FRED_API_KEY")
        if not key:
            raise ValueError("FRED_API_KEY is required in process environment, never saved")
        for sid in sorted({s for pair in REGIONS.values() for s in pair}):
            params = {"series_id": sid, "realtime_start": str(cutoff), "realtime_end": str(cutoff),
                      "observation_start": "2019-01-01", "observation_end": str(cutoff),
                      "file_type": "json", "limit": 100000}
            url = "https://api.stlouisfed.org/fred/series/observations?"+urllib.parse.urlencode(params | {"api_key": key})
            try:
                with urllib.request.urlopen(url, timeout=60) as response:
                    raw = response.read()
            except Exception:
                raise RuntimeError(f"ALFRED request failed for {sid}; credential URL suppressed") from None
            path = directory / f"{sid}.json"
            with path.open("xb") as handle:
                handle.write(raw)
            manifest["market"].append({"series_id": sid, "file": str(path), "sha256": sha(path),
                                       "endpoint": "https://api.stlouisfed.org/fred/series/observations",
                                       "parameters": params})
        save(directory / "capture.json", manifest)
        print(json.dumps({"quarter": case["quarter"], "captured_sources": len(tasks)+6}), flush=True)


def market_snapshot(manifest):
    cutoff = manifest["case"]["cutoff"]
    baskets = {}
    for source in manifest["market"]:
        path = Path(source["file"])
        if sha(path) != source["sha256"]:
            raise ValueError("raw market hash mismatch")
        payload = json.loads(path.read_text())
        rows = payload.get("observations", [])
        if (payload.get("realtime_start") != cutoff or payload.get("realtime_end") != cutoff
                or payload.get("count") != len(rows) or payload.get("offset") != 0
                or payload.get("units") != "lin" or not rows):
            raise ValueError("empty, incomplete or wrong-vintage ALFRED snapshot")
        sid = source["series_id"]
        weekday = 0 if sid.startswith("GAS") else 4
        basket = {}
        for row in rows:
            observed = date.fromisoformat(row["date"])
            if (row["date"] > cutoff or observed.weekday() != weekday
                    or row["realtime_start"] != cutoff or row["realtime_end"] != cutoff):
                raise ValueError("observation outside historical snapshot")
            if row["value"] == ".":
                continue
            value = float(row["value"])*100
            if not 0 < value < float("inf") or observed in basket:
                raise ValueError("invalid or duplicate price")
            basket[observed-timedelta(days=observed.weekday())] = value
        baskets[sid] = basket
    common = set.intersection(*(set(b) for b in baskets.values()))
    if len(baskets) != 5 or not common:
        raise ValueError("missing required market series")
    return [MarketWeek(week, region, baskets[retail][week], baskets[wholesale][week])
            for week in sorted(common) for region, (retail, wholesale) in sorted(REGIONS.items())]


def training(case, directory):
    original = json.loads((BASE / "verification_v1.json").read_text())
    cutoff, quarter = case["cutoff"], case["quarter"]
    verified, sources = {}, {}
    for source in original["sources"]:
        if source["kind"] != "company_margin" or source["available_at"] > cutoff:
            continue
        path = BASE / source["file"]
        if sha(path) != source["raw_sha256"]:
            raise ValueError("company source hash mismatch")
        published, year, number, values = parse_company(path.read_bytes())
        if str(published) != source["available_at"]:
            raise ValueError("company publication mismatch")
        for q, value in source["verified_margins"].items():
            if q < quarter and int(q[-1]) == number and values[year-int(q[:4])] == value:
                verified[q] = value
                sources[str(path)] = sha(path)
    # Current provenance's 2023Q4 comparative is too late for May2024: retrieve its original release.
    if quarter > "2023Q4" and "2023Q4" not in verified:
        path = directory / "original_2023Q4.html"
        url = ("https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/"
               "2024/Murphy-USA-Inc.-Reports-Preliminary-Fourth-Quarter-2023-Results/default.aspx")
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(fetch(url))
        published, year, number, values = parse_company(path.read_bytes())
        if str(published) > cutoff or (year, number) != (2023, 4):
            raise ValueError("2023Q4 training source not eligible")
        verified["2023Q4"] = values[0]
        sources[str(path)] = sha(path)
    actuals = []
    with Path("data/actuals.csv").open() as handle:
        for row in csv.DictReader(handle):
            if row["quarter"] >= quarter:
                continue
            value = float(row["retail_margin_cpg"])
            if verified.get(row["quarter"]) != value:
                raise ValueError("unverified historical training target: "+row["quarter"])
            actuals.append(QuarterActual(row["quarter"], date.fromisoformat(row["start"]),
                                        date.fromisoformat(row["end"]), value))
    filing = max((f for f in SEC_FILINGS if str(f.filed_at) <= cutoff), key=lambda f: f.filed_at)
    path = Path("data/raw/geo/2026-09-27T202037Z/sec") / f"{filing.report_year}-{filing.document}"
    counts, total = extract_state_counts(path.read_bytes())
    with Path("data/geo/state_store_counts.csv").open() as handle:
        expected = {r["raw_sha256"] for r in csv.DictReader(handle)
                    if r["report_date"] == f"{filing.report_year}-12-31" and r["available_at"] <= cutoff}
    if expected != {sha(path)}:
        raise ValueError("PIT store weights hash not verified")
    mapping = {"PADD1B": "East Coast", "PADD1C": "East Coast", "PADD2": "Midwest", "PADD3": "Gulf Coast"}
    regional = {r: sum(v for state, v in counts.items() if mapping.get(STATE_PADD[state]) == r)
                for r in set(mapping.values())}
    weights = [RegionWeight(r, v/sum(regional.values())) for r,v in sorted(regional.items())]
    sources[str(path)] = sha(path)
    return actuals, weights, sources, {"weights_available_at": str(filing.filed_at),
                                      "weights_source": filing.url, "covered_stores": sum(regional.values()),
                                      "reported_stores": total}


def proxy_share(start, period_end, end, demand):
    days = [start+timedelta(days=n) for n in range((end-start).days+1)]
    weeks = {d: d+timedelta(days=(4-d.weekday())%7) for d in days}
    known = [d for d in days if weeks[d] in demand]
    growth = sum(demand[weeks[d]] for d in known)/sum(demand[weeks[d]-timedelta(days=364)] for d in known)
    rates = {d: demand[weeks[d]] if weeks[d] in demand else demand[weeks[d]-timedelta(days=364)]*growth
             for d in days}
    if any(not 0 < v < float("inf") for v in rates.values()):
        raise ValueError("invalid demand proxy")
    share = sum(v for d,v in rates.items() if d <= period_end)/sum(rates.values())
    return share, {str(d): {"expected_daily_rate": v, "source_week": str(weeks[d]),
                           "projected": weeks[d] not in demand} for d,v in rates.items()}


def fit(engine):
    rows, targets = engine._training()
    changes, target_changes = engine._change_training(rows, targets, len(rows))
    return RidgeModel(2).fit(changes, target_changes)


def persist(market, end):
    last = max(m.week for m in market)
    projected = list(market)
    for m in [m for m in market if m.week == last]:
        week = last+timedelta(days=7)
        while week <= end:
            projected.append(MarketWeek(week, m.region, m.retail_cpg, m.wholesale_cpg))
            week += timedelta(days=7)
    return projected


def predict(root, case):
    directory = root/case["quarter"]
    output = directory/"replay"
    output.mkdir(exist_ok=False)
    hashes = {str(SPEC): sha(SPEC)}
    result = {"quarter": case["quarter"], "evaluation_role": "RETROSPECTIVE_MECHANICAL_REPLAY",
              "methodology_origin": "RETROSPECTIVE_PIT_RULE_REPLAY", "forecast_created_at": now(),
              "information_cutoff": case["cutoff"], "disclosure_precision": case["precision"],
              "gallon_share_evidence_type": "PIT_MODELLED_GALLON_SHARE", "actual_margin_cpg": None,
              "shadow_forecast": None, "production_forecast_same_as_of": None,
              "disclosure_period_start": case["period_start"], "disclosure_period_end": case["period_end"],
              "disclosure_available_at": case["cutoff"], "remaining_forecast_created_at": now(),
              "remaining_forecast_information_cutoff": case["cutoff"],
              "limitations": ["National-demand gallons proxy, not company-observed volumes",
                              "Approximate management number, not exact audited monthly actual",
                              "Unvalidated quarterly-to-shorter-period coefficient and anchor transfer",
                              "Known outcomes and retrospectively specified rules; not blind validation"]}
    try:
        manifest = json.loads((directory/"capture.json").read_text())
        if manifest["spec_sha256"] != sha(SPEC) or manifest["case"] != case:
            raise ValueError("specification or case changed after acquisition")
        for suffix, expected in [("disclosure.pdf", manifest["disclosure_sha256"]),
                                 ("disclosure.txt", manifest["disclosure_text_sha256"])]:
            p = directory/suffix
            if sha(p) != expected:
                raise ValueError("disclosure raw evidence changed")
            hashes[str(p)] = expected
        hashes[str(directory/"capture.json")] = sha(directory/"capture.json")
        market = market_snapshot(manifest)
        demand = {}
        for source in manifest["demand"]:
            p = Path(source["file"])
            if sha(p) != source["sha256"] or source["available_at"] > case["cutoff"]:
                raise ValueError("demand source changed or arrived too late")
            ending, rate = parse_demand(p.read_bytes())
            demand[ending] = rate
            hashes[str(p)] = sha(p)
        for source in manifest["market"]:
            hashes[source["file"]] = source["sha256"]
        actuals, weights, company_hashes, meta = training(case, directory)
        hashes.update(company_hashes)
        engine = NowcastEngine(market, weights, actuals)
        ridge = fit(engine)
        start, end = bounds(case["quarter"])
        prior = next(a for a in actuals if a.quarter == f"{start.year-1}Q{case['quarter'][-1]}")
        baseline = prior.retail_margin_cpg
        current = engine.features(start, end, date.fromisoformat(case["cutoff"])).model_values()
        production = baseline+.5*ridge.predict_one(engine._changes(current, engine.features(prior.start, prior.end).model_values()))
        observed_end = date.fromisoformat(case["period_end"])
        remaining_start = observed_end+timedelta(days=1)
        projected_engine = NowcastEngine(persist(market, end), weights, actuals)
        rem_features = projected_engine.features(remaining_start, end).model_values()
        prior_rem = engine.features(remaining_start.replace(year=remaining_start.year-1),
                                    end.replace(year=end.year-1)).model_values()
        remaining = baseline+.5*ridge.predict_one(engine._changes(rem_features, prior_rem))
        share, days = proxy_share(start, observed_end, end, demand)
        save(output/"inputs.json", {"proxy_days": days, "weights": [vars(w) for w in weights],
                                   "training_actuals": [{"quarter": a.quarter, "retail_margin_cpg": a.retail_margin_cpg} for a in actuals],
                                   "ridge_coefficients": ridge.coefficients, "means": ridge.means, "scales": ridge.scales,
                                   "remaining_features": rem_features, "prior_remaining_features": prior_rem, **meta})
        for p in [output/"inputs.json", Path(__file__), Path("musa_nowcast/model.py"),
                  Path("musa_nowcast/mathutils.py"), Path("musa_nowcast/pit_replay.py"), Path("musa_nowcast/geo.py")]:
            hashes[str(p)] = sha(p)
        result.update(status="FROZEN_UNSCORED_RESEARCH_REPLAY", observed_gallon_share=share,
                      remaining_gallon_share=1-share, remaining_period_start=str(remaining_start), remaining_period_end=str(end),
                      remaining_margin_forecast=remaining, production_forecast_same_as_of=production,
                      shadow_forecast=share*case["disclosed_margin_cpg"]+(1-share)*remaining,
                      training_quarters=len(actuals), latest_complete_market_week=str(max(m.week for m in market)),
                      production_comparator="PRODUCTION_FORMULA_WITH_LATEST_ELIGIBLE_STORE_WEIGHTS")
    except (ValueError, KeyError, OSError, ZeroDivisionError) as exc:
        result.update(status="BLOCKED_PIT_EVIDENCE_INSUFFICIENT", reason=str(exc))
    result["input_hashes"] = hashes
    save(output/"forecast.json", result)
    return result


def score(root, case):
    forecast = root/case["quarter"]/"replay"/"forecast.json"
    frozen = json.loads(forecast.read_text())
    if frozen["status"] != "FROZEN_UNSCORED_RESEARCH_REPLAY":
        return {"quarter": case["quarter"], "status": "BLOCKED_NOT_SCORED"}
    if any(sha(Path(p)) != h for p,h in frozen["input_hashes"].items()):
        raise ValueError("frozen input changed")
    # Outcome parsing starts only here, after every replay is frozen.
    actual = next(a.retail_margin_cpg for a in load_actuals("data/actuals.csv") if a.quarter == case["quarter"])
    provenance = json.loads(Path("data/actuals.provenance.json").read_text())
    source = next(s for s in provenance["sources"] if case["quarter"] in s["quarters"])
    raw = fetch(source["url"])
    published, year, number, values = parse_company(raw)
    if values[year-int(case["quarter"][:4])] != actual or number != int(case["quarter"][-1]) or str(published) <= case["cutoff"]:
        raise ValueError("scoring outcome source not verified")
    output = forecast.parent/"scoring"
    output.mkdir(exist_ok=False)
    with (output/"outcome.html").open("xb") as handle:
        handle.write(raw)
    shadow_error, production_error = abs(actual-frozen["shadow_forecast"]), abs(actual-frozen["production_forecast_same_as_of"])
    result = {"quarter": case["quarter"], "evaluation_role": frozen["evaluation_role"],
              "status": "SCORED_APPROXIMATE_RESEARCH_REPLAY_NOT_VALIDATION", "scored_at": now(),
              "actual_margin_cpg": actual, "actual_source_url": source["url"], "actual_available_at": str(published),
              "outcome_sha256": sha(output/"outcome.html"), "frozen_forecast_sha256": sha(forecast),
              "shadow_forecast": frozen["shadow_forecast"], "production_forecast_same_as_of": frozen["production_forecast_same_as_of"],
              "shadow_abs_error": shadow_error, "production_abs_error": production_error,
              "incremental_abs_error_improvement": production_error-shadow_error, "prospective_validation": False}
    save(output/"score.json", result)
    return result


def live(manifest_path, output):
    manifest = json.loads(manifest_path.read_text())
    path = manifest_path.parent/manifest["market_file"]
    if sha(path) != manifest["market_sha256"]:
        raise ValueError("live market hash mismatch")
    market, actuals, weights = load_market(path), load_actuals("data/actuals.csv"), load_weights("data/weights.csv")
    engine = NowcastEngine(market, weights, actuals)
    start, end = bounds("2026Q4")
    ridge = fit(engine)
    prior = next(a for a in actuals if a.quarter == "2025Q4")
    projected = NowcastEngine(persist(market, end), weights, actuals)
    change = ridge.predict_one(engine._changes(projected.features(start,end).model_values(),
                                               engine.features(prior.start,prior.end).model_values()))
    shadow = prior.retail_margin_cpg+.5*change
    result = {"quarter": "2026Q4", "evaluation_role": "LIVE_RESEARCH_SHADOW_NOT_PRODUCTION",
              "information_cutoff": manifest["information_cutoff"], "forecast_created_at": now(),
              "production_status": "BLOCKED_NO_COMPLETE_Q4_MARKET_WEEK", "production_forecast": None,
              "seasonal_reference_cpg": prior.retail_margin_cpg, "flat_price_shadow_cpg": shadow,
              "observed_complete_quarter_weeks": len(engine._weekly_basket(start,end)),
              "latest_complete_market_week": str(max(m.week for m in market)),
              "partial_quarter_company_shadow": None, "actual_margin_cpg": None,
              "assumption": "All quarter paired regional prices persist at the last available complete pre-quarter week; no company disclosure anchor.",
              "latest_completed_quarter_nowcast": engine.forecast("2026Q3", *bounds("2026Q3"),
                                                                 date.fromisoformat(manifest["information_cutoff"][:10])).as_dict(),
              "input_hashes": {str(p): sha(p) for p in [manifest_path,path,SPEC,Path("data/weights.csv"),
                                                        Path("data/actuals.csv"),Path(__file__)]}}
    output.mkdir(parents=True, exist_ok=False)
    save(output/"forecast.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["capture", "predict", "score", "live"])
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    if args.action == "capture":
        capture(args.root)
    elif args.action == "live":
        if not args.manifest:
            parser.error("live requires --manifest")
        print(json.dumps(live(args.manifest,args.root), indent=2))
    else:
        spec = json.loads(SPEC.read_text())
        for case in spec["cases"]:
            print(json.dumps(predict(args.root,case) if args.action == "predict" else score(args.root,case), indent=2))


if __name__ == "__main__":
    main()
