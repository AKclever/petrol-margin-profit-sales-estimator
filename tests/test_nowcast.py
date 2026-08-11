from __future__ import annotations

import csv
from datetime import date, timedelta

import pytest

from musa_nowcast.data import DataError, load_actuals, load_market, load_weights
from musa_nowcast.model import NowcastEngine


REGIONS = {"Gulf Coast": 0.55, "Midwest": 0.30, "East Coast": 0.15}


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def dataset(tmp_path):
    weights_path = tmp_path / "weights.csv"
    market_path = tmp_path / "market.csv"
    actuals_path = tmp_path / "actuals.csv"
    write_csv(weights_path, ["region", "weight"],
              [{"region": region, "weight": weight} for region, weight in REGIONS.items()])

    market_rows, actual_rows = [], []
    starts = [date(2024, 1, 1) + timedelta(days=91 * index) for index in range(9)]
    for quarter_index, start in enumerate(starts):
        spread = 74 + quarter_index * 2.7
        for week_index in range(13):
            week = start + timedelta(days=7 * week_index)
            wholesale = 210 - week_index * (1.2 + quarter_index * 0.08)
            for region_index, region in enumerate(REGIONS):
                regional_wholesale = wholesale + region_index * 3
                market_rows.append({
                    "week": week.isoformat(), "region": region,
                    "retail_cpg": regional_wholesale + spread + week_index * 0.15,
                    "wholesale_cpg": regional_wholesale,
                })
        if quarter_index < 8:
            actual_rows.append({
                "quarter": f"Q{quarter_index + 1}", "start": start.isoformat(),
                "end": (start + timedelta(days=90)).isoformat(),
                "retail_margin_cpg": 24 + spread * 0.12,
                "supply_rin_cpg": 3 + quarter_index * 0.3,
                "gallons_million": 1100 + quarter_index * 10,
            })
    write_csv(market_path, ["week", "region", "retail_cpg", "wholesale_cpg"], market_rows)
    write_csv(actuals_path, ["quarter", "start", "end", "retail_margin_cpg",
                             "supply_rin_cpg", "gallons_million"], actual_rows)
    return market_path, weights_path, actuals_path, starts[-1]


def test_end_to_end_forecast_has_scenarios_and_backtest(dataset):
    market_path, weights_path, actuals_path, forecast_start = dataset
    engine = NowcastEngine(load_market(market_path), load_weights(weights_path),
                           load_actuals(actuals_path))
    result = engine.forecast("forecast", forecast_start, forecast_start + timedelta(days=90),
                             forecast_start + timedelta(days=84), gallons_million=1200)

    assert result.coverage > 0.9
    assert result.retail_low_cpg < result.retail_margin_cpg < result.retail_high_cpg
    assert result.supply_rin_low_cpg < result.supply_rin_high_cpg
    assert result.all_in_low_cpg < result.all_in_base_cpg < result.all_in_high_cpg
    assert result.estimated_fuel_contribution_million == pytest.approx(
        result.all_in_base_cpg * 12, abs=0.06
    )
    assert result.backtest_mae_cpg < result.baseline_mae_cpg


def test_partial_quarter_has_less_coverage_and_wider_interval(dataset):
    market_path, weights_path, actuals_path, forecast_start = dataset
    engine = NowcastEngine(load_market(market_path), load_weights(weights_path),
                           load_actuals(actuals_path))
    early = engine.forecast("forecast", forecast_start, forecast_start + timedelta(days=90),
                            forecast_start + timedelta(days=35))
    late = engine.forecast("forecast", forecast_start, forecast_start + timedelta(days=90),
                           forecast_start + timedelta(days=84))

    assert early.coverage < late.coverage
    assert early.retail_high_cpg - early.retail_low_cpg > late.retail_high_cpg - late.retail_low_cpg
    assert early.warning and "75%" in early.warning


def test_incomplete_region_week_is_excluded(dataset):
    market_path, weights_path, actuals_path, forecast_start = dataset
    rows = list(csv.DictReader(market_path.open(encoding="utf-8")))
    rows = [row for row in rows if not (row["week"] == forecast_start.isoformat()
                                        and row["region"] == "East Coast")]
    write_csv(market_path, ["week", "region", "retail_cpg", "wholesale_cpg"], rows)
    engine = NowcastEngine(load_market(market_path), load_weights(weights_path),
                           load_actuals(actuals_path))
    features = engine.features(forecast_start, forecast_start + timedelta(days=90))
    assert features.observed_weeks == 12


def test_weights_must_sum_to_one(tmp_path):
    path = tmp_path / "weights.csv"
    write_csv(path, ["region", "weight"], [
        {"region": "A", "weight": 0.6}, {"region": "B", "weight": 0.5}
    ])
    with pytest.raises(DataError, match="sum to 1.0"):
        load_weights(path)


def test_duplicate_market_observations_are_rejected(tmp_path):
    path = tmp_path / "market.csv"
    row = {"week": "2026-07-01", "region": "A", "retail_cpg": 300,
           "wholesale_cpg": 220}
    write_csv(path, list(row), [row, row])
    with pytest.raises(DataError, match="Duplicate"):
        load_market(path)


def test_forecast_rejects_invalid_assumptions(dataset):
    market_path, weights_path, actuals_path, forecast_start = dataset
    engine = NowcastEngine(load_market(market_path), load_weights(weights_path),
                           load_actuals(actuals_path))
    with pytest.raises(ValueError, match="gallons"):
        engine.forecast("forecast", forecast_start, forecast_start + timedelta(days=90),
                        forecast_start, gallons_million=-1)
    with pytest.raises(ValueError, match="as-of"):
        engine.forecast("forecast", forecast_start, forecast_start + timedelta(days=90),
                        forecast_start - timedelta(days=1))
