# MUSA forecast error direction backtest

Casey’s peer surprise correctly identified whether MUSA’s actual retail margin would be above or below production in 15 of 22 modern quarters (68.2%). Couche-Tard’s surprise was correct in 16 of 22 (72.7%). Each identified the direction in four of the six original production misses of at least 5 cents per gallon. These are encouraging developmental results, not validated probabilities or authorization to change production.

## Frozen rules and information cutoff

The target is the sign of actual retail margin minus the unchanged production forecast, not the direction of year-over-year margin growth. Each quarter uses a quarter-end information cutoff. An eligible peer report must have been published strictly before that cutoff and cover some of the MUSA quarter. The latest eligible report supplies the sign of its own actual margin minus its own baseline forecast. Missing or numerically neutral evidence produces an abstention.

A separate comparator uses the mean of the latest four previously published same-era MUSA forecast errors. No thresholds or coefficients were optimized against the large misses. The large-error subgroup is identified only for retrospective scoring; it cannot select which live quarters receive a signal.

The specification is `data/error_direction_spec_v1.json`. The run archives input and implementation hashes, then writes predictions without target outcomes before attaching actuals for scoring. This computational separation does not undo earlier research on these quarters. Inputs are current-vintage reconstructions filtered by publication dates, not fully verified historical market vintages. The evaluation role remains `DEVELOPMENTAL_CURRENT_VINTAGE_PUBLICATION_FILTERED_NOT_STRICT_PIT`.

## Modern quarter results

The 22 quarters from 2021 onward contain 11 positive and 11 negative production errors. Always predicting above or always predicting below therefore achieves 50% on the same rows.

- Casey’s: 15 correct out of 22, or 68.2%. It identifies 7 of 11 above-estimate outcomes and 8 of 11 below-estimate outcomes.
- Couche-Tard: 16 correct out of 22, or 72.7%. It identifies 9 of 11 above-estimate outcomes and 7 of 11 below-estimate outcomes.
- Recent MUSA residuals: 8 correct out of 18 calls, or 44.4%, with four abstentions. This comparator does not improve on the constant-direction baselines.

On the 15 rows where a historical majority-direction comparator can issue a call, that comparator achieves 40%, versus 80% for either peer signal. This is a coverage-matched comparison, not a comparison of different sample sizes.

The descriptive Wilson intervals are approximately 47–84% for Casey’s and 52–87% for Couche-Tard. They do not account for serial dependence or repeated experimentation. Removing any single scored quarter leaves Casey’s accuracy between 66.7% and 71.4%, and Couche-Tard’s between 71.4% and 76.2%; this is a sensitivity check without refitting, not cross-validation.

## Original large misses

The six misses are balanced between three above-production and three below-production outcomes. Both peer signals achieve four correct calls, or 66.7%, versus 50% for either constant-direction baseline.

- 2021 Q2: production was 5.18 cents too high. Both peers correctly called below.
- 2021 Q4: production was 6.31 cents too low. Couche-Tard correctly called above; Casey’s called below.
- 2022 Q1: production was 5.18 cents too high. Both peers incorrectly called above.
- 2022 Q3: production was 9.79 cents too low. Both peers correctly called above.
- 2023 Q3: production was 6.68 cents too high. Casey’s correctly called below; Couche-Tard called above.
- 2026 Q2: production was 6.60 cents too low. Both peers correctly called above.

The six-quarter sample is too small to establish reliable tail direction. Its descriptive accuracy interval is approximately 30–90%. The mean of recent MUSA residuals gets only one of its four eligible large-miss calls right. Neither peer signal estimates the size of a miss merely by identifying its sign.

## Older history and implications

Across all eras, Casey’s is correct in 20 of 40 calls (50%), and Couche-Tard in 21 of 37 (56.8%). Modern performance should therefore not be assumed to persist across older margin regimes. Among the 16 ordinary modern quarters, Casey’s is correct in 11 and Couche-Tard in 12; the apparent signal is not confined to the six selected misses.

For Q3 2026, already captured Casey’s and Couche-Tard reports both show positive surprises relative to their own baselines. That supports an upward hypothesis, but their fiscal periods overlap only the early part of MUSA’s quarter. It does not establish which later squeeze or capture mechanisms dominated. A 72.7% historical hit rate must not be presented as a calibrated 72.7% probability of an upside Q3 miss. Production and the bidirectional regime-risk classification remain unchanged.

The next credible test is to freeze these independent calls before new MUSA results and score them without revising the rules. Combining the two signals or converting them into a point adjustment would be a separate preregistered experiment.

## Reproduction

Run `.venv/bin/python -m musa_nowcast.error_direction --out data/error_direction/NEW_RUN` into a new directory. The completed archive is `data/error_direction/2026-10-08_v1`, including `frozen_predictions.json`, `results.json`, hashed input copies and `manifest.json`.
