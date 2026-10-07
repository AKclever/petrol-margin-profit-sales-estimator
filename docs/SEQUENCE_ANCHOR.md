# Sequence and seasonal-anchor residual challenger V1

Production is unchanged. This challenger shows a small retrospective improvement,
but fails the existing promotion gate and is not independently validated.

The specification in `data/sequence_anchor_spec_v1.json` was frozen before the
first fit. Features were motivated by already-inspected historical misses, so
time-ordered target holdouts do not make this an independent hypothesis test.
Current market history and store weights are not historical PIT vintages;
company-outcome publication lags are not reconstructed.

## Mechanism

The correction is added to production rather than rebuilding margin levels.
Three features are used: negative seasonal-anchor anomaly, persistent capture,
and negative persistent squeeze. The anchor anomaly compares the prior-year
same-quarter margin to the median of up to three earlier same-quarter margins.
Only earlier outcomes are used. A single earlier seasonal observation gives
zero anomaly rather than an invented normalized baseline.

Capture and squeeze impulses are calculated separately within each region,
before geographic aggregation. Each stock retains 80% of its prior-week value.
It continues across quarter boundaries; the quarterly feature averages stocks
over the same complete in-quarter weeks as production. Opposing regional moves
therefore do not disappear before the asymmetric impulses are calculated.
Weights are static store weights and uniform weekly weights, not observed
MUSA gallon shares. Missing internal complete weeks or insufficient regional
warmup block the calculation.

The residual targets are actual minus expanding-window production prediction.
At least eight earlier out-of-fold production residuals are required before a
correction can be evaluated. Nonnegative standardized ridge coefficients,
alpha 2 and a 50% correction shrinkage are fixed. No hyperparameter search,
post-result feature tuning or selection among scenarios was performed.

## Results

There are 14 comparable quarters, Q1 2023 through Q2 2026. The correction cannot
be evaluated on the earliest eight production test quarters, including Q3 2022,
because insufficient earlier residual targets existed. Those cases remain
training observations, not claimed correction successes.

Production MAE on the 14 identical rows is 2.3025 cents; challenger MAE is 2.2293,
an improvement of approximately 3.2%. RMSE falls from 3.1202 to 2.7797 cents.
Directional accuracy remains 85.7%. Recent-eight MAE falls from 2.1535 to 1.8711.
The paired improvement lower confidence bound is negative (-0.6690 cents), and
the overall MAE improvement is below the fixed 10% threshold. The gate fails.

Q2 2026 improves materially: prediction rises from 28.50 to 32.43 cents versus
35.10 actual, reducing absolute error from 6.60 to 2.67 cents. Q3 2023 improves
only modestly, from 35.38 to 34.53 versus 28.70 actual. Several other quarters
worsen. Removing Q2 2026 from the descriptive comparison reverses the aggregate
benefit; this is a fragility diagnostic, not a justification to change the test
sample or fitting rules.

Q3 2026 research shadow is 29.8034 cents versus production 28.94, a +0.8634-cent
correction. Q3 actual and scoring fields remain unset. The shadow is not a new
official forecast, and the earlier 29.54-cent pre-earnings checkpoint is intact.

## Artifacts and reproduction

`data/sequence_anchor/q3_2026_v1_run2/` includes the forecast, per-quarter paired
backtest, feature details and regional contributions, production out-of-fold
residuals, and hash-verified copies of the code, inputs and frozen specification.
The original `q3_2026_v1` run is retained. Run 2 corrected inherited optimizer
feature-name metadata and added additive correction contributions; forecasts
and every metric are exactly identical. No fitting assumptions changed.

```bash
.venv/bin/python -m musa_nowcast.sequence_anchor --output data/sequence_anchor/new_run
```

Existing output directories are refused. The module is not wired into daily
production capture, and no automatic promotion is permitted.
