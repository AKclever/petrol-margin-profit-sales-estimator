# Constrained state-space challenger V1

This experiment failed. It is not a replacement for production and its negative
Q3 2026 point is not a usable MUSA margin estimate.

## Frozen experiment

`data/state_space_spec_v1.json` was written before the first fit. There is no
hyperparameter search, best-scenario selection, or post-result retuning.
Each expanding-window fold estimates regional equilibrium price spreads and
bounded asymmetric adjustment speeds using only earlier weekly history.
A forward cost filter treats wholesale spot as a noisy observation of a local
cost level. A second forward filter evolves regional pump pricing toward cost
plus the equilibrium spread, with different rising and falling response speeds.
Observed regional retail prices update that state. Neither filter is a
backward smoother.

Four separate seasonal company-versus-proxy margin offsets are random walks.
Reported company quarterly retail margins update the corresponding seasonal
offset through scalar Kalman updates. No target-quarter company outcome enters
its forecast. Gallon-weighted weekly filtered spreads plus the prior offset
reconcile exactly to the quarterly estimate.

This is a constrained, approximate scalar state-space prototype, not a full
joint Bayesian delivered-cost model. Filter cross-covariance, parameter
uncertainty, and company cost differences are not identified. Partial-quarter
disclosures are not assimilated in V1. Their strict replay blockers are unchanged.

## Result, preserved without retuning

The central Q3 2026 raw research output is -6.65 cents per gallon, against a
production rerun of 28.94 cents. Fixed slow/fast cost scenarios span -7.69 to
-3.96 cents; that range is sensitivity, not a confidence interval.

On the same 21 held-out quarters, central-model MAE is 8.68 cents versus
production's 3.12 cents. RMSE is 10.78 versus 4.05; directional accuracy is
66.7% versus 90.5%. The existing historical gate fails. No promotion occurred.

The calculations reconcile; the economic mapping does not. The filtered Q3
regional price spread is 45.35 cents and the seasonal company basis offset is
-52.00 cents. Their sum gives the negative output. A slowly evolving additive
offset is too rigid to transfer the regional spot/pump spread into MUSA realized
margin across these regimes. This is an inference from this prototype's
outputs, not proof about MUSA's actual acquisition costs or pricing behavior.
The negative result has not been floored to hide that failure.

Current-vintage prices, demand, static store weights, outcome availability, and
research-informed hypotheses prevent a historical PIT/prospective-validation
claim. The 3 final boundary days use the prior weekly state, not future prices.
Q3 actual remains null; no scored Q3 result is claimed.

## Artifacts and reproduction

`data/state_space/q3_2026_v1/` contains forecast, paired backtest, weekly scenario
allocations, and immutable copies/hashes of inputs, specification and code.
Demand bytes are reused from the archived weekly challenger capture, not fetched
from an unrecorded historical vintage. To rerun into a new directory:

```bash
.venv/bin/python -m musa_nowcast.state_space --output data/state_space/new_run
```

Existing output directories are refused. Production and the earlier frozen
29.54-cent pre-earnings checkpoint remain untouched.
