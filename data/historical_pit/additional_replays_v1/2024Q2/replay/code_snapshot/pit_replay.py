"""Isolated Q2 2025 research replay; never changes the strict replay or production."""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from lxml import html

from .alfred import CUTOFF, sha
from .daily_capture import fetch
from .data import MarketWeek, QuarterActual, RegionWeight, load_market
from .geo import SEC_FILINGS, STATE_PADD, extract_state_counts
from .mathutils import RidgeModel
from .model import NowcastEngine


START, DISCLOSED_END, END = date(2025, 4, 1), date(2025, 5, 31), date(2025, 6, 30)
SPEC = Path("data/historical_pit/q2_2025_rule_spec.json")
DISCLOSURE_URL = ("https://ir.corporate.murphyusa.com/investor-relations/news-releases/"
                  "press-release-details/2025/Murphy-USA-Issues-Operations-Update/default.aspx")
RELEASES_2025 = "04-09 04-16 04-23 04-30 05-07 05-14 05-21 05-29 06-04 06-11".split()
RELEASES_2024 = "04-10 04-17 04-24 05-01 05-08 05-15 05-22 05-30 06-05 06-12 06-20 06-26 07-03 07-10".split()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save(path: Path, payload: dict) -> None:
    with path.open("x") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def parse_demand(raw: bytes) -> tuple[date, float]:
    """Read the *single-week*, not four-week-average, Table 1 supplied rate."""
    rows = list(csv.reader(io.StringIO(raw.decode("cp1252"))))
    header = next(row for row in rows if row[:2] == ["STUB_1", "STUB_2"])
    ending = datetime.strptime(header[2], "%m/%d/%y").date()
    matches = [row for row in rows if len(row) > 2 and row[0].strip() == "Products Supplied"
               and re.fullmatch(r"\(\d+\)\s+Finished Motor Gasoline", row[1].strip())]
    if len(matches) != 1:
        raise ValueError("cannot identify one finished-gasoline supplied row")
    rate = float(matches[0][2].replace(",", ""))
    if ending.weekday() != 4 or not math.isfinite(rate) or rate <= 0:
        raise ValueError("invalid weekly demand observation")
    return ending, rate


def parse_company(raw: bytes) -> tuple[date, int, int, list[float]]:
    tree = html.fromstring(raw)
    dates = tree.xpath('//*[contains(@class,"evergreen-news-date-text")]')
    if len(dates) != 1:
        raise ValueError("issuer publication date is ambiguous")
    published = datetime.strptime(" ".join(dates[0].text_content().split()), "%B %d, %Y").date()
    rows = [row for row in tree.xpath("//tr") if
            "Retail fuel margin (cpg)" in " ".join(row.text_content().split())]
    if len(rows) != 1:
        raise ValueError("quarterly retail-margin row is ambiguous")
    values = []
    for cell in rows[0].xpath("./td"):
        text = " ".join(cell.text_content().split())
        if re.fullmatch(r"\d+\.\d+", text):
            values.append(float(text))
    table = rows[0].xpath("ancestor::table[1]")[0]
    table_rows = table.xpath(".//tr")
    header_rows = []
    for row in table_rows[:8]:
        header_rows.append(" ".join(" ".join(row.itertext()).split()))
        if "Key Operating Metrics" in header_rows[-1]:
            break
    header = " ".join(header_rows)
    if not re.search(r"Three Months Ended", header, re.I):
        raise ValueError("retail-margin target is not a three-month figure")
    years = re.findall(r"\b20\d\d\b", header)
    if len(years) < 2 or int(years[1]) != int(years[0]) - 1 or len(values) < 2:
        raise ValueError("cannot verify current/prior-year column order")
    months = {"March": 1, "June": 2, "September": 3, "December": 4}
    matched = [quarter for month, quarter in months.items() if month in header]
    if len(matched) != 1:
        raise ValueError("quarter-end month is ambiguous")
    return published, int(years[0]), matched[0], values[:2]


def capture_disclosure(root: Path) -> None:
    raw = fetch(DISCLOSURE_URL)
    tree = html.fromstring(raw)
    text = " ".join(tree.text_content().split())
    published = tree.xpath('//*[contains(@class,"evergreen-news-date-text")]')
    if len(published) != 1 or " ".join(published[0].text_content().split()) != "June 16, 2025":
        raise ValueError("disclosure date not verified")
    if not re.search(r"period April 1st to May 31st", text) or not re.search(r"retail margins of 29\.6 cents", text):
        raise ValueError("disclosure retail basis, period or value not verified")
    path = root / "raw" / "disclosure.html"
    with path.open("xb") as handle:
        handle.write(raw)
    save(root / "disclosure.json", {"url": DISCLOSURE_URL, "raw_file": str(path), "raw_sha256": sha(path),
                                    "available_at": CUTOFF, "captured_at": now(), "retail_margin_cpg": 29.6,
                                    "period_start": str(START), "period_end": str(DISCLOSED_END)})


def verify_sources(root: Path) -> dict:
    """Append a raw-backed verification; never rewrite the initial capture audit."""
    original = json.loads((root / "sources.json").read_text())
    sources = []
    for source in original["sources"]:
        revised = dict(source)
        path = root / source["file"]
        if not path.exists() or sha(path) != source.get("raw_sha256"):
            raise ValueError(f"missing or altered raw source: {source['file']}")
        if source["kind"] == "company_margin":
            published, year, quarter, values = parse_company(path.read_bytes())
            if published.isoformat() > CUTOFF:
                raise ValueError("post-cutoff training disclosure")
            verified = {}
            for name in source["quarters"]:
                offset = year - int(name[:4])
                if offset not in (0, 1) or int(name[-1]) != quarter:
                    raise ValueError("training target column mismatch")
                verified[name] = values[offset]
            revised.update(available_at=published.isoformat(), verified_margins=verified,
                           verification_method="EXPLICIT_QUARTER_HEADER_AND_CURRENT_PRIOR_YEAR_COLUMNS")
        else:
            ending, value = parse_demand(path.read_bytes())
            if not ending.isoformat() < source["release_date"] <= CUTOFF:
                raise ValueError("invalid archived demand release date")
            revised.update(available_at=source["release_date"], week_ending=str(ending),
                           rate_thousand_barrels_per_day=value)
        revised.update(status="VERIFIED", verified_at=now())
        # The original failed parser check remains in sources.json, not silently erased.
        revised.pop("error", None)
        sources.append(revised)
    result = {"sources": sources, "spec_sha256": original["spec_sha256"],
              "capture_manifest_sha256": sha(root / "sources.json"), "verified_at": now(),
              "information_cutoff": CUTOFF}
    save(root / "verification_v1.json", result)
    return result


def capture(root: Path) -> None:
    """Append-only raw official archives. Failed fetches cannot become evidence."""
    root.mkdir(parents=True, exist_ok=False)
    (root / "raw").mkdir()
    tasks = []
    for year, releases in [(2024, RELEASES_2024), (2025, RELEASES_2025)]:
        for month_day in releases:
            released = f"{year}-{month_day}"
            stem = released.replace("-", "_")
            url = f"https://www.eia.gov/petroleum/supply/weekly/archive/{year}/{stem}/csv/table1.csv"
            tasks.append({"kind": "demand", "url": url, "release_date": released,
                          "file": f"raw/wpsr_{released}.csv"})
    provenance = json.loads(Path("data/actuals.provenance.json").read_text())
    for index, source in enumerate(provenance["sources"]):
        quarters = [q for q in source["quarters"] if q <= "2025Q1"]
        if quarters:
            tasks.append({"kind": "company_margin", "url": source["url"], "quarters": quarters,
                          "file": f"raw/company_{index:02}.html"})

    def acquire(task):
        result = dict(task)
        try:
            raw = fetch(task["url"])
            with (root / task["file"]).open("xb") as handle:
                handle.write(raw)
            result.update(raw_sha256=sha(root / task["file"]), captured_at=now())
            if task["kind"] == "demand":
                ending, value = parse_demand(raw)
                released = date.fromisoformat(task["release_date"])
                if not ending < released <= date.fromisoformat(CUTOFF):
                    raise ValueError("demand release outside cutoff or ending after release")
                result.update(available_at=released.isoformat(), week_ending=ending.isoformat(),
                              rate_thousand_barrels_per_day=value)
            else:
                published, current_year, quarter_number, values = parse_company(raw)
                if published.isoformat() > CUTOFF:
                    raise ValueError("company release was published after cutoff")
                verified = {}
                for quarter in task["quarters"]:
                    offset = current_year - int(quarter[:4])
                    if offset not in (0, 1) or int(quarter[-1]) != quarter_number:
                        raise ValueError("quarter year does not match source table columns")
                    verified[quarter] = values[offset]
                result.update(available_at=published.isoformat(), verified_margins=verified,
                              availability_method="ISSUER_DATED_HISTORICAL_RELEASE_RETRIEVED_NOW")
            result["status"] = "VERIFIED"
        except Exception as exc:
            result.update(status="BLOCKED", error=str(exc))
        return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        sources = list(pool.map(acquire, tasks))
    save(root / "sources.json", {"captured_at": now(), "information_cutoff": CUTOFF,
                                "sources": sources, "spec_sha256": sha(SPEC)})
    print(json.dumps({"verified": sum(s["status"] == "VERIFIED" for s in sources),
                      "blocked": [{"file": s["file"], "error": s["error"]}
                                  for s in sources if s["status"] != "VERIFIED"]}))


def gallon_share(observations: dict[date, float]) -> tuple[float, list[dict]]:
    """Calendar boundaries allocate *demand*, never substitute a calendar share."""
    def friday(day):
        return day + timedelta(days=(4 - day.weekday()) % 7)

    known_current, known_prior = 0.0, 0.0
    day = START
    while day <= END:
        week = friday(day)
        if week in observations:
            known_current += observations[week]
            known_prior += observations[week - timedelta(days=364)]
        day += timedelta(days=1)
    if known_current <= 0 or known_prior <= 0:
        raise ValueError("missing observed demand for proxy growth factor")
    growth = known_current / known_prior
    days = []
    day = START
    while day <= END:
        week = friday(day)
        rate = observations.get(week)
        method = "ARCHIVED_WEEKLY_DEMAND"
        if rate is None:
            rate = observations[week - timedelta(days=364)] * growth
            method = "52_WEEK_PRIOR_SCALED"
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("invalid proxy volume")
        days.append({"day": day.isoformat(), "week_ending": week.isoformat(),
                     "demand_rate": rate, "method": method, "growth_factor": growth})
        day += timedelta(days=1)
    share = sum(row["demand_rate"] for row in days if row["day"] <= DISCLOSED_END.isoformat()) / sum(
        row["demand_rate"] for row in days)
    if not 0 < share < 1:
        raise ValueError("gallon share outside (0,1)")
    return share, days


def predict(source_root: Path, output: Path) -> dict:
    """No outcome is read by this step. Block on incomplete or altered evidence."""
    output.mkdir(parents=True, exist_ok=False)
    spec = json.loads(SPEC.read_text())
    manifest = json.loads((source_root / "verification_v1.json").read_text())
    result = {"evaluation_role": spec["evaluation_role"], "methodology_origin": spec["methodology_origin"],
              "forecast_created_at": now(), "remaining_forecast_created_at": now(),
              "remaining_forecast_information_cutoff": CUTOFF,
              "disclosure_period_end": DISCLOSED_END.isoformat(), "disclosure_available_at": CUTOFF,
              "remaining_period_start": "2025-06-01", "remaining_period_end": END.isoformat(),
              "gallon_share_evidence_type": "PIT_MODELLED_GALLON_SHARE",
              "gallon_share_method": spec["gallon_share_method"],
              "remaining_margin_method": spec["remaining_margin_method"],
              "eventual_actual_margin": None, "shadow_abs_error": None, "production_abs_error": None,
              "incremental_abs_error_improvement": None,
              "shadow_forecast": None, "production_forecast_same_as_of": None,
              "strict_replay_status": "BLOCKED_MISSING_OBSERVED_COMPANY_GALLONS",
              "limitations": spec["remaining_margin_rules"][4], "input_hashes": {}}
    try:
        if manifest["spec_sha256"] != sha(SPEC):
            raise ValueError("rule specification changed after source capture")
        if manifest["capture_manifest_sha256"] != sha(source_root / "sources.json"):
            raise ValueError("original source capture manifest changed")
        verified, demand = {}, {}
        for source in manifest["sources"]:
            if source["status"] != "VERIFIED":
                raise ValueError(f"unverified source {source['file']}: {source.get('error')}")
            path = source_root / source["file"]
            if sha(path) != source["raw_sha256"] or source["available_at"] > CUTOFF:
                raise ValueError("raw source changed or is unavailable at cutoff")
            result["input_hashes"][str(path)] = sha(path)
            if source["kind"] == "company_margin":
                published, year, quarter_number, values = parse_company(path.read_bytes())
                for quarter in source["quarters"]:
                    if int(quarter[-1]) != quarter_number or year-int(quarter[:4]) not in (0, 1):
                        raise ValueError("training quarter mismatches source columns")
                    value = values[year - int(quarter[:4])]
                    if source["verified_margins"][quarter] != value or published.isoformat() != source["available_at"]:
                        raise ValueError("normalized company evidence differs from raw source")
                    verified[quarter] = value
            else:
                ending, value = parse_demand(path.read_bytes())
                if ending.isoformat() != source["week_ending"] or value != source["rate_thousand_barrels_per_day"]:
                    raise ValueError("normalized demand differs from raw source")
                demand[ending] = value
        disclosure_path = source_root / "disclosure.json"
        disclosure = json.loads(disclosure_path.read_text())
        if disclosure["available_at"] != CUTOFF or sha(Path(disclosure["raw_file"])) != disclosure["raw_sha256"]:
            raise ValueError("disclosure provenance changed")
        if (disclosure["retail_margin_cpg"] != 29.6 or disclosure["period_start"] != str(START)
                or disclosure["period_end"] != str(DISCLOSED_END)):
            raise ValueError("disclosure target or period mismatch")
        result["input_hashes"][str(disclosure_path)] = sha(disclosure_path)
        result["input_hashes"][disclosure["raw_file"]] = disclosure["raw_sha256"]
        # Do not load final quarter company gallons, supply/RINs or outcome into the model.
        actuals = []
        with Path("data/actuals.csv").open() as handle:
            for row in csv.DictReader(handle):
                if row["quarter"] > "2025Q1":
                    continue
                margin = float(row["retail_margin_cpg"])
                if verified.get(row["quarter"]) != margin:
                    raise ValueError(f"training margin not verified: {row['quarter']}")
                actuals.append(QuarterActual(row["quarter"], date.fromisoformat(row["start"]),
                                            date.fromisoformat(row["end"]), margin))
        if len(actuals) != 25 or len({a.quarter for a in actuals}) != 25:
            raise ValueError("training set must contain the 25 verified quarters 2019Q1-2025Q1")
        filing = next(f for f in SEC_FILINGS if f.report_year == 2024)
        raw_weights = Path("data/raw/geo/2026-09-27T202037Z/sec/2024-musa-20241231.htm")
        counts, total = extract_state_counts(raw_weights.read_bytes())
        expected_hashes = {row["raw_sha256"] for row in csv.DictReader(Path("data/geo/state_store_counts.csv").open())
                           if row["report_date"] == "2024-12-31" and row["available_at"] <= CUTOFF}
        if expected_hashes != {sha(raw_weights)} or filing.filed_at.isoformat() > CUTOFF:
            raise ValueError("historical weights raw hash or filing availability unverified")
        regions = {"PADD1B": "East Coast", "PADD1C": "East Coast", "PADD2": "Midwest", "PADD3": "Gulf Coast"}
        regional = {region: sum(n for state, n in counts.items() if regions.get(STATE_PADD[state]) == region)
                    for region in set(regions.values())}
        covered = sum(regional.values())
        weights = [RegionWeight(region, n / covered) for region, n in sorted(regional.items())]
        market_path = Path("data/historical_pit/2025Q2/2025-06-16/market.csv")
        validation = json.loads(market_path.with_name("validation.json").read_text())
        if sha(market_path) != validation["aligned_market_sha256"]:
            raise ValueError("ALFRED normalized market hash mismatch")
        market = load_market(market_path)
        if max(m.week for m in market) != date(2025, 6, 2):
            raise ValueError("market contains post-cutoff complete weeks")
        engine = NowcastEngine(market, weights, actuals)
        rows, targets = engine._training()
        changes, target_changes = engine._change_training(rows, targets, len(rows))
        ridge = RidgeModel(alpha=2).fit(changes, target_changes)
        prior = next(a for a in actuals if a.quarter == "2024Q2")
        quarter_features = engine.features(START, END, date.fromisoformat(CUTOFF))
        production = prior.retail_margin_cpg + .5 * ridge.predict_one(engine._changes(
            quarter_features.model_values(), engine.features(prior.start, prior.end).model_values()))
        last_week = max(m.week for m in market)
        projected = list(market)
        for region in engine.weights:
            latest = next(m for m in market if m.week == last_week and m.region == region)
            week = last_week + timedelta(days=7)
            while week <= END:
                projected.append(MarketWeek(week, region, latest.retail_cpg, latest.wholesale_cpg))
                week += timedelta(days=7)
        projected_engine = NowcastEngine(projected, weights, actuals)
        june = projected_engine.features(date(2025, 6, 1), END)
        previous_june = engine.features(date(2024, 6, 1), date(2024, 6, 30))
        remaining = prior.retail_margin_cpg + .5 * ridge.predict_one(engine._changes(
            june.model_values(), previous_june.model_values()))
        share, days = gallon_share(demand)
        save(output / "gallon_proxy_days.json", {"days": days, "observed_gallon_share": share,
                                               "remaining_gallon_share": 1 - share})
        # Save actual training records, weights and coefficients, not merely a claim of verification.
        save(output / "training.json", {"actuals": [vars(a) | {"start": a.start.isoformat(), "end": a.end.isoformat()}
                                                   for a in actuals], "feature_rows": rows,
                                         "change_feature_rows": changes, "target_changes": target_changes,
                                         "ridge_coefficients": ridge.coefficients, "means": ridge.means,
                                         "scales": ridge.scales, "weights": [vars(w) for w in weights],
                                         "weights_source": filing.url, "weights_available_at": str(filing.filed_at),
                                         "store_counts": counts, "covered_stores": covered, "reported_stores": total,
                                         "quarter_features": quarter_features.model_values(),
                                         "remaining_features": june.model_values(),
                                         "prior_june_features": previous_june.model_values()})
        for path in [SPEC, market_path, market_path.with_name("validation.json"), raw_weights,
                     source_root / "sources.json", source_root / "verification_v1.json",
                     output / "training.json", output / "gallon_proxy_days.json",
                     Path(__file__), Path("musa_nowcast/model.py"), Path("musa_nowcast/mathutils.py")]:
            result["input_hashes"][str(path)] = sha(path)
        result.update(status="FROZEN_UNSCORED_RESEARCH_REPLAY", observed_gallon_share=share,
                      remaining_gallon_share=1-share, remaining_margin_forecast=remaining,
                      disclosed_margin_cpg=29.6, shadow_forecast=share * 29.6 + (1-share) * remaining,
                      production_forecast_same_as_of=production, training_quarters=len(actuals),
                      production_comparator="PRODUCTION_FORMULA_WITH_PIT_2024_STORE_WEIGHTS",
                      scoring_status="AWAITING_SEPARATE_OUTCOME_STEP")
    except (ValueError, KeyError, OSError) as exc:
        result.update(status="BLOCKED_PIT_EVIDENCE_INSUFFICIENT", block_reason=str(exc))
    save(output / "forecast.json", result)
    return result


def score(forecast_path: Path, output: Path) -> dict:
    """Freeze exists before outcome retrieval; append score without rewriting inputs."""
    frozen = json.loads(forecast_path.read_text())
    if frozen["status"] != "FROZEN_UNSCORED_RESEARCH_REPLAY":
        raise ValueError("blocked replay cannot be scored")
    for path, digest in frozen["input_hashes"].items():
        if sha(Path(path)) != digest:
            raise ValueError(f"frozen input changed before scoring: {path}")
    output.mkdir(parents=True, exist_ok=False)
    url = ("https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/"
           "2025/Murphy-USA-Inc--Reports-Second-Quarter-2025-Results/default.aspx")
    raw = fetch(url)
    published, year, quarter_number, values = parse_company(raw)
    if (year, quarter_number) != (2025, 2) or published.isoformat() != "2025-07-30":
        raise ValueError("outcome source quarter or publication date not verified")
    with (output / "outcome.html").open("xb") as handle:
        handle.write(raw)
    actual = values[0]
    shadow_error = abs(actual-frozen["shadow_forecast"])
    production_error = abs(actual-frozen["production_forecast_same_as_of"])
    result = {"evaluation_role": frozen["evaluation_role"], "methodology_origin": frozen["methodology_origin"],
              "quarter": "2025Q2", "status": "SCORED_RESEARCH_REPLAY_NOT_VALIDATION", "scored_at": now(),
              "frozen_forecast_sha256": sha(forecast_path), "outcome_sha256": sha(output / "outcome.html"),
              "actual_source_url": url, "actual_available_at": published.isoformat(), "actual_margin_cpg": actual,
              "shadow_forecast": frozen["shadow_forecast"],
              "production_forecast_same_as_of": frozen["production_forecast_same_as_of"],
              "shadow_abs_error": shadow_error, "production_abs_error": production_error,
              "incremental_abs_error_improvement": production_error-shadow_error,
              "prospective_validation": False, "strict_replay_unchanged": True}
    save(output / "score.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["capture", "capture-disclosure", "verify", "predict", "score"])
    parser.add_argument("--sources", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--forecast", type=Path)
    args = parser.parse_args(argv)
    if args.action in ("capture", "capture-disclosure", "verify", "predict") and args.sources is None:
        parser.error("this action requires --sources")
    if args.action == "capture":
        capture(args.sources)
    elif args.action == "capture-disclosure":
        capture_disclosure(args.sources)
    elif args.action == "verify":
        result = verify_sources(args.sources)
        print(json.dumps({"verified_sources": len(result["sources"])}))
    elif args.action == "score":
        if args.forecast is None or args.output is None:
            parser.error("score requires --forecast and --output")
        print(json.dumps(score(args.forecast, args.output), indent=2))
    else:
        if args.output is None:
            parser.error("predict requires --output")
        print(json.dumps(predict(args.sources, args.output), indent=2))


if __name__ == "__main__":
    main()
