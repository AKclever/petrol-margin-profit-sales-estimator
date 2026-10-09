# Historical wholesale, peer and perimeter evidence

The scoped evidence extension is complete. No free matched-terminal rack history was verified for the six largest modern production misses. The expanded peer challenger modestly improves modern average error, but does not reliably solve the large misses or pass the existing promotion gate. Production remains unchanged.

Canonical artifacts: `data/historical_evidence_extension/2026-10-08_review_v3/`. Specification: `data/historical_evidence_extension_spec_v1.json`, frozen before scoring. Earlier capture/review directories remain intact; v3 adds two original Couche-Tard releases missed by the initial title search, not a retuned model.

## Historical local wholesale coverage

Eight raw EIA workbooks were captured, hashed and normalized: all-seller regular-gasoline rack (PRA) and refiner resale (PWG), separately for East Coast, Midwest, Gulf Coast and Texas. Check the observation dates, not the webpage's last release date.

- All four checked PRA rack series run January 1994 through February 2011. None covers any of the six modern large misses. These are monthly regional/state aggregates, not terminal quotes. [EIA rack table](https://www.eia.gov/dnav/pet/pet_pri_allmg_a_epmr_pra_dpgal_m.htm).
- All four PWG refiner-resale series run January 1983 through March 2022. Complete-quarter coverage exists for Q2 2021, Q4 2021 and Q1 2022 only. These are resale prices, not rack quotes or MUSA delivered acquisition costs. They provide regional context, not verified historical rack-minus-spot basis. Today's downloaded histories are not verified original vintages. [EIA resale table](https://www.eia.gov/dnav/pet/PET_PRI_REFMG_A_EPMR_PWG_DPGAL_M.htm).
- OPIS advertises historical location-specific rack products, but a free downloadable archive matching the required locations and quarters was not verified. No subscription or trial was purchased. [OPIS pricing](https://www.opis.com/product/pricing/).
- California's public wholesale disclosures concern a different market; no justified MUSA three-region mapping was established. Its raw capture failed and remains `UNRESOLVED_FETCH_FAILED`, not a negative finding. USDA ethanol/futures information is not local gasoline rack history; its attempted raw capture also remains unresolved. [California disclosure program](https://www.energy.ca.gov/data-reports/energy-almanac/californias-petroleum-market/california-oil-refinery-cost-disclosure), [USDA report entry](https://mymarketnews.ams.usda.gov/viewReport/3198).

Result: `BLOCKED_NO_FREE_MATCHED_TERMINAL_HISTORY_VERIFIED`. Stop this scoped rack experiment without fitting a substitute correction. This is not a claim that no free local data exist anywhere. The usable resale observations remain archived separately. Every successful capture retains the URL, search/capture timestamps and SHA-256; unsuccessful captures retain their failures.

## Older comparable peer evidence

Reconciled 24 older Casey's quarters and 20 older Couche-Tard quarters against original release text, publication dates and fiscal period endpoints. Casey's parsing rejects year-to-date, annual and guidance figures; prepared-remarks duplicates that cannot support a unique current-quarter target remain unresolved, not assumed to contain no disclosure. Three Couche-Tard releases with atypical titles were added to the original discovery set.

Preserved distinct target definitions:

- Casey's reported fuel margin excludes credit-card fees and includes RIN economics where disclosed. It is not MUSA retail margin.
- Couche-Tard target is US company-operated fuel margin before electronic-payment fees. Current-quarter before/fee/after figures are reconciled separately from annual columns; actual 12/13/16/17-week periods are retained. Fee and acquisition context stay with each source.
- Recent peer histories are inherited from the existing reviewed dataset; this extension independently reconciles the older releases, not every recent margin disclosure. Some inherited Casey's hashes support the dated SEC filing cover rather than a newly reviewed numeric release.

The resulting histories support 42 fiscal peer-model predictions for each company. Peer surprise means reported margin minus an earlier-trained prediction on that peer's own basis, never its absolute margin averaged into MUSA. Couche-Tard equal regional weights remain a provisional proxy, not verified outlet weights.

The frozen challenger uses only the latest published overlapping peer period strictly before both MUSA quarter-end and MUSA's reporting date. Same-day publication is excluded because only dates are verified. It records overlap days and never treats differing fiscal periods as identical calendar quarters. Eight earlier published MUSA residuals with both peer inputs are required within the same regime; ridge penalty 10 and half-strength correction were fixed before evaluation. This conservative quarter-end checkpoint does not exploit later peers that might become available before MUSA reports.

**Important limitation:** company publication ordering is enforced, but underlying market inputs are current-vintage history, not fully verified historical available-at snapshots. Therefore this is `DEVELOPMENTAL_CURRENT_VINTAGE_PUBLICATION_FILTERED_NOT_STRICT_PIT`, not a proven investable backtest or prospective validation.

## Peer results

Fourteen scoreable modern quarters, Q1 2023–Q2 2026, compared on identical rows:

- MAE: production 2.303¢, peer shadow 2.155¢.
- RMSE: 3.120¢ versus 3.026¢.
- Directional accuracy: 12/14 versus 10/14.
- Errors at least 5¢: two versus two; worst error 6.683¢ versus 6.787¢.
- Paired improvement lower 95% normal-approximation bound: -0.039¢. The existing promotion gate fails; this statistic is not adjusted for the project's multiple research experiments.
- Original large-error subset: two scoreable quarters, MAE 6.644¢ versus 6.372¢. Ordinary twelve: MAE 1.579¢ versus 1.452¢.

Individual modern large misses:

- Q3 2023: production 35.383¢, peer shadow 35.487¢, actual 28.7¢. Absolute error worsens from 6.683¢ to 6.787¢.
- Q2 2026: production 28.495¢, peer shadow 29.142¢, actual 35.1¢. Absolute error improves from 6.605¢ to 5.958¢, still a large miss.
- Q2 2021, Q4 2021, Q1 2022 and Q3 2022 now have published overlapping peer pairs, but remain blocked for insufficient earlier same-regime residual training. Older low-margin observations are not silently pooled to make them scoreable.

Two earlier low-margin quarters become scoreable, Q3/Q4 2019: MAE 3.952¢ to 4.097¢ and RMSE 4.143¢ to 4.451¢, with one large error in both models. The gate fails. No 2020-transition quarter is scoreable. These small subsets do not establish generalization. Selection of original large misses is descriptive only, never an activation rule.

## Acquisition and operating perimeter

All 52 archived MUSA earnings releases were hash-verified and audited for acquisition, same-store, per-store, opening/closing and rebuild context, with targeted acquisition filings added. This is release-level data-quality work, not an exhaustive review of every filing or call and not an estimated cents-per-gallon adjustment.

QuickChek closed January 29, 2021. The closing announcement says 157 stores; subsequent filing/earnings disclosures say 156. Preserve that discrepancy as unresolved, and do not treat either number as fuel-site counts or gallon weights. [Closing announcement](https://www.sec.gov/Archives/edgar/data/1573516/000095010321001416/dp145149_ex9901.htm), [subsequent filing](https://www.sec.gov/Archives/edgar/data/1573516/000157351622000035/musa-20220630.htm).

Quarter comparability flags:

- Before 2021: pre-QuickChek perimeter.
- Q1 2021: partial acquisition quarter, not like-for-like against the prior year.
- Q2–Q4 2021: current results include QuickChek but prior-year anchors do not.
- Q1 2022: full current ownership quarter versus a partial prior-year acquisition quarter.
- Q2 2022 onward: both ownership periods include full QuickChek quarters. This resolves that particular date discontinuity, not integration, fuel-mix or organic store-mix changes.

Original release definitions include acquired sites in average-per-store metrics from the acquisition date; same-store metrics require stores operating throughout comparison periods and calendar-year eligibility. Presentation-specific exclusions must not be generalized to every quarter. Do not divide consolidated costs by a different same-store gallon denominator.

Peer perimeter context is retained too. Casey's Buchanan acquisition combined retail stores with a dealer/wholesale network; those consolidated economics are not automatically comparable pump margins. [Casey's filing](https://www.sec.gov/Archives/edgar/data/726958/000072695821000136/casy-20211031.htm). Couche-Tard's release-level acquisition context, including CST, stays alongside the margin evidence. No acquisition is assumed to explain an error without quantified same-basis evidence.

Every audited quarter retains `retail_margin_adjustment_cpg = null` and `organic_mix_stable_proven = false`. Reported retail-margin targets are not rebased. The existing MUSA disclosure taxonomy and pending source-audit states are unchanged.

## Reproduction and artifacts

Run from the repository root using a new output directory:

```sh
.venv/bin/python -m musa_nowcast.historical_evidence_extension \
  --source data/historical_evidence_extension/2026-10-08_sources_v2 \
  --additional-source data/historical_evidence_extension/2026-10-08_peer_gaps_v1 \
  --out data/historical_evidence_extension/NEW_UNIQUE_RUN
.venv/bin/python -m pytest -q tests/test_historical_evidence_extension.py
```

Artifacts include frozen input copies/hashes, wholesale coverage and normalized observations, source-level peer reviews, fiscal forecasts and exclusions, overlapping peer selections, residual training quarters, frozen shadow predictions, scored results and the 52-quarter perimeter audit. Existing output directories cannot be overwritten silently. No live forecast, probability model, data purchase or GitHub push was made.
