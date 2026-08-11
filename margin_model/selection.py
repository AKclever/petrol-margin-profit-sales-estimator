"""Rolling-origin out-of-sample selection for wholesale lag structures."""

from collections.abc import Sequence
from math import sqrt


SINGLE_FEATURES = ("same_day", "trailing_3d", "trailing_7d", "lag_1w", "lag_2w")


def _fit_line(x: Sequence[float], y: Sequence[float]) -> tuple[float, float]:
    xbar, ybar = sum(x) / len(x), sum(y) / len(y)
    denom = sum((v - xbar) ** 2 for v in x)
    slope = sum((a - xbar) * (b - ybar) for a, b in zip(x, y)) / denom if denom else 0.0
    return ybar - slope * xbar, slope


def _fit_distributed(rows: Sequence[dict[str, float]], y: Sequence[float]) -> tuple[float, list[float]]:
    """Grid-fit nonnegative [current, 1w, 2w] weights summing to one."""
    best: tuple[float, float, list[float]] | None = None
    for current_i in range(11):
        for week1_i in range(11 - current_i):
            weights = [current_i / 10, week1_i / 10, (10 - current_i - week1_i) / 10]
            x = [sum(w * float(r[k]) for w, k in zip(weights, ("same_day", "lag_1w", "lag_2w"))) for r in rows]
            intercept, slope = _fit_line(x, y)
            error = sum((actual - (intercept + slope * value)) ** 2 for actual, value in zip(y, x))
            if best is None or error < best[0]:
                best = error, intercept, [slope * w for w in weights]
    assert best is not None
    return best[1], best[2]


def rolling_origin_scores(
    rows: Sequence[dict[str, float]], target: Sequence[float], min_train: int, horizon: int = 1
) -> dict[str, dict[str, object]]:
    """Calculate expanding-window RMSEs with strictly subsequent test folds."""
    if len(rows) != len(target) or min_train < 3 or len(rows) < min_train + horizon:
        raise ValueError("insufficient or mismatched observations")
    errors: dict[str, list[float]] = {name: [] for name in (*SINGLE_FEATURES, "distributed_0_1_2w")}
    for stop in range(min_train, len(rows), horizon):
        test_stop = min(stop + horizon, len(rows))
        train_y = [float(v) for v in target[:stop]]
        for name in SINGLE_FEATURES:
            intercept, slope = _fit_line([float(r[name]) for r in rows[:stop]], train_y)
            errors[name].extend(float(target[i]) - (intercept + slope * float(rows[i][name])) for i in range(stop, test_stop))
        intercept, coefs = _fit_distributed(rows[:stop], train_y)
        for i in range(stop, test_stop):
            prediction = intercept + sum(c * float(rows[i][k]) for c, k in zip(coefs, ("same_day", "lag_1w", "lag_2w")))
            errors["distributed_0_1_2w"].append(float(target[i]) - prediction)
    result = {name: {"rmse": sqrt(sum(e * e for e in values) / len(values)), "errors": values} for name, values in errors.items()}
    winner = min(result, key=lambda name: float(result[name]["rmse"]))
    result["selection"] = {"winner": winner, "criterion": "minimum rolling-origin RMSE"}
    return result

