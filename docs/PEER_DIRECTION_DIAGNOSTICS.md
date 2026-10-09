# Directional peer margin updates

Casey's → MUSA is the most promising direction in this developmental test. A simple fixed update outperformed the fitted transfer on the same 14 modern quarters, and its improvement survived removal of its best quarter. The reverse direction worsened Casey's estimates. Production forecasts remain unchanged.

## Frozen rules

The specification was saved before scoring in `data/peer_direction_diagnostics_spec_v1.json`. All six ordered company pairs were evaluated separately. High overlap means at least 50% of the recipient's calendar period; low overlap means positive overlap below 50%. This measures calendar exposure, not gallon share. There was no threshold search or separate fitting within overlap bins.

At the recipient's report-date cutoff, the donor must have published strictly earlier. Same-day publications are excluded because the archive only establishes dates. The latest published overlapping donor report supplies its surprise relative to its own company-specific baseline, preserving each company's margin definition.

For overlap fraction f and donor surprise s, the three estimates are:

- No update: recipient baseline.
- Fixed update: baseline + 0.5 × f × s.
- Fitted update: baseline + 0.5 × loading × f × s.

The fitted loading uses the existing ridge penalty of 10, bounds of zero to one, and at least eight earlier published training pairs in the same era. It is not refitted for overlap groups. Primary comparisons use identical fitted-eligible recipient quarters. Fixed-update coverage before fitted eligibility is reported separately, not mixed into that comparison.

Inputs and predictions were archived before attaching scoring outcomes. The implementation retains training pairs, source hashes, publication cutoffs and excluded targets. These are current-vintage, publication-filtered research results, **not strict historical PIT or prospective validation**. Historical market vintages and original baseline creation timestamps remain unverified.

## Modern matched results

MAE below is in cents per gallon, ordered **no update / fixed / fitted**. Samples cover recipient periods beginning in 2021 or later, subject to publication ordering and fitted eligibility.

- Casey's → MUSA, 14 quarters: **2.303 / 1.985 / 2.131**. All are low overlap.
- Couche-Tard → MUSA, 14 quarters: **2.303 / 2.171 / 2.235**. All are low overlap.
- MUSA → Casey's, 13 quarters: **2.649 / 2.945 / 2.762**. All are high overlap.
- MUSA → Couche-Tard, 14 quarters: **3.457 / 3.592 / 3.562**. All are high overlap.
- Casey's → Couche-Tard, 13 quarters: **3.672 / 3.427 / 3.585**. High overlap, seven quarters: 2.776 / 2.325 / 2.608. Low overlap, six quarters: 4.716 / 4.713 / 4.725.
- Couche-Tard → Casey's, four quarters: **2.577 / 3.169 / 2.942**. High overlap, two quarters: 1.252 / 2.447 / 1.987. Low overlap, two quarters: 3.902 / 3.891 / 3.897.

Overlap does not establish transfer quality. For four directions there is only one populated modern overlap bin, so they cannot support a within-direction high-versus-low comparison. The remaining bins are small. Comparing different directions would confound overlap with company, reporting order and target period.

The Casey's → MUSA fixed update passes the existing numerical screening gate on this matched sample; its fitted alternative does not. No other modern matched direction passes. Passing a screen on repeatedly researched history does not authorize promotion or establish a clean validation result.

## Dependence on exceptional quarters

Leave-one-quarter-out checks score already frozen predictions; they do not refit models.

Casey's → MUSA gains 0.318¢ MAE with the fixed update and 0.172¢ with the fitted update. Removing the largest contributor, Q2 2026, leaves gains of **0.260¢ and 0.129¢**, respectively. Both improve 11 of 14 quarters. Removing every original error of at least 5¢ leaves gains of 0.217¢ and 0.125¢. This result is not solely an exceptional-quarter effect.

Couche-Tard → MUSA also retains a positive gain after removing its best contributor: 0.083¢ fixed and 0.045¢ fitted, versus original gains of 0.131¢ and 0.068¢. Its practical benefit is smaller.

Casey's → Couche-Tard is fragile. Removing recipient F2026Q4 changes its average gain to **−0.005¢ fixed and −0.031¢ fitted**. Its high-overlap subgroup likewise loses its gain. This is not evidence for a dependable high-overlap update.

The remaining three directions already worsen matched MAE. Their best-quarter removal checks do not rescue them. All individual removals, positive-gain concentration, RMSE, directional accuracy and large-error counts are retained in `results.json`.

## Coverage and MUSA's largest misses

The fixed rule can run before eight training pairs exist. On all 22 modern MUSA quarters, Casey's reduces MAE from **3.133¢ to 2.985¢**, and Couche-Tard reduces it to **3.003¢**. These broader fixed-only results must not be compared against fitted MAE on 14 quarters.

Only two of the six original MUSA errors of at least 5¢ qualify for the modern fitted test. The fixed Casey's update reduces Q3 2023 absolute error from 6.683¢ to 5.913¢ and Q2 2026 from 6.605¢ to 5.536¢; both remain large misses. Earlier fixed-only results are mixed: Q2 2021 improves from 5.181¢ to 4.624¢ and Q3 2022 from 9.792¢ to 8.579¢, but Q4 2021 worsens from 6.309¢ to 6.603¢ and Q1 2022 from 5.179¢ to 5.660¢.

Peer evidence provides a modest lead, not a solution to MUSA's largest errors. Retain Casey's → MUSA as a separately frozen prospective shadow. Do not enable bidirectional propagation, select the best overlap subgroup after scoring, or change the official estimate from these results.

## Reproduction

Run from the repository root with a new output directory:

```bash
.venv/bin/python -m musa_nowcast.peer_direction_diagnostics --out data/peer_direction_diagnostics/NEW_RUN
.venv/bin/python -m pytest -q tests/test_peer_direction_diagnostics.py
```

Canonical archive: `data/peer_direction_diagnostics/2026-10-08_v1`. Earlier-era and full-sample results are preserved alongside modern groups; regimes are not blindly pooled for training.
