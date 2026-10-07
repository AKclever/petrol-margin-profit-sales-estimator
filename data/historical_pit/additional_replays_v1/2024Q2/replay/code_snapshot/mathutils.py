"""Small dependency-free statistical helpers."""

from __future__ import annotations

import math


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires observations")
    position = (len(ordered) - 1) * probability
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    fraction = position - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve Ax=b with partial-pivot Gaussian elimination."""
    augmented = [row[:] + [value] for row, value in zip(matrix, vector, strict=True)]
    size = len(vector)
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("Singular model matrix")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [left - factor * right
                              for left, right in zip(augmented[row], augmented[column], strict=True)]
    return [augmented[row][-1] for row in range(size)]


class RidgeModel:
    """Standardized ridge regression with an unpenalized intercept."""

    def __init__(self, alpha: float = 2.0):
        self.alpha = alpha

    def fit(self, rows: list[list[float]], targets: list[float]) -> "RidgeModel":
        if len(rows) != len(targets) or not rows:
            raise ValueError("Features and targets must have equal nonzero length")
        width = len(rows[0])
        self.means = [sum(row[i] for row in rows) / len(rows) for i in range(width)]
        self.scales = []
        for i, mean in enumerate(self.means):
            variance = sum((row[i] - mean) ** 2 for row in rows) / len(rows)
            self.scales.append(math.sqrt(variance) or 1.0)
        design = [[1.0] + [(value - mean) / scale for value, mean, scale
                           in zip(row, self.means, self.scales, strict=True)] for row in rows]
        size = width + 1
        gram = [[sum(row[i] * row[j] for row in design) for j in range(size)] for i in range(size)]
        rhs = [sum(row[i] * target for row, target in zip(design, targets, strict=True))
               for i in range(size)]
        for i in range(1, size):
            gram[i][i] += self.alpha
        self.coefficients = solve(gram, rhs)
        return self

    def predict_one(self, row: list[float]) -> float:
        standardized = [(value - mean) / scale for value, mean, scale
                        in zip(row, self.means, self.scales, strict=True)]
        return self.coefficients[0] + sum(coef * value for coef, value in
                                          zip(self.coefficients[1:], standardized, strict=True))

