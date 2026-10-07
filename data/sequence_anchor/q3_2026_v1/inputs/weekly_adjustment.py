"""Sequence-sensitive weekly retail adjustment challenger; not production."""
from __future__ import annotations

import argparse
import itertools
import json
import math
from datetime import date, timedelta
from pathlib import Path

import xlrd

from .daily_capture import fetch
from .data import MarketWeek, load_actuals, load_market, load_weights
from .geo import _predictions
from .mathutils import RidgeModel
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

SPEC = Path("data/weekly_adjustment_spec_v1.json")
DEMAND_URL = "https://www.eia.gov/dnav/pet/hist_xls/WGFUPUS2w.xls"
WEEK = timedelta(days=7)


class WeeklyError(ValueError):
    pass


class PositiveRidge:
    """Exact active-set search for three nonnegative standardized coefficients."""
    def fit(self, rows, targets):
        if any(len(r) != 3 for r in rows):
            raise WeeklyError("three weekly features required")
        best = None
        for size in range(4):
            for active in itertools.combinations(range(3), size):
                subrows = [[r[i] for i in active] for r in rows]
                model = RidgeModel(2).fit(subrows, targets)
                if any(c < 0 for c in model.coefficients[1:]):
                    continue
                objective = sum((y-model.predict_one(r))**2 for r,y in zip(subrows,targets))
                objective += 2*sum(c*c for c in model.coefficients[1:])
                if best is None or objective < best[0]:
                    best = (objective, active, model)
        _, self.active, self.model = best
        return self

    def predict_one(self, row):
        return self.model.predict_one([row[i] for i in self.active])

    def export(self):
        return {"active_feature_indices": self.active, "standardized_coefficients": self.model.coefficients,
                "means": self.model.means, "scales": self.model.scales,
                "constraints": "nonnegative on spread, negative squeeze and capture", "alpha": 2}


def update_states(squeeze, capture, cost_change, retail_change):
    squeeze_impulse = max(cost_change-retail_change,0) if cost_change > 0 else 0
    capture_impulse = max(retail_change-cost_change,0) if cost_change < 0 else 0
    return .5*squeeze+squeeze_impulse, .5*capture+capture_impulse


def load_demand(path):
    book = xlrd.open_workbook(str(path))
    sheet = book.sheet_by_name("Data 1")
    if sheet.cell_value(1,1) != "WGFUPUS2":
        raise WeeklyError("unexpected demand source key")
    result = {}
    for index in range(3,sheet.nrows):
        ending = xlrd.xldate_as_datetime(float(sheet.cell_value(index,0)),book.datemode).date()
        rate = float(sheet.cell_value(index,1))
        week = ending-timedelta(days=ending.weekday())
        if ending.weekday() != 4 or not math.isfinite(rate) or rate <= 0 or week in result:
            raise WeeklyError("invalid demand observation")
        result[week] = rate
    return result


def regional_path(market, region):
    rows = sorted((m for m in market if m.region == region),key=lambda m:m.week)
    if len({r.week for r in rows}) != len(rows):
        raise WeeklyError("duplicate regional week")
    result = {}
    previous = None
    cost_previous = None
    squeeze = capture = 0.0
    transitions = 0
    for row in rows:
        if previous is None or row.week-previous.week != WEEK:
            previous, cost_previous = row, None
            squeeze = capture = 0
            transitions = 0
            continue
        cost = .5*(row.wholesale_cpg+previous.wholesale_cpg)
        if cost_previous is not None:
            squeeze,capture = update_states(squeeze,capture,cost-cost_previous,row.retail_cpg-previous.retail_cpg)
            transitions += 1
            result[row.week] = {"week": row.week, "region": region, "retail_cpg": row.retail_cpg,
                                "spot_wholesale_cpg": row.wholesale_cpg, "replacement_cost_proxy_cpg": cost,
                                "squeeze_state": squeeze, "capture_state": capture,
                                "warmup_transitions": transitions,
                                "features": [row.retail_cpg-cost,-squeeze,capture], "boundary_imputed": False}
        previous, cost_previous = row,cost
    return result


def quarterly_path(market, weights, demand, start, end):
    """All calendar days represented; only a final partial-week carry is allowed."""
    first = start-timedelta(days=start.weekday())
    last = end-timedelta(days=end.weekday())
    complete = end-timedelta(days=4)
    complete -= timedelta(days=complete.weekday())
    if (end-complete).days > 10:
        raise WeeklyError("invalid complete-week boundary")
    paths = {w.region:regional_path(market,w.region) for w in weights}
    records = []
    week = first
    while week <= last:
        days = (min(end,week+timedelta(days=6))-max(start,week)).days+1
        imputed = week > complete
        source = week-WEEK if imputed else week
        if source not in demand:
            raise WeeklyError(f"missing demand at {source}")
        rate = demand[source]
        for weight in weights:
            path = paths[weight.region]
            if source not in path:
                raise WeeklyError(f"missing regional state at {source}/{weight.region}")
            row = dict(path[source])
            if week == first and row["warmup_transitions"] < 8:
                raise WeeklyError("insufficient eight-transition warmup")
            if imputed:
                cost = row["spot_wholesale_cpg"]
                squeeze,capture = update_states(row["squeeze_state"],row["capture_state"],
                                               cost-row["replacement_cost_proxy_cpg"],0)
                row.update(replacement_cost_proxy_cpg=cost,squeeze_state=squeeze,capture_state=capture,
                           features=[row["retail_cpg"]-cost,-squeeze,capture],boundary_imputed=True)
            row.update(week=str(week),days_in_quarter=days,demand_rate=rate,
                       demand_source_week=str(source),geographic_weight=weight.weight,
                       expected_volume_proxy=rate*days*weight.weight)
            records.append(row)
        week += WEEK
    total = sum(r["expected_volume_proxy"] for r in records)
    for row in records:
        row["gallon_weight_proxy"] = row["expected_volume_proxy"]/total
    aggregate = [sum(r["gallon_weight_proxy"]*r["features"][i] for r in records) for i in range(3)]
    return aggregate,records


def train(history, features):
    indexed = {a.quarter:a for a in history}
    rows,targets = [],[]
    for actual in history:
        prior = f"{actual.start.year-1}Q{actual.quarter[-1]}"
        if prior in indexed:
            rows.append([a-b for a,b in zip(features[actual.quarter],features[prior])])
            targets.append(actual.retail_margin_cpg-indexed[prior].retail_margin_cpg)
    return PositiveRidge().fit(rows,targets)


def forecast_weekly(model, baseline, prior_features, records):
    rows = []
    for r in records:
        delta = [a-b for a,b in zip(r["features"],prior_features)]
        rows.append(r | {"latent_margin_cpg": baseline+.5*model.predict_one(delta)})
    point = sum(r["gallon_weight_proxy"]*r["latent_margin_cpg"] for r in rows)
    aggregated = [sum(r["gallon_weight_proxy"]*r["features"][i] for r in rows) for i in range(3)]
    direct = baseline+.5*model.predict_one([a-b for a,b in zip(aggregated,prior_features)])
    if abs(direct-point) > 1e-9:
        raise WeeklyError("weekly allocation does not reconcile to quarter forecast")
    return point,rows


def evaluate(market_path, weights_path, actuals_path, output):
    output.mkdir(parents=True,exist_ok=False)
    raw = fetch(DEMAND_URL)
    demand_path = output/"national_demand.xls"
    with demand_path.open("xb") as handle:
        handle.write(raw)
    cutoff = now()
    save(output/"demand_capture.json", {"source_url": DEMAND_URL,"captured_at": cutoff,
                                       "available_at": cutoff,"sha256": sha(demand_path),
                                       "vintage_status": "CURRENT_CAPTURE_NOT_HISTORICAL_PIT"})
    market,weights,actuals = load_market(market_path),load_weights(weights_path),load_actuals(actuals_path)
    if any(a.quarter >= "2026Q3" for a in actuals):
        raise WeeklyError("target or future actual in training input")
    demand = load_demand(demand_path)
    history,features,excluded = [],{},[]
    warmup_ready = max(min(week for week,row in regional_path(market,w.region).items()
                          if row["warmup_transitions"] >= 8) for w in weights)
    for actual in actuals:
        first = actual.start-timedelta(days=actual.start.weekday())
        if first < warmup_ready:
            excluded.append({"quarter":actual.quarter,"reason":"initial history lacks eight-transition warmup"})
            continue
        try:
            features[actual.quarter],_ = quarterly_path(market,weights,demand,actual.start,actual.end)
            history.append(actual)
        except WeeklyError as exc:
            if "warmup" not in str(exc):
                raise
            excluded.append({"quarter":actual.quarter,"reason":str(exc)})
    predictions = {}
    for index in range(8,len(history)):
        heldout = history[index]
        prior_key = f"{heldout.start.year-1}Q{heldout.quarter[-1]}"
        training = history[:index]
        prior = next((a for a in training if a.quarter == prior_key),None)
        if prior is None:
            continue
        model = train(training,features)
        point = prior.retail_margin_cpg+.5*model.predict_one(
            [a-b for a,b in zip(features[heldout.quarter],features[prior_key])])
        predictions[heldout.quarter] = {"quarter":heldout.quarter,"actual_cpg":heldout.retail_margin_cpg,
            "prediction_cpg":point,"direction_correct": (point>prior.retail_margin_cpg)-(point<prior.retail_margin_cpg)
            == (heldout.retail_margin_cpg>prior.retail_margin_cpg)-(heldout.retail_margin_cpg<prior.retail_margin_cpg),
            "last_training_quarter": training[-1].quarter}
    champion = NowcastEngine(market,weights,actuals)
    production = {r["quarter"]:r for r in _predictions(champion)}
    common = sorted(set(predictions)&set(production))
    metrics = _metrics(production,predictions,common)
    model = train(history,features)
    quarter_features,records = quarterly_path(market,weights,demand,date(2026,7,1),date(2026,9,30))
    prior = next(a for a in history if a.quarter == "2025Q3")
    point,weekly = forecast_weekly(model,prior.retail_margin_cpg,features["2025Q3"],records)
    paired = [predictions[q] | {"production_prediction_cpg":production[q]["prediction_cpg"]} for q in common]
    save(output/"backtest.json", {"evaluation_role":"RETROSPECTIVE_CURRENT_VINTAGE_RESEARCH_NOT_PIT_VALIDATION",
                                   "metrics":metrics,"rows":paired,"excluded":excluded})
    save(output/"q3_2026_weekly.json", {"quarter":"2026Q3","weekly_regional_allocations":weekly,
                                       "gallon_basis":"NATIONAL_DEMAND_PLUS_STORE_COUNT_PROXY",
                                       "weekly_company_margins_observed":False})
    imputed_days = sum(r["days_in_quarter"] for r in weekly if r["boundary_imputed"] and r["region"] == weights[0].region)
    result = {"spec_id":"MUSA_WEEKLY_RETAIL_ADJUSTMENT_V1","evaluation_role":"Q3_2026_POST_PATH_RESEARCH_SHADOW",
        "forecast_created_at":now(),"information_cutoff":cutoff,"quarter":"2026Q3",
        "retail_margin_cpg":point,"production_same_inputs_cpg":champion.forecast("2026Q3",date(2026,7,1),date(2026,9,30),
                                                                                date.fromisoformat(cutoff[:10])).retail_margin_cpg,
        "eventual_actual_margin_cpg":None,"production_changed":False,"automatic_promotion":False,
        "historical_gate_passed":metrics["passes_pre_registered_gate"],"metrics":metrics,
        "training_quarters":len(history),"calibration":model.export(),"quarter_features":quarter_features,
        "calendar_days_represented":92,"boundary_price_and_demand_imputed_days":imputed_days,
        "weekly_state_components": {"weighted_squeeze_cpg":-quarter_features[1],"weighted_capture_cpg":quarter_features[2]},
        "limitations":json.loads(SPEC.read_text()),
        "input_hashes":{str(p):sha(p) for p in [market_path,weights_path,actuals_path,SPEC,demand_path,Path(__file__),
                                                Path("musa_nowcast/mathutils.py"),Path("musa_nowcast/model.py")]}}
    # Preserve code and input bytes alongside hashes for subsequent review.
    (output/"inputs").mkdir()
    for path in [market_path,weights_path,actuals_path,SPEC,Path(__file__),Path("musa_nowcast/mathutils.py"),
                 Path("musa_nowcast/model.py"),Path("musa_nowcast/timing.py"),Path("musa_nowcast/geo.py")]:
        with (output/"inputs"/path.name).open("xb") as handle:
            handle.write(path.read_bytes())
    save(output/"forecast.json",result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market",type=Path,default=Path("data/market.csv"))
    parser.add_argument("--weights",type=Path,default=Path("data/weights.csv"))
    parser.add_argument("--actuals",type=Path,default=Path("data/actuals.csv"))
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args(argv)
    result = evaluate(args.market,args.weights,args.actuals,args.output)
    print(json.dumps({k:result[k] for k in ["retail_margin_cpg","production_same_inputs_cpg","metrics",
                                          "boundary_price_and_demand_imputed_days","historical_gate_passed"]},indent=2))


if __name__ == "__main__":
    main()
