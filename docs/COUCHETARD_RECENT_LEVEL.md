# Couche Tard margin challenger results

The fixed recent-level seasonal-anchor challenger does not improve average forecast accuracy. It reduces errors in several original large-miss quarters but creates large errors in previously ordinary quarters. Keep the existing own-basis model and MUSA production unchanged.

## Geography and acquisition evidence

The current official footprint counts combine corporate stores, company-owned/dealer-operated sites, dealer-owned/dealer-operated sites and affiliates. They are not weights for the US company-operated fuel-margin target. They are dated July 19, 2026 and cannot be backfilled into earlier forecasts. [Official footprint](https://corporate.couche-tard.com/where-we-operate).

The scoped check captures that page and the annual-report index, and inherits the existing original-release evidence. It does not complete an exhaustive annual-report/state-store reconstruction. No dated, target-matched historical regional exposure series was verified, so geographic reweighting remains blocked. Equal East Coast/Midwest/Gulf Coast weights are retained as provisional proxies; western exposure remains omitted rather than silently assigned to another region.

The 50-quarter release-level audit preserves named acquisition/divestiture context in both current and prior-year releases. Names include CST, Holiday, MAPCO, GetGo, Kroger and TotalEnergies. A new mention is not proof of a closing date, a US company-operated perimeter break or a quantified retail-margin effect. The audit is retrospective documentary context, not a predictive feature or an exhaustive transaction register.

For example, the fiscal Q1 2026 release distinguishes GetGo's June 28, 2025 closing from regulatory disposals and describes competitive pressure in southern US markets. Its broader US road-fuel margin differs from the separately tabulated company-operated before-payment-fee target used here. Those definitions are not pooled, and acquisition revenue or EBITDA contributions are not converted into cents-per-gallon margin corrections. [Original release](https://corporate.couche-tard.com/2025-09-02-ALIMENTATION-COUCHE-TARD-ANNOUNCES-ITS-RESULTS-FOR-ITS-FIRST-QUARTER-OF-FISCAL-YEAR-2026).

## Frozen challenger

With historical geographic reweighting unsupported, one alternative was frozen before scoring in `data/couchetard_specific_spec_v1.json`: retain the existing market-model forecast and add half the average of the last four previously published fiscal year-over-year margin changes.

This changes the seasonal anchor to account for the recent reported margin level, without fitting a new coefficient. Both members of each change pair must be published strictly before the target fiscal period end; the current observation must end before the target starts. Neither the target outcome nor a same-day release enters its own adjustment.

The target stays US company-operated fuel margin before electronic-payment fees. Actual fiscal labels and 12/13/16/17-week periods are preserved. The comparator and challenger share the same archived market model, geographic proxies and full training history; there is no shorter-history confounding like the Casey RIN experiment. The recent offset can double-count persistence already represented by the market model; its benefit must be demonstrated, not assumed.

The specification is fixed, but this is developmental current-vintage research. Earlier-only company outcomes do not establish historical market available-at vintages or prospective validation. The existing archive's original-release basis and perimeter qualifications remain.

## Results across all 42 quarters

- MAE: existing model 4.151¢ versus challenger 4.163¢.
- RMSE: 5.778¢ versus 5.495¢.
- Correct year-over-year direction: 33/42 versus 30/42.
- Recent-eight MAE: 3.863¢ versus 3.930¢.
- Errors at least 5¢: 15 versus 13; worst error 17.837¢ versus 16.661¢.
- Original fifteen large-error quarters: MAE 8.409¢ versus 6.836¢.
- Original twenty-seven ordinary quarters: MAE 1.784¢ versus 2.679¢, including three newly large misses.

The prior-year-only baseline has MAE 5.660¢. Recent-level seasonal without the market correction has MAE 5.596¢. Both are weaker than the existing model on these rows. The challenger fails the existing promotion gate: average error and recent error are worse, direction declines and the paired-improvement lower bound is negative.

## Modern quarters and tail cost

For the 22 fiscal periods starting in 2021 or later:

- MAE: 4.153¢ to 4.478¢.
- RMSE: 5.064¢ to 5.304¢.
- Correct direction: 16/22 to 13/22.
- Errors at least 5¢: ten to nine; worst error grows from 9.742¢ to 10.702¢.
- Original ten large misses: MAE 6.859¢ to 5.655¢.
- Original twelve ordinary quarters: MAE 1.898¢ to 3.496¢, including three newly large errors.

Some large misses improve: F2023Q2 improves by 4.379¢ and F2023Q3 by 4.452¢ of absolute error. Others worsen: F2022Q3 by 1.502¢ and F2022Q4 by 0.960¢. F2027Q1 improves from a 45.144¢ archived prediction to a 46.203¢ retrospective shadow against 53.87¢ actual, leaving a 7.667¢ error. This is a scored historical outcome, not a new live estimate.

These are original-model error groups, not an activation rule. Choosing the challenger only for quarters subsequently known to be large misses would invalidate the comparison.

## Earlier periods

Sixteen earlier fiscal periods starting before 2020 worsen from MAE 2.439¢ to 2.775¢. Four periods starting in 2020 improve from 10.981¢ to 7.989¢, but remain a tiny high-error transition sample. This transition improvement does not rescue the worse modern result. All subgroup promotion gates fail; no subgroup-based selection was added.

## Artifacts and reproduction

Canonical archive: `data/couchetard_specific/2026-10-08_evaluation_v1/`. It contains immutable input copies/hashes, the scoped geography/acquisition audit, four-change source trails, predictions frozen before scoring, exclusions and full results. Original release audits are inherited from the existing evidence archive rather than claimed as a new exhaustive source review.

```sh
.venv/bin/python -m musa_nowcast.couchetard_specific \
  --out data/couchetard_specific/NEW_UNIQUE_RUN
.venv/bin/python -m pytest -q tests/test_couchetard_specific.py
```

No weights were inferred from mixed store counts, no acquisition margin correction was fitted, and no live forecast, data purchase, model promotion or GitHub push was made.
