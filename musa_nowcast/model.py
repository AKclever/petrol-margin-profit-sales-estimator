"""Feature construction, backtesting, and uncertainty-aware nowcasting."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from .data import MarketWeek, QuarterActual, RegionWeight
from .mathutils import RidgeModel, percentile


FEATURE_NAMES = ("spread", "falling_capture", "rising_squeeze", "volatility")


@dataclass(frozen=True)
class QuarterFeatures:
    spread: float
    falling_capture: float
    rising_squeeze: float
    volatility: float
    observed_weeks: int
    expected_weeks: int
    coverage: float

    def model_values(self) -> list[float]:
        return [self.spread, self.falling_capture, self.rising_squeeze, self.volatility]


@dataclass(frozen=True)
class Forecast:
    quarter: str
    as_of: str
    retail_margin_cpg: float
    retail_low_cpg: float
    retail_high_cpg: float
    supply_rin_low_cpg: float
    supply_rin_base_cpg: float
    supply_rin_high_cpg: float
    all_in_low_cpg: float
    all_in_base_cpg: float
    all_in_high_cpg: float
    coverage: float
    observed_weeks: int
    expected_weeks: int
    backtest_mae_cpg: float
    backtest_rmse_cpg: float
    baseline_mae_cpg: float
    beats_baseline: bool
    warning: str | None
    estimated_gallons_million: float | None = None
    estimated_fuel_contribution_million: float | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class NowcastEngine:
    """Calibrate market proxies to reported retail margins."""

    def __init__(self, market: list[MarketWeek], weights: list[RegionWeight],
                 actuals: list[QuarterActual], alpha: float = 2.0):
        self.market = market
        self.weights = {item.region: item.weight for item in weights}
        self.actuals = actuals
        self.alpha = alpha
        if alpha < 0:
            raise ValueError("Ridge penalty must be nonnegative")
        market_regions = {item.region for item in market}
        missing = set(self.weights) - market_regions
        if missing:
            raise ValueError(f"No market data for weighted regions: {', '.join(sorted(missing))}")

    def _weekly_basket(self, start: date, end: date, as_of: date | None = None) -> list[tuple[date, float, float]]:
        cutoff = min(end, as_of) if as_of else end
        grouped: dict[date, dict[str, MarketWeek]] = {}
        for item in self.market:
            if start <= item.week <= cutoff and item.region in self.weights:
                grouped.setdefault(item.week, {})[item.region] = item
        result = []
        for week, regions in sorted(grouped.items()):
            if set(regions) != set(self.weights):
                continue  # Never silently reweight a week with incomplete regions.
            retail = sum(regions[region].retail_cpg * weight for region, weight in self.weights.items())
            wholesale = sum(regions[region].wholesale_cpg * weight for region, weight in self.weights.items())
            result.append((week, retail, wholesale))
        return result

    def features(self, start: date, end: date, as_of: date | None = None) -> QuarterFeatures:
        basket = self._weekly_basket(start, end, as_of)
        if not basket:
            raise ValueError(f"No complete weighted market weeks between {start} and {end}")
        spreads = [retail - wholesale for _, retail, wholesale in basket]
        falling, rising, volatility = [], [], []
        for (_, old_retail, old_wholesale), (_, retail, wholesale) in zip(basket, basket[1:]):
            retail_change, wholesale_change = retail - old_retail, wholesale - old_wholesale
            volatility.append(abs(wholesale_change))
            falling.append(max((-wholesale_change) - (-retail_change), 0.0) if wholesale_change < 0 else 0.0)
            rising.append(max(wholesale_change - retail_change, 0.0) if wholesale_change > 0 else 0.0)
        expected = max(1, math.ceil((end - start + timedelta(days=1)).days / 7))
        return QuarterFeatures(
            sum(spreads) / len(spreads),
            sum(falling) / max(1, len(falling)),
            sum(rising) / max(1, len(rising)),
            sum(volatility) / max(1, len(volatility)),
            len(basket), expected, min(1.0, len(basket) / expected),
        )

    def _training(self) -> tuple[list[list[float]], list[float]]:
        rows, targets = [], []
        for actual in self.actuals:
            rows.append(self.features(actual.start, actual.end).model_values())
            targets.append(actual.retail_margin_cpg)
        return rows, targets

    def backtest(self) -> dict[str, float | bool]:
        rows, targets = self._training()
        errors, baseline_errors = [], []
        for held_out in range(len(rows)):
            train_rows = [row for i, row in enumerate(rows) if i != held_out]
            train_targets = [target for i, target in enumerate(targets) if i != held_out]
            prediction = RidgeModel(self.alpha).fit(train_rows, train_targets).predict_one(rows[held_out])
            errors.append(targets[held_out] - prediction)
            baseline = sum(train_targets) / len(train_targets)
            baseline_errors.append(abs(targets[held_out] - baseline))
        mae = sum(abs(value) for value in errors) / len(errors)
        rmse = math.sqrt(sum(value * value for value in errors) / len(errors))
        baseline_mae = sum(baseline_errors) / len(baseline_errors)
        return {"mae": mae, "rmse": rmse, "baseline_mae": baseline_mae,
                "beats_baseline": mae < baseline_mae}

    def forecast(self, quarter: str, start: date, end: date, as_of: date,
                 gallons_million: float | None = None) -> Forecast:
        if end < start:
            raise ValueError("Forecast end must not precede start")
        if as_of < start:
            raise ValueError("Forecast as-of date must not precede quarter start")
        if gallons_million is not None and gallons_million <= 0:
            raise ValueError("Forecast gallons must be positive")
        features = self.features(start, end, as_of)
        rows, targets = self._training()
        prediction = RidgeModel(self.alpha).fit(rows, targets).predict_one(features.model_values())
        backtest = self.backtest()
        # Incomplete quarters receive an explicit uncertainty penalty that fades with coverage.
        interval = 1.64 * float(backtest["rmse"]) * math.sqrt(1.0 + (1.0 - features.coverage))
        supply_values = [item.supply_rin_cpg for item in self.actuals]
        supply_low = percentile(supply_values, 0.20)
        supply_base = percentile(supply_values, 0.50)
        supply_high = percentile(supply_values, 0.80)
        all_in_base = prediction + supply_base
        contribution = all_in_base * gallons_million / 100.0 if gallons_million is not None else None
        warning = None
        if not bool(backtest["beats_baseline"]):
            warning = "The calibrated model does not beat a historical-mean baseline; treat as a dashboard signal."
        elif features.coverage < 0.75:
            warning = "Less than 75% of expected quarter-weeks are observed; the interval remains preliminary."
        return Forecast(
            quarter, as_of.isoformat(), round(prediction, 2), round(prediction - interval, 2),
            round(prediction + interval, 2), round(supply_low, 2), round(supply_base, 2),
            round(supply_high, 2), round(prediction - interval + supply_low, 2),
            round(all_in_base, 2), round(prediction + interval + supply_high, 2),
            round(features.coverage, 3), features.observed_weeks, features.expected_weeks,
            round(float(backtest["mae"]), 2), round(float(backtest["rmse"]), 2),
            round(float(backtest["baseline_mae"]), 2), bool(backtest["beats_baseline"]), warning,
            gallons_million, round(contribution, 2) if contribution is not None else None,
        )
