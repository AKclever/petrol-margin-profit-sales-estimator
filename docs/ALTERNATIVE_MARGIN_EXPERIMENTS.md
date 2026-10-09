# Lagged revenue gap, regional supply context and dated futures scenarios

All three requested experiments are implemented separately. Production remains
unchanged; no combination of challengers was fitted, no paid data was purchased,
and no infrastructure was deployed. The specification was saved before fitting:
`data/alternative_margin_experiments_spec_v1.json`.

## Lagged revenue-gap challenger

One feature: immediately previous-quarter accounting-basis revenue gap. The
quarter's company revenue sources must have been published before the forecast
cutoff. Train on at least eight earlier **published** production OOF residuals,
using standardized ridge alpha2 and 50% correction shrinkage. Target outcomes
and future residuals are excluded from each fit. Training-quarter lists are
archived for every prediction.

On 14 identical quarters, Q1 2023 through Q2 2026:

- Production MAE **2.3025c**, challenger **2.2071c**, a **4.14%** improvement.
- RMSE **3.1202c** versus **2.9713c**.
- Direction accuracy **85.7%** for both.
- Recent-eight MAE **2.1535c** versus **2.0148c**, a **6.44%** improvement.
- Approximate paired-benefit interval's lower end **-0.1538c**; not positive.
- Remove the best-benefit quarter, Q2 2026: MAE **1.9716c** versus **1.9609c**,
  only about **0.54%** improvement.

It **fails the unchanged promotion gate**. The +0.41 descriptive correlation
does not establish robust out-of-sample improvement. The small average benefit
is mostly one large miss. Keep the fixed model for prospective research if
desired; do not tune it against these same quarters.

Q3 2026 research output at October7: **28.9530c** versus same-input production
**28.94c**, a **+0.0130c** correction. The earlier frozen 29.54c production
checkpoint remains preserved, not overwritten by this same-input comparison.
Q3 actual/error are null.

## Regional supply-context challenger

Six official EIA weekly histories were captured with raw XLS files, SHA-256,
observation dates and first-capture availability timestamps:

- Total motor gasoline stocks: PADD1 `WGTSTP11`, PADD2 `WGTSTP21`, PADD3 `WGTSTP31`.
- Refinery utilization: `W_NA_YUP_R10_PER`, `W_NA_YUP_R20_PER`, `W_NA_YUP_R30_PER`.

Stocks are thousand barrels, including blending components; utilization is
percent. Neither measures MUSA store inventory, terminal quotes or delivered
fuel acquisition cost. [EIA stocks](https://www.eia.gov/dnav/pet/pet_stoc_wstk_dcu_r30_w.htm)
and [utilization](https://www.eia.gov/dnav/pet/pet_pnp_wiup_dcu_r30_w.htm) document
the distinct bases.

Two fixed features: year-over-year change in the weighted quarterly gasoline
stocks average, and change in the weighted refinery-utilization average.
Existing company-region weights map East Coast to PADD1, Midwest to PADD2 and
Gulf Coast to PADD3. These are provisional exposure weights, not measured
company gallons. All six series must have the exact Friday observations; no
filling or dropping a missing region. The final seven days of each quarter
are excluded conservatively. That exclusion **does not prove historical PIT
availability**; original release dates and revisions remain unverified.

The model uses the same fixed ridge/shrinkage/eight-published-residual rules.
On the same 14 targets:

- Production MAE **2.3025c**, challenger **2.5089c**: about **9.0% worse**.
- RMSE **3.1202c** versus **3.2961c**.
- Direction accuracy **85.7%** versus **64.3%**.
- Recent-eight MAE **2.1535c** versus **2.1377c**, insufficient improvement.

It **fails the promotion gate**. This particular two-feature supply correction
does not improve margin forecasts. That does not establish that regional supply
conditions have no relevance; it rejects this fixed experiment, not all possible
mechanisms. Do not interpret the residual fit as recovered acquisition costs.

Q3 research output is **29.3932c**, +0.4532c from production. Given the failed
evaluation, it is not a recommended forecast adjustment. Q3 feature values are
weighted stocks **-7.0621% YoY**, utilization **+0.2330 percentage points YoY**.

## Dated futures prototype

The supplied USDA PDF was SHA-256 checked, visually reviewed and parsed without
rewriting its original bytes. The printed report date is **October7 2026**;
settlements are **October6**. Conservative available-at is the raw verification
timestamp, not an invented original intraday publication timestamp.

Contracts run November2026-April2027. A complete Q1 2027 scenario uses January
2.9674, February2.9045 and March2.9011 USD/gallon. The explicit **equal-month
scenario** average is **$2.9243/gallon RBOB**; parallel -20c and +20c stress
scenarios yield $2.7243 and $3.1243. These are not probabilities or observed
gallon weights. This is **wholesale RBOB**, not pump prices or MUSA retail margin.

From today's calendar quarter Q4 2026, the two-quarter-ahead target is **Q2 2027**.
The supplied report lacks May and June contracts, so it returns
`BLOCKED_INCOMPLETE_CONTRACT_COVERAGE` with no quarterly number. Q4 2026 also
lacks October in the captured futures curve. At a quarter-end cutoff, a six-month
curve can cover the target two quarter-index steps ahead; at this early-Q4
checkpoint it does not. Do not silently reinterpret Q1 as two quarters ahead.

Every MUSA retail-margin field remains null:
`BLOCKED_RETAIL_RESPONSE_AND_REGIONAL_BASIS_METHODOLOGY`. A futures curve alone
does not tell us pump-price response, ethanol/blend basis, regional delivered
costs or MUSA competitive discounts. Historical forward validation also remains
blocked because a complete archive of original dated curves has not been verified.
This exercise does not improve or supersede the earlier 4.16-4.45c forward
benchmark MAEs.

## Governance and evidence

Both margin tests are **developmental current-vintage retrospective research**,
not prospective validation. Earlier outcomes have publication filters, but
original market vintages are not fully PIT-audited and these company quarters
already informed earlier hypothesis development. An approximate normal paired
interval does not address all serial dependence or research-selection effects.

Inputs/spec/code are snapshotted before evaluation. Outputs are append-only,
refusing an existing output directory. Source identifiers/units, unavailable
company features, target/future outcomes and missing supply weeks/contracts
have defensive checks. The research registry records both failed margin gates
and the futures blockers without changing the production champion.

Final outputs:

- `data/alternative_margin_experiments/2026-10-07_evaluation_v2/results.json`
- `data/alternative_margin_experiments/2026-10-07_supply_v1/manifest.json`
- `data/alternative_margin_experiments/2026-10-07_futures_v1/scenarios.json`

## Reproduction

Capture regional context:
`.venv/bin/python -m musa_nowcast.alternative_experiments capture --output NEW_SUPPLY_DIR`.

Evaluate both independent margin challengers:
`.venv/bin/python -m musa_nowcast.alternative_experiments evaluate --supply SUPPLY_DIR --output NEW_RESULT_DIR`.
The default accounting input is the all-quarter reviewed archive.

Parse a verified dated futures snapshot:
`.venv/bin/python -m musa_nowcast.futures_scenarios --pdf PDF_PATH --manifest MANIFEST_PATH --output NEW_SCENARIO_DIR`.
The manifest must include the raw SHA-256, source URL and conservative available-at.

No automatic recurring USDA acquisition was enabled: historical coverage and
original exchange-data usage terms still require verification. No hidden API,
subscription or login-only data was accessed. Results and source files are local;
these changes have not yet been pushed to GitHub.

## Recommendation

Do not change the point estimate on these results. Preserve the lagged-gap model
as a frozen prospective shadow, retain supply data as context, and prioritize
verified company-specific pump prices and a defensible retail-response/basis
methodology before interpreting futures curves as future retailer margins.
