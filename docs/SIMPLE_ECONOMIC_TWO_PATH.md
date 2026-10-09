# Simple economic two-path experiment

Production is unchanged. The market-only challenger fails the existing promotion gate. The disclosure path reproduces an existing historical mechanical research result; it is not a newly validated forecasting strategy.

## Frozen design

[Specification](../data/simple_economic_spec_v1.json) was frozen before this experiment's scoring. The history has already informed previous research, so this is **DEVELOPMENTAL_CURRENT_VINTAGE_NOT_PIT_VALIDATION**, not prospective preregistration. One candidate, no parameter grid or activation based on known misses.

**With verified numeric retail disclosure:** mechanically combine disclosed low/central/high retail margins with an explicit observed gallon share and an independently archived retail remaining-period forecast. A separately opted-in PIT-modelled share is supported, with method version, as-of and input hashes. The original strict replay remains unchanged and rejects modelled shares. Missing evidence blocks; no calendar fraction or conversion from all-in guidance.

The research router checks contiguous observed/remaining periods covering the quarter, matching retail basis, source verification flag, input hashes, finite values and share bounds. Disclosure and gallon-share information cannot postdate the remaining forecast's information cutoff; production and remaining forecasts must have the same cutoff. Intraday timestamp checks retain time zones. Evidence metadata is a caller contract, not automatic verification of raw sources; this does not authorize automatic live disclosure assimilation.

**Without disclosure:** construct regional weekly retail minus a two-week averaged wholesale spot-cost proxy. Preserve sequence through the existing asymmetric rising-squeeze/falling-capture states with fixed 0.5 decay. Use two explanatory features: weighted spread and weighted capture minus squeeze. Fit an intercept and up to two nonnegative slopes, standardized ridge alpha=2, using the latest eight published feature-complete quarters. There is no prior-year margin anchor or fitted residual correction.

Eight prior quarters are required, including earlier low-margin/2020 transition observations for early modern forecasts. This is explicitly a rolling recent-level experiment, not a claim that all regimes are exchangeable. Early regime transitions are a limitation.

Weights are archived current-vintage EIA national demand times regional store weights: **a volume proxy, not company-observed gallons**. Weekly allocations are inferred, not observed MUSA weekly margins. Existing final partial-week carry rules remain explicit; internal gaps block. This experiment does not recreate historical market publication vintages. The linear weekly allocations reconcile exactly to the quarterly prediction.

## Market-only results

Canonical archive: [2026-10-08_v2 results](../data/simple_economic/2026-10-08_v2/results.json). V2 adds timestamp and routing safeguards; the forecast formula and numeric results are identical to V1, not a second parameter trial.

There are **21 matched modern quarters**. 2021Q1 is blocked for insufficient feature-complete published training quarters; all six original large misses are covered.

- MAE: production **3.122 cents**, challenger **4.327 cents**.
- RMSE: production **4.048 cents**, challenger **5.943 cents**.
- Absolute errors >=5 cents: **6/21 to 7/21**.
- Original six large-miss MAE: **6.625 to 6.926 cents**; RMSE **6.802 to 8.581 cents**.
- Original 15 ordinary-quarter MAE: **1.721 to 3.288 cents**. Four become new large misses.
- Recent-eight MAE: **2.154 to 2.947 cents**.
- Worst absolute error: **9.792 to 17.334 cents**.

Predictions for the original six misses, retail cents per gallon:

- 2021Q2: actual 21.80; production 26.98; simple economic 17.62.
- 2021Q4: actual 25.50; production 19.19; simple economic 23.67.
- 2022Q1: actual 23.30; production 28.48; simple economic 18.18.
- 2022Q3: actual 39.30; production 29.51; simple economic 21.97.
- 2023Q3: actual 28.70; production 35.38; simple economic 24.22.
- 2026Q2: actual 35.10; production 28.50; simple economic 26.48.

Four of the six improve slightly or substantially, but the two deteriorations outweigh those gains. Counting only improvements or only the reduction from six to three large errors within the original large group would conceal the severe 2022Q3 miss and four new ordinary-quarter large errors.

The Q3 2026 post-path research shadow is **26.985 cents retail**. No actual is present, and this is not a prospective forecast or replacement for the frozen production checkpoint. In this fit the sign constraint selects only the sequence coefficient; the spread slope is zero. Do not interpret the shadow as a independently verified current acquisition-cost estimate.

## Mechanical disclosure reproduction

The existing Q2 2025 archived forecast was checked against its linked score SHA-256 and its weighted average recomputed. This uses the **previously frozen remaining-period methodology**, not the newly tested two-feature calibration.

- Disclosed April–May retail margin: **29.6 cents**.
- Explicit PIT-modelled observed gallon share: **65.9731%**, using `EIA_WEEKLY_DEMAND_52_WEEK_SEASONAL_PROXY_V1`; not company-observed gallons.
- Archived remaining June forecast: **27.5363 cents**.
- Recomputed mechanical shadow: **28.8978 cents**.
- Archived production forecast at the same historical cutoff: **33.3154 cents**.
- Actual: **29.2 cents**.
- Shadow absolute error: **0.3022 cents**, production absolute error **4.1154 cents**, improvement **3.8132 cents**.

Role remains **RETROSPECTIVE_MECHANICAL_REPLAY**. Strict replay remains `BLOCKED_MISSING_OBSERVED_COMPANY_GALLONS`. This is one favorable previously archived research example, not new historical proof, and not pooled into the market-only backtest. The remaining-period methodology transfers quarterly coefficients/seasonality to a monthly target, an explicit unvalidated assumption. This run checks the archived arithmetic and forecast-to-score link; it does not independently re-audit every underlying historical source.

## Conclusion and reproduction

The disclosure mechanism is useful machinery when its evidence exists. The simple market-only formulation tested here is not an improvement. It cannot reliably recover the exceptionally high company margins from the available proxies, and merely removing the prior-year anchor creates other errors. Preserve it as a failed research challenger; do not tune weights on these six misses.

Run `.venv/bin/python -m musa_nowcast.simple_economic --out data/simple_economic/NEW_UNIQUE_RUN`. The output includes frozen source copies and hashes, predictions frozen before scoring, training-quarter identities and coefficients, tail/ordinary metrics, Q3 weekly allocations and the separate archived disclosure example. Use `route_forecast` in [the module](../musa_nowcast/simple_economic.py) for explicit evidence-bearing research routing; it is not wired into production or scheduled live forecasts.

[Tests](../tests/test_simple_economic.py) cover arithmetic, evidence blocks, basis mismatch, modelled-share opt-in, intraday future-information rejection, sign constraints and held-out-outcome independence.
