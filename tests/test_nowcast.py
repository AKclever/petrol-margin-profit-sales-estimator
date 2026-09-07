from __future__ import annotations

import csv
from dataclasses import replace
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


def quarter_start(index):
    year, offset = 2021 + index // 4, index % 4
    return date(year, 1 + offset * 3, 1)


@pytest.fixture
def dataset(tmp_path):
    weights_path = tmp_path / "weights.csv"
    market_path = tmp_path / "market.csv"
    actuals_path = tmp_path / "actuals.csv"
    write_csv(weights_path, ["region", "weight"],
              [{"region": region, "weight": weight} for region, weight in REGIONS.items()])

    market_rows, actual_rows = [], []
    starts = [quarter_start(index) for index in range(18)]
    for quarter_index, start in enumerate(starts):
        spread = 74 + quarter_index * 2.7
        first_week = start + timedelta(days=(-start.weekday()) % 7)
        for week_index in range(13):
            week = first_week + timedelta(days=7 * week_index)
            wholesale = 210 - week_index * (1.2 + quarter_index * 0.08)
            for region_index, region in enumerate(REGIONS):
                regional_wholesale = wholesale + region_index * 3
                market_rows.append({
                    "week": week.isoformat(), "region": region,
                    "retail_cpg": regional_wholesale + spread + week_index * 0.15,
                    "wholesale_cpg": regional_wholesale,
                })
        if quarter_index < 17:
            end = quarter_start(quarter_index + 1) - timedelta(days=1)
            actual_rows.append({
                "quarter": f"{start.year}Q{(start.month - 1) // 3 + 1}",
                "start": start.isoformat(), "end": end.isoformat(),
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
    assert result.backtest_quarters >= 8
    assert result.validated
    assert result.recent_backtest_mae_cpg < result.recent_baseline_mae_cpg
    assert result.market_model_cpg != result.seasonal_baseline_cpg


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
    first_week = forecast_start + timedelta(days=(-forecast_start.weekday()) % 7)
    original_engine = NowcastEngine(load_market(market_path), load_weights(weights_path),
                                    load_actuals(actuals_path))
    original_count = original_engine.features(
        forecast_start, forecast_start + timedelta(days=90)
    ).observed_weeks
    rows = list(csv.DictReader(market_path.open(encoding="utf-8")))
    rows = [row for row in rows if not (row["week"] == first_week.isoformat()
                                        and row["region"] == "East Coast")]
    write_csv(market_path, ["week", "region", "retail_cpg", "wholesale_cpg"], rows)
    engine = NowcastEngine(load_market(market_path), load_weights(weights_path),
                           load_actuals(actuals_path))
    features = engine.features(forecast_start, forecast_start + timedelta(days=90))
    assert features.observed_weeks == original_count - 1


def test_weights_must_sum_to_one(tmp_path):
    path = tmp_path / "weights.csv"
    write_csv(path, ["region", "weight"], [
        {"region": "A", "weight": 0.6}, {"region": "B", "weight": 0.5}
    ])
    with pytest.raises(DataError, match="sum to 1.0"):
        load_weights(path)


def test_duplicate_market_observations_are_rejected(tmp_path):
    path = tmp_path / "market.csv"
    row = {"week": "2026-07-06", "region": "A", "retail_cpg": 300,
           "wholesale_cpg": 220}
    write_csv(path, list(row), [row, row])
    with pytest.raises(DataError, match="Duplicate"):
        load_market(path)


def test_market_week_must_be_monday(tmp_path):
    path = tmp_path / "market.csv"
    row = {"week": "2026-07-01", "region": "A", "retail_cpg": 300,
           "wholesale_cpg": 220}
    write_csv(path, list(row), [row])

    with pytest.raises(DataError, match="Monday"):
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


def test_backtest_is_time_ordered_and_uses_seasonal_baseline(dataset):
    market_path, weights_path, actuals_path, _ = dataset
    engine = NowcastEngine(load_market(market_path), load_weights(weights_path),
                           load_actuals(actuals_path))
    result = engine.backtest()

    assert result["backtest_quarters"] == 9
    assert result["seasonal_baseline_mae"] == result["baseline_mae"]
    assert result["historical_mean_mae"] > 0
    assert 0 <= result["directional_accuracy"] <= 1


def test_recent_regime_failure_blocks_validation(dataset):
    market_path, weights_path, actuals_path, _ = dataset
    actuals = load_actuals(actuals_path)
    adjusted = actuals[:]
    for index in range(len(adjusted) - 8, len(adjusted)):
        adjusted[index] = replace(
            adjusted[index], retail_margin_cpg=adjusted[index - 4].retail_margin_cpg
        )
    engine = NowcastEngine(load_market(market_path), load_weights(weights_path), adjusted)

    result = engine.backtest()

    assert result["recent_baseline_mae"] == 0
    assert result["validated"] is False
