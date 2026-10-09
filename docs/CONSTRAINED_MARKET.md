# Constrained market challenger results

Sign constraints did not improve the modern production backtest overall or its six original large misses. Keep production unchanged. The challenger improves Q1 2022 and Q2 2026, but worsens the other four large misses. This is developmental current-vintage research, not strict point-in-time or prospective validation.

## Frozen experiment

One specification was frozen before the first scoring run: `data/constrained_market_spec_v1.json`. Preserve the production prior-year anchor, expanding YoY training, standardized ridge penalty of 2, unpenalized intercept, regional features and 50% market-change shrinkage. Constrain spread and falling-capture slopes to be nonnegative and rising-squeeze slope to be nonpositive. Leave volatility unrestricted because volatility alone does not have a justified directional effect.

The eight active-subset fits solve one constrained convex optimization problem; they are not eight challengers selected using held-out errors. All fit decisions use earlier targets only. An inactive slope is exactly zero. This is a refit under constraints, not clipping already-fitted production coefficients.

All 44 archived production predictions were reproduced within 1e-8 before comparison. Earlier and 2020-transition quarters use the archived expanded-history training; modern quarters retain production's 2019-onward training. Regimes are evaluated separately, not blindly pooled. Earlier training releases must predate the target quarter end and market quarters must be complete. Current market vintages are not verified historical vintages. Quarter-end information availability is not quarter-start availability, and this test does not measure two-quarter-ahead forecasting.

## Modern quarters

Across all 22 quarters from Q1 2021 through Q2 2026:

- MAE: production 3.133c, constrained 3.336c.
- RMSE: production 4.019c, constrained 4.267c.
- Errors at least 5c: six versus five; worst error 9.792c versus 9.879c.
- Directional accuracy: both 20/22.
- Recent-eight MAE: 2.154c versus 2.026c, insufficient to offset deterioration overall.
- Paired improvement lower 95% normal-approximation bound: -0.570c. This is the existing descriptive gate statistic, not a multiple-research-adjusted confidence claim.
- Original six large misses: MAE 6.625c versus 6.801c; RMSE 6.802c versus 7.087c.
- Original sixteen ordinary quarters: MAE 1.823c versus 2.036c; no new errors at least 5c.

The unchanged prior-year-only baseline is weaker: modern MAE 4.836c and RMSE 6.340c. Both calibrated models improve on that simple baseline, but the constrained challenger does not improve on production. The existing promotion gate fails.

## Individual original large misses

All values are retail cents per gallon; forecasts are production then constrained, followed by actual.

- Q2 2021: 26.981c versus 29.678c; actual 21.8c. Absolute error worsens by 2.697c.
- Q4 2021: 19.191c versus 18.992c; actual 25.5c. Absolute error worsens by 0.198c.
- Q1 2022: 28.479c versus 19.972c; actual 23.3c. Absolute error improves by 1.851c, but the error changes from overestimation to underestimation rather than disappearing.
- Q3 2022: 29.508c versus 29.421c; actual 39.3c. Absolute error worsens by 0.088c.
- Q3 2023: 35.383c versus 36.022c; actual 28.7c. Absolute error worsens by 0.638c.
- Q2 2026: 28.495c versus 29.210c; actual 35.1c. Absolute error improves by 0.715c but remains 5.890c.

These six are defined by original production error, not by challenger success. They are a retrospective descriptive subset, not a prospective large-miss detector. Disclosure audit classifications are untouched; no verified no-disclosure subgroup is claimed.

## Earlier regimes

Eighteen earlier low-margin quarters: MAE 2.598c to 2.532c, RMSE 3.431c to 3.405c, large-error count three to one. However worst error increases from 8.983c to 9.850c and directional accuracy falls from 14/18 to 13/18. The gate fails.

Four 2020 transition quarters: MAE 7.726c to 7.269c and RMSE 9.889c to 9.516c. Large-error count remains two; worst error increases from 14.664c to 15.081c. This tiny sample cannot establish generalization; the gate fails.

## Interpretation

Economically appealing signs are conditional hypotheses, not identified causal effects. Spread, capture, squeeze and volatility overlap statistically. In five of the six modern large-miss fits, both capture and squeeze collapse to zero under constraints; in Q2 2021 only squeeze collapses to zero. The resulting mapping still leaves the major Q3 misses unresolved. Removing a counterintuitive coefficient can improve one quarter while shifting the intercept and other coefficients adversely elsewhere.

The test rejects this specific sign-constrained correction as a replacement for production. It does not prove that company pump prices are essential, that all public-data approaches fail, or that the unconstrained coefficients measure real economic causation. No thresholds, shrinkage, anchors or penalties were retuned after seeing results. No new live Q3 estimate was substituted.

## Reproduction

Run from the repository root with a new output directory:

```sh
.venv/bin/python -m musa_nowcast.constrained_market --out data/constrained_market/NEW_UNIQUE_RUN
.venv/bin/pytest -q tests/test_constrained_market.py
```

Canonical artifacts are in `data/constrained_market/2026-10-08_v1/`: immutable input copies and hashes, all predictions frozen before error calculation, full coefficient/training trails, and scored results. Output directories are exclusive and cannot silently overwrite an existing run. Production code and forecasts are unchanged.
