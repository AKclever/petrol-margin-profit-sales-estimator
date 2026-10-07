"""Feature construction, backtesting, and uncertainty-aware nowcasting."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from .data import MarketWeek, QuarterActual, RegionWeight
from .mathutils import RidgeModel, percentile


FEATURE_NAMES = ("spread", "falling_capture", "rising_squeeze", "volatility")
ADAPTIVE_FEATURE_NAMES = (
    "spread_mean", "falling_capture", "rising_squeeze", "price_volatility",
    "large_decline", "large_increase", "recent_spread_mean",
    "recent_wholesale_change", "recent_volatility", "price_acceleration",
    "max_weekly_wholesale_drop", "max_weekly_wholesale_increase",
)
MIN_TRAINING_QUARTERS = 8
MIN_BACKTEST_QUARTERS = 8
MARKET_CHANGE_SHRINKAGE = 0.5
MIN_BASELINE_IMPROVEMENT = 0.10
MIN_DIRECTIONAL_ACCURACY = 0.55
RECENT_BACKTEST_QUARTERS = 8
NORMAL_95_Z = 1.96
RECENT_WINDOW_WEEKS = 4
SHOCK_HINGE_CPG = 25.0
REGIME_SUPPORT_MINIMUM = 3


@dataclass(frozen=True)
class QuarterFeatures:
    spread_mean: float
    falling_capture: float
    rising_squeeze: float
    price_volatility: float
    wholesale_change: float
    retail_change: float
    large_decline: float
    large_increase: float
    recent_spread_mean: float
    recent_wholesale_change: float
    recent_volatility: float
    price_acceleration: float
    max_weekly_wholesale_drop: float
    max_weekly_wholesale_increase: float
    share_weeks_falling: float
    share_weeks_rising: float
    observed_weeks: int
    expected_weeks: int
    coverage: float

    def model_values(self, adaptive: bool = False) -> list[float]:
        """Features fixed before evaluation; all values are cents per gallon."""
        if not adaptive:
            return [self.spread_mean, self.falling_capture, self.rising_squeeze,
                    self.price_volatility]
        return [
            self.spread_mean, self.falling_capture, self.rising_squeeze,
            self.price_volatility, self.large_decline, self.large_increase,
            self.recent_spread_mean, self.recent_wholesale_change,
            self.recent_volatility, self.price_acceleration,
            self.max_weekly_wholesale_drop, self.max_weekly_wholesale_increase,
        ]


@dataclass(frozen=True)
class Forecast:
    quarter: str
    as_of: str
    forecast_type: str
    retail_margin_cpg: float
    retail_low_cpg: float
    retail_high_cpg: float
    market_model_cpg: float
    seasonal_baseline_cpg: float
    regime: str
    historical_regime_support: int
    feature_distance_z: float
    regime_penalty: float
    supply_rin_low_cpg: float | None
    supply_rin_base_cpg: float | None
    supply_rin_high_cpg: float | None
    all_in_low_cpg: float | None
    all_in_base_cpg: float | None
    all_in_high_cpg: float | None
    coverage: float
    observed_weeks: int
    expected_weeks: int
    backtest_mae_cpg: float
    backtest_rmse_cpg: float
    baseline_mae_cpg: float
    historical_mean_mae_cpg: float
    seasonal_baseline_mae_cpg: float
    backtest_directional_accuracy: float
    recent_backtest_mae_cpg: float
    recent_baseline_mae_cpg: float
    recent_directional_accuracy: float
    mae_improvement_cpg: float
    mae_improvement_ci_low_cpg: float
    backtest_quarters: int
    beats_baseline: bool
    validated: bool
    warning: str | None
    estimated_gallons_million: float | None = None
    estimated_fuel_contribution_million: float | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class NowcastEngine:
    """Calibrate market proxies to reported retail margins."""

    def __init__(self, market: list[MarketWeek], weights: list[RegionWeight],
                 actuals: list[QuarterActual], alpha: float = 2.0,
                 adaptive: bool = False):
        self.market = market
        self.weights = {item.region: item.weight for item in weights}
        self.actuals = actuals
        self.alpha = alpha
        self.adaptive = adaptive
        if alpha < 0:
            raise ValueError("Ridge penalty must be nonnegative")
        market_regions = {item.region for item in market}
        missing = set(self.weights) - market_regions
        if missing:
            raise ValueError(f"No market data for weighted regions: {', '.join(sorted(missing))}")

    def _model_values(self, features: QuarterFeatures) -> list[float]:
        return features.model_values(adaptive=self.adaptive)

    def _weekly_basket(self, start: date, end: date, as_of: date | None = None) -> list[tuple[date, float, float]]:
        cutoff = min(end, as_of) if as_of else end
        first_week = start + timedelta(days=(-start.weekday()) % 7)
        last_complete_day = cutoff - timedelta(days=4)
        last_week = last_complete_day - timedelta(days=last_complete_day.weekday())
        grouped: dict[date, dict[str, MarketWeek]] = {}
        for item in self.market:
            if first_week <= item.week <= last_week and item.region in self.weights:
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
        retail_prices = [retail for _, retail, _ in basket]
        wholesale_prices = [wholesale for _, _, wholesale in basket]
        falling, rising, wholesale_moves = [], [], []
        for (_, old_retail, old_wholesale), (_, retail, wholesale) in zip(basket, basket[1:]):
            retail_change, wholesale_change = retail - old_retail, wholesale - old_wholesale
            wholesale_moves.append(wholesale_change)
            falling.append(max((-wholesale_change) - (-retail_change), 0.0) if wholesale_change < 0 else 0.0)
            rising.append(max(wholesale_change - retail_change, 0.0) if wholesale_change > 0 else 0.0)
        recent_start = max(0, len(basket) - RECENT_WINDOW_WEEKS)
        recent_spreads = spreads[recent_start:]
        recent_wholesale = wholesale_prices[recent_start:]
        recent_moves = [right - left for left, right in zip(recent_wholesale, recent_wholesale[1:])]
        midpoint = max(0, len(recent_wholesale) - 3)
        prior_move = (recent_wholesale[midpoint] - recent_wholesale[0]
                      if len(recent_wholesale) >= 3 else 0.0)
        latest_move = (recent_wholesale[-1] - recent_wholesale[midpoint]
                       if len(recent_wholesale) >= 3 else 0.0)
        wholesale_change = wholesale_prices[-1] - wholesale_prices[0]
        retail_change = retail_prices[-1] - retail_prices[0]
        first_week = start + timedelta(days=(-start.weekday()) % 7)
        last_complete_day = end - timedelta(days=4)
        last_week = last_complete_day - timedelta(days=last_complete_day.weekday())
        expected = max(1, ((last_week - first_week).days // 7) + 1)
        return QuarterFeatures(
            sum(spreads) / len(spreads),
            sum(falling) / max(1, len(falling)),
            sum(rising) / max(1, len(rising)),
            sum(abs(move) for move in wholesale_moves) / max(1, len(wholesale_moves)),
            wholesale_change,
            retail_change,
            max(0.0, -wholesale_change - SHOCK_HINGE_CPG),
            max(0.0, wholesale_change - SHOCK_HINGE_CPG),
            sum(recent_spreads) / len(recent_spreads),
            recent_wholesale[-1] - recent_wholesale[0],
            sum(abs(move) for move in recent_moves) / max(1, len(recent_moves)),
            latest_move - prior_move,
            max([0.0] + [-move for move in wholesale_moves]),
            max([0.0] + wholesale_moves),
            sum(move < 0 for move in wholesale_moves) / max(1, len(wholesale_moves)),
            sum(move > 0 for move in wholesale_moves) / max(1, len(wholesale_moves)),
            len(basket), expected, min(1.0, len(basket) / expected),
        )

    def _training(self) -> tuple[list[list[float]], list[float]]:
        rows, targets = [], []
        for actual in self.actuals:
            rows.append(self._model_values(self.features(actual.start, actual.end)))
            targets.append(actual.retail_margin_cpg)
        return rows, targets

    @staticmethod
    def _regime(features: QuarterFeatures, reference: list[QuarterFeatures]) -> str:
        """Classify price conditions mechanically, without an event-name indicator."""
        changes = [item.wholesale_change for item in reference]
        volatilities = [item.price_volatility for item in reference]
        if features.wholesale_change <= percentile(changes, 0.20) and features.wholesale_change < 0:
            return "FAST_FALLING"
        if features.wholesale_change >= percentile(changes, 0.80) and features.wholesale_change > 0:
            return "FAST_RISING"
        if features.price_volatility >= percentile(volatilities, 0.80):
            return "HIGH_VOLATILITY"
        return "NORMAL"

    @staticmethod
    def _feature_distance(current: list[float], reference: list[list[float]]) -> float:
        """Largest absolute training-distribution z-score, robust to flat features."""
        distances = []
        for column, value in enumerate(current):
            values = [row[column] for row in reference]
            mean = sum(values) / len(values)
            variance = sum((item - mean) ** 2 for item in values) / len(values)
            scale = math.sqrt(variance)
            distances.append(abs(value - mean) / scale if scale > 1e-9 else 0.0)
        return max(distances, default=0.0)

    @staticmethod
    def _quarter_key(item: QuarterActual) -> tuple[int, int]:
        return item.start.year, (item.start.month - 1) // 3 + 1

    def _prior_year_index(self, index: int) -> int | None:
        year, quarter = self._quarter_key(self.actuals[index])
        wanted = (year - 1, quarter)
        return next((i for i, item in enumerate(self.actuals[:index])
                     if self._quarter_key(item) == wanted), None)

    def _seasonal_margin(self, start: date) -> float:
        wanted = (start.year - 1, (start.month - 1) // 3 + 1)
        matches = [item.retail_margin_cpg for item in self.actuals
                   if self._quarter_key(item) == wanted]
        if len(matches) != 1:
            raise ValueError(
                f"Forecast requires exactly one prior-year actual for {wanted[0]}Q{wanted[1]}"
            )
        return matches[0]

    @staticmethod
    def _changes(current: list[float], prior: list[float]) -> list[float]:
        return [left - right for left, right in zip(current, prior, strict=True)]

    def _change_training(self, rows: list[list[float]], targets: list[float],
                         stop: int) -> tuple[list[list[float]], list[float]]:
        change_rows, change_targets = [], []
        for index in range(stop):
            prior_year = self._prior_year_index(index)
            if prior_year is None:
                continue
            change_rows.append(self._changes(rows[index], rows[prior_year]))
            change_targets.append(targets[index] - targets[prior_year])
        return change_rows, change_targets

    @staticmethod
    def _direction(value: float) -> int:
        return (value > 0) - (value < 0)

    def backtest(self) -> dict[str, float | bool | int]:
        rows, targets = self._training()
        errors, mean_errors, seasonal_errors = [], [], []
        direction_results = []
        for held_out in range(MIN_TRAINING_QUARTERS, len(rows)):
            prior_year = self._prior_year_index(held_out)
            if prior_year is None:
                continue
            # This is an expanding-window test: a historical quarter is predicted using
            # only company actuals that were available before that quarter.
            seasonal = targets[prior_year]
            change_rows, change_targets = self._change_training(rows, targets, held_out)
            market_change = (RidgeModel(self.alpha)
                             .fit(change_rows, change_targets)
                             .predict_one(self._changes(rows[held_out], rows[prior_year])))
            prediction = seasonal + MARKET_CHANGE_SHRINKAGE * market_change
            errors.append(targets[held_out] - prediction)
            mean_errors.append(abs(targets[held_out]
                                   - sum(targets[:held_out]) / held_out))
            seasonal_errors.append(abs(targets[held_out] - seasonal))
            direction_results.append(self._direction(targets[held_out] - seasonal)
                                     == self._direction(prediction - seasonal))
        if not errors:
            raise ValueError("Backtest requires prior-year actuals after the training window")
        mae = sum(abs(value) for value in errors) / len(errors)
        rmse = math.sqrt(sum(value * value for value in errors) / len(errors))
        mean_mae = sum(mean_errors) / len(mean_errors)
        seasonal_mae = sum(seasonal_errors) / len(seasonal_errors)
        directional_accuracy = sum(direction_results) / len(errors)
        recent_count = min(RECENT_BACKTEST_QUARTERS, len(errors))
        recent_mae = sum(abs(value) for value in errors[-recent_count:]) / recent_count
        recent_mean_mae = sum(mean_errors[-recent_count:]) / recent_count
        recent_seasonal_mae = sum(seasonal_errors[-recent_count:]) / recent_count
        recent_directional_accuracy = (sum(direction_results[-recent_count:])
                                       / recent_count)
        strongest_baseline = min(mean_mae, seasonal_mae)
        baseline_errors = mean_errors if mean_mae < seasonal_mae else seasonal_errors
        improvements = [baseline_error - abs(error)
                        for baseline_error, error in zip(baseline_errors, errors, strict=True)]
        mean_improvement = sum(improvements) / len(improvements)
        improvement_variance = (sum((value - mean_improvement) ** 2 for value in improvements)
                                / max(1, len(improvements) - 1))
        improvement_ci_low = (mean_improvement
                              - NORMAL_95_Z * math.sqrt(improvement_variance / len(improvements)))
        beats_baseline = mae < strongest_baseline
        validated = (len(errors) >= MIN_BACKTEST_QUARTERS
                     and mae <= strongest_baseline * (1.0 - MIN_BASELINE_IMPROVEMENT)
                     and directional_accuracy >= MIN_DIRECTIONAL_ACCURACY
                     and improvement_ci_low > 0
                     and recent_mae <= min(recent_mean_mae, recent_seasonal_mae)
                                      * (1.0 - MIN_BASELINE_IMPROVEMENT)
                     and recent_directional_accuracy >= MIN_DIRECTIONAL_ACCURACY)
        return {"mae": mae, "rmse": rmse, "baseline_mae": seasonal_mae,
                "historical_mean_mae": mean_mae, "seasonal_baseline_mae": seasonal_mae,
                "directional_accuracy": directional_accuracy,
                "recent_mae": recent_mae,
                "recent_baseline_mae": min(recent_mean_mae, recent_seasonal_mae),
                "recent_directional_accuracy": recent_directional_accuracy,
                "mae_improvement": mean_improvement,
                "mae_improvement_ci_low": improvement_ci_low,
                "backtest_quarters": len(errors), "beats_baseline": beats_baseline,
                "validated": validated}

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
        historical_features = [self.features(item.start, item.end) for item in self.actuals]
        seasonal = self._seasonal_margin(start)
        wanted = (start.year - 1, (start.month - 1) // 3 + 1)
        prior_year = next(i for i, item in enumerate(self.actuals)
                          if self._quarter_key(item) == wanted)
        change_rows, change_targets = self._change_training(rows, targets, len(rows))
        market_change = (RidgeModel(self.alpha).fit(change_rows, change_targets)
                         .predict_one(self._changes(self._model_values(features), rows[prior_year])))
        market_prediction = seasonal + market_change
        prediction = seasonal + MARKET_CHANGE_SHRINKAGE * market_change
        backtest = self.backtest()
        if self.adaptive:
            regime = self._regime(features, historical_features)
            regime_support = sum(self._regime(item, historical_features) == regime
                                 for item in historical_features)
            feature_distance = self._feature_distance(self._model_values(features), rows)
            # A live point outside historical feature space gets a transparent uncertainty
            # multiplier. This changes the interval, not the fitted relationship.
            regime_penalty = min(
                2.0,
                1.0 + 0.15 * max(0.0, feature_distance - 1.0)
                + (0.25 if regime_support < REGIME_SUPPORT_MINIMUM else 0.0),
            )
        else:
            regime, regime_support, feature_distance, regime_penalty = (
                "NOT_EVALUATED", 0, 0.0, 1.0
            )
        # Incomplete quarters and out-of-distribution regimes both widen the interval.
        interval = (1.64 * float(backtest["rmse"])
                    * math.sqrt(1.0 + (1.0 - features.coverage)) * regime_penalty)
        supply_values = [item.supply_rin_cpg for item in self.actuals
                         if item.supply_rin_cpg is not None]
        if supply_values and len(supply_values) != len(self.actuals):
            raise ValueError("Supply/RIN history must be either complete or omitted entirely")
        if supply_values:
            supply_low = percentile(supply_values, 0.20)
            supply_base = percentile(supply_values, 0.50)
            supply_high = percentile(supply_values, 0.80)
            all_in_low = prediction - interval + supply_low
            all_in_base = prediction + supply_base
            all_in_high = prediction + interval + supply_high
        else:
            supply_low = supply_base = supply_high = None
            all_in_low = all_in_base = all_in_high = None
        contribution_margin = all_in_base if all_in_base is not None else prediction
        contribution = (contribution_margin * gallons_million / 100.0
                        if gallons_million is not None else None)
        warnings = []
        if not bool(backtest["validated"]):
            warnings.append("The model fails the leakage-safe trust gate; treat this as an "
                            "experimental dashboard signal, not a validated forecast.")
        if features.coverage < 0.75:
            warnings.append("Less than 75% of expected quarter-weeks are observed; the "
                            "interval remains preliminary.")
        if self.adaptive and feature_distance > 2.0:
            warnings.append("Current market features are outside the usual historical range; "
                            "the interval includes an out-of-distribution penalty.")
        if self.adaptive and regime_support < REGIME_SUPPORT_MINIMUM:
            warnings.append(f"Regime {regime} has weak historical support "
                            f"({regime_support} comparable quarters).")
        warning = " ".join(warnings) or None
        return Forecast(
            quarter, as_of.isoformat(),
            "adaptive_realized_market_nowcast" if self.adaptive else "realized_market_nowcast",
            round(prediction, 2), round(prediction - interval, 2),
            round(prediction + interval, 2), round(market_prediction, 2), round(seasonal, 2),
            regime, regime_support, round(feature_distance, 2), round(regime_penalty, 2),
            round(supply_low, 2) if supply_low is not None else None,
            round(supply_base, 2) if supply_base is not None else None,
            round(supply_high, 2) if supply_high is not None else None,
            round(all_in_low, 2) if all_in_low is not None else None,
            round(all_in_base, 2) if all_in_base is not None else None,
            round(all_in_high, 2) if all_in_high is not None else None,
            round(features.coverage, 3), features.observed_weeks, features.expected_weeks,
            round(float(backtest["mae"]), 2), round(float(backtest["rmse"]), 2),
            round(float(backtest["baseline_mae"]), 2),
            round(float(backtest["historical_mean_mae"]), 2),
            round(float(backtest["seasonal_baseline_mae"]), 2),
            round(float(backtest["directional_accuracy"]), 3),
            round(float(backtest["recent_mae"]), 2),
            round(float(backtest["recent_baseline_mae"]), 2),
            round(float(backtest["recent_directional_accuracy"]), 3),
            round(float(backtest["mae_improvement"]), 2),
            round(float(backtest["mae_improvement_ci_low"]), 2),
            int(backtest["backtest_quarters"]), bool(backtest["beats_baseline"]),
            bool(backtest["validated"]), warning,
            gallons_million, round(contribution, 2) if contribution is not None else None,
        )


class AdaptiveNowcastEngine(NowcastEngine):
    """Shadow challenger with pre-specified shock and recency features.

    It is deliberately opt-in so production forecasts retain their frozen feature set until
    the challenger completes its separately governed promotion process.
    """

    def __init__(self, market: list[MarketWeek], weights: list[RegionWeight],
                 actuals: list[QuarterActual], alpha: float = 2.0):
        super().__init__(market, weights, actuals, alpha=alpha, adaptive=True)
