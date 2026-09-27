# MUSA wholesale timing challenger V1

`MUSA_WHOLESALE_TIMING_CHALLENGER_V1` asks whether MUSA's realized acquisition cost is
better represented by a small, fixed delay in the existing wholesale proxy. The specification
was frozen before evaluation and does not fit a lag or weight to MUSA outcomes.

## Fixed candidates

| Name | Wholesale transformation |
| --- | --- |
| A | Exactly one-week lag |
| B | 50% current week plus 50% prior week |
| C | Equal-weight current and prior two weeks |

All other components remain unchanged: production retail observations and weights, four
features, ridge penalty, 50% market-change shrinkage, expanding-window evaluation, target,
and eligible historical quarters. Missing calendar weeks are not bridged. Q3 2026's reported
outcome was unavailable and was not used.

## Preserved result

All comparisons use the same 22 quarters as the production model.

| Measure | Production | A: lag 1 | B: 50/50 | C: trailing 3 |
| --- | ---: | ---: | ---: | ---: |
| MAE | 3.13 | 2.76 | 2.78 | 3.05 |
| RMSE | 4.02 | 3.59 | 3.84 | 4.05 |
| Directional accuracy | 90.9% | 72.7% | 86.4% | 90.9% |
| Recent-eight MAE | 2.15 | 2.45 | 2.02 | 1.94 |
| Recent-eight direction | 75.0% | 62.5% | 75.0% | 87.5% |
| Mean paired improvement | — | 0.38 | 0.35 | 0.08 |
| Paired 95% lower bound | — | -0.21 | -0.22 | -0.67 |
| Q3 2026 retail estimate | 29.54 | 29.49 | 27.98 | 28.04 |

No candidate passes. A has the best full-sample MAE but materially damages directional
accuracy and worsens in the latest eight quarters. B's full-sample MAE improvement exceeds
10%, but its direction is worse, its recent MAE improvement is only about 6%, and its paired
lower bound is negative. C preserves full-sample direction and improves the recent period,
but its full-sample improvement is too small and statistically unstable.

Production remains unchanged at a 29.54 cpg Q3 retail-margin estimate. These candidates are
preserved as `NOT_AUTOMATICALLY_PROMOTED`; they must not be combined or tuned retrospectively.

## Reproduce

```bash
python -m musa_nowcast.timing \
  --market data/market.csv \
  --weights data/weights.csv \
  --actuals data/actuals.csv \
  --output-dir data/timing_research \
  --quarter 2026Q3 \
  --start 2026-07-01 \
  --end 2026-09-30 \
  --as-of 2026-09-27
```

`research_spec.json` contains the frozen specification and hash. `evaluation.csv` contains
every paired quarter. `results.json`, `current_forecasts.json`, and `manifest.json` preserve
the decision, live estimates, input hashes, and artifact hashes. The three transformed market
files make the mechanical inputs directly inspectable.
