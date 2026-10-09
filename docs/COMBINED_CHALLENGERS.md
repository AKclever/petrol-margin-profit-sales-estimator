# Combined challengers and diesel survey-break audit

Canonical output: `data/combined_challengers/2026-10-08_v2/results.json`.
Specification: `data/combined_challengers_spec_v1.json`, frozen before scoring.
Role: **DEVELOPMENTAL_CURRENT_VINTAGE_RESEARCH_NOT_PIT_VALIDATION**.
Production and the existing point forecast are unchanged. No challenger passes
the existing promotion gate; no weights or thresholds were optimized.

## Diesel measurement break

[EIA documents a new diesel survey sample and methodology on June 13, 2022](https://www.eia.gov/petroleum/gasdiesel/diesel_proc-methods.php).
Estimates across the switch are not directly comparable. The previous diesel
experiment used unadjusted YoY retail-price changes, so features in 2022Q2
through 2023Q2 cross or straddle that switch.

The new clean diesel experiment removes those five feature rows from **both
training and scoring**, rather than merely hiding them from reported metrics.
No historical level adjustment or bridge coefficient is invented. Clean
pre-switch YoY and post-switch YoY observations remain eligible. This does
not repair all historical revisions or turn market data into PIT vintages.

Eight earlier published clean modern residuals are required, leaving nine
held-out quarters, 2024Q2–2026Q2. Clean diesel MAE is **2.188¢ production →
2.013¢ shadow**, an 8.0% improvement. Its full directional accuracy is worse
(77.8% → 66.7%) and paired improvement's confidence lower bound is −0.209¢.
It fails the gate.

The previous 16.7% result used 14 different test quarters and a different
training history. It must not be directly subtracted from this result to
quantify a survey-artifact contribution. The new result is a stricter
sensitivity test, not proof that all earlier benefit was spurious.

## Frozen combinations

Joint models use standardized ridge alpha **10**, minimum eight earlier
published complete-feature residuals, and **50%** correction shrinkage.
Equal blends average full shadow forecasts with fixed equal weights. Every
required component must exist; missing components never trigger reweighting.

On the same nine quarters, production MAE is **2.188¢**:

- Clean diesel alone: **2.013¢**.
- Equal blend of clean diesel and lagged revenue gap: **2.013¢** (8.0% gain).
- Joint clean diesel/revenue gap: **1.989¢** (9.1% gain).
- Equal blend of seven compatible shadows: **2.070¢** (5.4% gain).

The seven fixed components are clean diesel, lagged revenue gap, regional
supply, margin-floor cost/volume pressure, all-grade gasoline, Casey's and
Couche-Tard. Their individual MAEs on these identical nine quarters are
2.013¢, 2.069¢, 2.238¢, 2.127¢, 2.189¢, 2.033¢ and 2.156¢ respectively.
The broad blend is not better than the simpler two-input joint model.
This is a fixed experiment, not a search over every possible feature subset.

Neither the two-input joint model nor the blend passes the gate. The joint
model falls short of 10% overall improvement, worsens overall direction,
and its paired-benefit confidence lower bound is negative. The two-shadow
blend preserves overall direction and improves recent direction, but has
less than 10% overall MAE gain and a negative confidence lower bound.
The seven-shadow blend has less than 10% overall/recent MAE gain and its
confidence lower bound is slightly negative (−0.002¢).

The two-input joint model's recent-eight error improves 2.154¢ → 1.833¢.
Removing its largest-benefit quarter, 2024Q4, leaves 2.233¢ → 2.111¢;
the residual benefit is smaller and does not establish generalization.

## Competitor earnings

Use each peer's **unexpected reported margin**, relative to its own earlier-
trained model. Select the latest published overlapping fiscal period
strictly before MUSA's quarter-end cutoff. Preserve fiscal dates, published
dates, source evidence, margin basis and overlap. Absolute peer margins
are never copied into MUSA's estimate.

The joint four-input model adds Casey's and Couche-Tard surprises to clean
diesel and revenue gap. Requiring complete peer inputs leaves **seven**
held-out quarters (2024Q4–2026Q2), below the eight-test promotion minimum:

- Production on those seven: **2.387¢ MAE**.
- Two-input joint model on those same seven: **2.089¢**.
- Four-input model including both peers: **2.294¢**.

Adding peers did not improve absolute-error accuracy in this implementation,
although directional accuracy improves 71.4% → 85.7% versus production.
Training eligibility differs between the two- and four-input models because
of peer availability; this is an operational matched-target comparison,
not an isolated causal attribution to peer features.

Remove the peer model's biggest-benefit quarter, 2026Q2, and production
beats it: **1.684¢ versus 1.806¢**. Preserve this negative finding.
Peers remain contextual evidence, not grounds for a production adjustment.

## Scope and governance

Risk flags and qualitative disclosures are confidence/context objects, not
numeric forecasts to average. Supply/RIN and all-in estimates have a different
target basis. Blocked replays and futures without a retail-response method
have no valid margin estimate. The failed negative-output state-space model
is not an eligible ensemble component. Earlier failed timing/weekly models
are not added through an unbounded feature-subset search.

Historical EIA/peer market inputs are current-vintage. Date-only disclosure
availability is conservative, not intraday proof. Original peer-release byte
identity, acquisitions and exposure remain limitations documented in the
individual peer reports. All archived component targets and available
production predictions are checked against the same MUSA baseline.

All inputs and code are hashed and copied before fitting. v1 is a retained
development run; v2 adds baseline consistency, peer availability and explicit
same-quarter peer comparison checks without changing candidate definitions.
All 148 tests pass, including diesel-break boundaries, delayed outcomes,
held-out target invariance, peer publication/overlap and fixed blend coverage.

```bash
.venv/bin/python -m musa_nowcast.combined_challengers --out data/combined_challengers/NEW_UNIQUE_RUN
.venv/bin/python -m pytest -q
```

Conclusion: combination is possible and sometimes reduces error, but adding
more signals is not reliably better. Freeze these findings. If carrying
forward a candidate, treat the small diesel/revenue-gap combination as a
prospective shadow only; retain production as champion. No current-quarter
forecast was altered or newly scored by this exercise.
