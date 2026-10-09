# Joint all-compatible-feature experiment

Specification: `data/joint_all_features_spec_v1.json`.
Canonical archive: `data/joint_all_features/2026-10-08_v1`.
Role: **DEVELOPMENTAL_CURRENT_VINTAGE_NOT_PIT_VALIDATION**.
Production unchanged. Single fitted joint model, not a blend of predictions.

## What was fitted

Sixteen standardized numeric features representing the seven compatible
research directions plus the original market features:

- Four YoY changes in regular retail/wholesale spread, falling capture,
  rising squeeze and wholesale volatility.
- Four incremental all-grade changes relative to those regular changes.
- Diesel retail-price YoY change.
- Immediately prior published revenue gap.
- Regional stock YoY change and refinery-utilization YoY change.
- Prior published station/store cost-per-gallon YoY change and signed
  negative prior same-store gallon growth.
- Casey's and Couche-Tard unexpected reported fuel margins, using the
  latest published overlapping fiscal periods.

The target is the original production model's earlier out-of-fold residual,
not final retail margin fitted in-sample. Prediction is the original
production forecast plus half the joint residual forecast. Ridge alpha 10,
50% correction shrinkage, minimum eight earlier published complete-feature
OOF rows. These settings and feature definitions were frozen before fitting;
no parameter grid, feature-subset search or special weighting of known
big misses. Squared-error training naturally penalizes large residuals.

All inputs must exist. No zero substitution or changing feature subsets.
The diesel survey-crossing rows 2022Q2–2023Q2 are excluded from training
and scoring. Original modern baseline is retained; earlier low-margin
regimes are not pooled into this fit. Peer absolute margins and all-in
supply/RIN economics are not mixed into the retail-margin target.

This represents all seven compatible numeric directions in the preceding
seven-shadow experiment. It is **not** every variable or output of every
previous failed model. Qualitative/risk evidence, blocked replays and futures
without a retail-response mapping cannot be treated as interchangeable
numeric retail-margin observations.

## Overall result

There are 15 complete feature rows, leaving **seven held-out tests**,
2024Q4–2026Q2. MAE on identical quarters:

- Original production: **2.387¢**.
- Joint all-feature model: **2.484¢** — about 4.1% worse.
- Previously frozen two-input diesel/revenue-gap model: **2.089¢**.

RMSE improves 3.227¢ → 2.945¢, while directional accuracy stays 71.4%.
The full model fails the gate: too few tests, worse MAE, and negative
paired-improvement confidence lower bound (−1.285¢). With 16 features and
only eight initial training rows, regularization permits a mathematical fit
but does not create enough independent evidence for trustworthy calibration.

## Original big misses

The six-quarter set was frozen from the original production errors before
this fit, rather than chosen from the joint model's outcomes.

Only **Q2 2026** is scoreable:

- Actual retail margin: **35.10¢**.
- Original production: **28.50¢**, absolute error **6.60¢**.
- Joint all-feature model: **29.55¢**, absolute error **5.55¢**.
- Improvement: **1.06¢**, approximately **16.0%**.

The previously tested four-input diesel/gap/peer model gave 29.88¢ and
5.22¢ error on this quarter, so adding the remaining features did not make
the large miss better than that simpler peer-inclusive model.

The other six eligible, non-big-miss quarters have average error
**1.684¢ production → 1.973¢ joint model**, approximately 17.1% worse.
That is also the remove-largest-benefit diagnostic: the largest-benefit
quarter is Q2 2026. The headline tail improvement is one observation, not
evidence that the system consistently identifies or solves high-opportunity
quarters before earnings.

The other five original big misses remain explicit:

- 2021Q2: missing eligible published peer input.
- 2021Q4 and 2022Q1: fewer than eight earlier published complete-feature rows.
- 2022Q3: diesel survey-break crossing.
- 2023Q3: fewer than eight earlier published complete-feature rows.

Their challenger forecasts/errors remain null. No later observations are
used to backfill an apparently successful forecast. Earlier unavailable
cases are missing evidence, not evidence that this model would succeed.

## Evidence and interpretation

All input bytes and code are copied/hashed before fitting. Normalized
feature vectors, feature order, source timing evidence, exclusions and
training-quarter lists are archived. Historical market observations remain
current-vintage; original intraday availability and revisions are not proven.
Peer period overlap, fee basis, proxy geography and acquisitions remain
limitations inherited from the prior experiments. Store expense is not
mechanically added to retail gross margin. No MUSA grade/diesel mix is
invented.

Conclusion: this experiment does **not** justify replacing production or
claiming a tail-forecasting edge. Big-margin misses are important, but knowing
afterwards which quarters were opportunities is not an investable selection
rule. The next honest test is frozen prospective shadow forecasts, paired
with a risk state defined before results; alternatively, reconstruct older
peer/source evidence to enlarge legitimate training coverage, without using
future outcomes to predict past misses.

```bash
.venv/bin/python -m musa_nowcast.joint_all_features --out data/joint_all_features/NEW_UNIQUE_RUN
.venv/bin/python -m pytest -q
```
