# Free information tests: October 8, 2026

Production remains unchanged. No paid data, trial enrollment, automated pump-price collection or source-access bypass was used. No new probability model or fitted combination was introduced.

Canonical [suite results](../data/free_information_suite/2026-10-08_v3/results.json) distinguish a new rack diagnostic, rerun regional-context experiments, existing historical experiments and blocked evidence channels. This is developmental current-vintage research, not strict PIT or prospective validation. The history has already informed earlier research.

## New free rack-price experiment

Downloaded the official [US regular-gasoline rack sales price by refiners](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=M&n=PET&s=EMA_EPMR_PRG_NUS_DPG) XLS, preserving raw bytes, SHA-256 and capture metadata. There are monthly observations January 1994–March 2022, excluding taxes. EIA's XLS labels months with the 15th: these were normalized to month-start period identifiers, **not publication dates**.

Before scoring, froze one mechanical candidate: production minus 0.5 times the year-over-year change in the national rack-minus-existing-regional-spot basis. Equal monthly means use all three current and prior-year months; there is no gap fill, extrapolation, parameter fitting or tuning on the known misses. The national refiner average is not local terminal pricing, MUSA's acquisition costs or an observed company mix.

The diagnostic covers 27 archived tests, reported separately:

- **18 earlier low-margin quarters:** MAE 2.598→3.699 cents; RMSE 3.431→4.329; >=5-cent errors 3→4.
- **Four 2020 transition quarters:** MAE 7.726→8.518; RMSE 9.889→11.312.
- **Five modern quarters, 2021Q1–2022Q1:** MAE **4.635→6.505**, RMSE **4.789→7.118**; >=5-cent errors 3→4.

Among the three modern original large misses covered, MAE worsens **5.556→7.484 cents**. Forecasts, retail cents per gallon:

- 2021Q2: actual 21.8; production 26.981; rack-adjusted 30.202 — worse.
- 2021Q4: actual 25.5; production 19.191; rack-adjusted 19.950 — modestly better.
- 2022Q1: actual 23.3; production 28.479; rack-adjusted 31.798 — worse.

The two ordinary modern quarters' MAE worsens 3.254→5.038, with one new large error. No later rack forecasts were manufactured: the series stops at March 2022, so Q3 2022/Q3 2023/Q2 2026 cannot be tested with this source.

Historical monthly release vintages have **not** been verified. Full-quarter monthly data can arrive after quarter-end; these are explanatory same-period tests, not feasible historical nowcasts at an asserted quarter-end cutoff. A strict PIT and live rack test remains blocked. This specific national monthly correction fails; that does not establish that correctly matched local daily rack data would be useless.

V1 stopped at parsing the source's day-15 month labels before scoring. V2 corrected period normalization. V3 preserves identical numeric tests while adding explicit diesel-break quarantine and pump-panel readiness validation. No parameter selection occurred between versions.

## Regional context and fuel-basis experiments

Reran the unchanged regional stocks/utilization and lagged revenue-gap experiments against the previously archived inputs, with publication-filtered training outcomes and no parameter changes. Historical market/supply publication vintages remain unverified.

- **Stocks/utilization, 14 matched quarters:** MAE 2.303→2.509; RMSE 3.120→3.296. Failed existing gate. This is not direct acquisition-cost evidence.
- **Prior-quarter revenue gap, same 14:** MAE 2.303→2.207; RMSE 3.120→2.971. Small improvement, negative confidence lower bound, failed gate.
- **Existing all-grade experiment, all 22 modern quarters:** MAE 3.133→3.103; RMSE 4.019→3.998; large-error count remains six. This archive was summarized, not rerun as a fresh trial.
- **Existing margin-floor/cost-volume experiment, 14:** MAE 2.303→2.309, not an improvement. Also an existing experiment, not a new trial.
- **Clean diesel reference, nine matched quarters:** MAE 2.188→2.013; RMSE 2.968→2.777; failed gate. It tests only one original large miss, Q2 2026. Do not claim broad tail coverage.

The older apparently stronger 14-quarter diesel result is explicitly **quarantined** because survey-break-crossing rows contaminated its training. The suite retains it for provenance, not as evidence of improvement. The cleaned experiment excludes crossing rows from both training and scoring, reducing coverage. No positive result is silently selected from incompatible samples.

The regional and lagged-gap tests cover Q3 2023 and Q2 2026 among the six original large misses, not all six. Missing early residual training cannot be fixed by inserting later outcomes.

## Company disclosures: all three existing scored mechanical cases

Checked forecast-to-score SHA-256 links and reproduced the weighted-average arithmetic of **all three** existing cases, not just the successful Q2 2025 example:

- **2023Q1:** shadow 15.967; shadow absolute error **7.233**, versus production **1.138** — substantially worse.
- **2024Q2:** shadow 23.787; shadow error **5.913**, versus production **6.336** — slightly better.
- **2025Q2:** shadow 28.898; shadow error **0.302**, versus production **4.115** — substantially better.

Q1 2023 and Q2 2024 use explicitly approximate management commentary. All three use `PIT_MODELLED_GALLON_SHARE`, not observed company gallons. They remain `RETROSPECTIVE_MECHANICAL_REPLAY`, not prospective validation. Different disclosure cutoffs and observed shares are retained; these scores are not compared against quarter-end production predictions. Reproduction of archive links/arithmetic does not independently audit every original historical source.

The January 2023 case illustrates that a company anchor cannot rescue a badly forecast remainder. Its archived remaining-period estimate is only 14.442 cents; the disclosed January reference is approximately 19 cents, with only about a third of gallons covered. The quarterly-to-shorter-period calibration assumption remains unvalidated.

The original 19 pending disclosure source audits remain unresolved. The newly discovered approximate April 2026 retail passage also remains pending period/precision adjudication, with no registered live gallon share or remaining-period forecast. It was not silently converted into a scored case. This run does **not** claim 22/22 disclosure audit completion or a backtest of every historical disclosure.

## Channels that cannot honestly be backtested yet

- **MUSA/competitor pump panel:** existing readiness validator rejects the empty station registry. Zero verified fixed pairs and no paired historical price observations. Manual-only intake is available; collection requires actual station identity, timestamped raw evidence, grade, payment and rewards basis. No invented prices or automatic source collection.
- **Daily retail plus daily wholesale:** daily wholesale archive exists, but historical matched daily retail coverage is missing. AAA automation remains disabled pending permission review; one retail capture day is not a historical margin backtest.
- **Continuous local rack prices:** no free licensed continuous dataset established; commercial subscription/trial was not acquired.
- **Company weekly regional gallons and supplier invoices:** not obtained. Public quarterly totals and regional demand proxies do not supply these company inputs.

To unblock the pump panel, supply permitted timestamped MUSA/nearby-competitor observations and station identities, or an explicitly authorized data source. To unblock a historical rack nowcast, obtain dated publication snapshots and a preregistered method for handling the reporting lag. No permissions were inferred from public visibility.

## Conclusion

No tested channel establishes a reliable improvement on the six large misses. The new broad rack adjustment makes its covered modern cases worse; regional supply context fails; all-grade changes little; cleaned diesel and lagged gap offer limited, failed-gate evidence. The company-anchored machinery has mixed historical results, emphasizing the importance of the remainder forecast.

The information hypothesis remains narrower than "rack data will fix it": local, basis-matched evidence could still be valuable, but this free national monthly substitute is not a successful implementation. Production stays unchanged.

Reproduce with `.venv/bin/python -m musa_nowcast.free_information_suite --out data/free_information_suite/NEW_UNIQUE_RUN --regional data/free_information_suite/2026-10-08_regional_v1`. [Frozen specification](../data/free_information_suite_spec_v1.json), [implementation](../musa_nowcast/free_information_suite.py), [tests](../tests/test_free_information_suite.py).
