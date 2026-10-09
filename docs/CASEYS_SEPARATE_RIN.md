# Casey margin and RIN decomposition results

The Casey-specific challenger improves average error against the expanded-history model, but much of that improvement also occurs with a shorter training history and no RIN split. The independent benefit of separating RINs is small, comes with slightly worse RMSE against that control, and fails the existing promotion gate. Preserve it as a research shadow, not a validated Casey forecast or a replacement for MUSA production.

## Evidence and target

Captured 28 original SEC-referenced earnings releases or call transcripts from 29 attempted fiscal-quarter sources. One unresolved source and all unusable numeric records remain explicit. Reconciled 22 current-quarter component records, F2021Q3 through F2026Q4. Source hashes, SEC cover dates, margin/gallon table passages and numeric RIN passages are archived separately.

The target remains Casey's achieved reported fuel margin excluding credit-card fees. Quarterly gallons are taken from the first current-quarter column of the fuel table, never annual or year-to-date gallons. RIN proceeds are taken from explicitly current-quarter statements. A missing disclosure is not zero; zero is accepted only when management explicitly states that no RINs were sold during the quarter.

Casey's historical policy records RINs as a reduction in cost of goods sold when transferred. The experiment subtracts disclosed quarterly RIN proceeds divided by fuel gallons from reported margin to form an **ex-RIN proceeds proxy**. It is not an independently observed delivered cost or an exact reconstruction of all net retail economics. Released amounts and margins are rounded. [Casey's fiscal 2024 filing](https://www.sec.gov/Archives/edgar/data/726958/000072695824000046/casy-20240430.htm).

Fiscal Q1 2027 is blocked because Casey's disclosed a change to RIN accounting, including fair-value recognition. Proceeds cannot silently stand in for total recognized RIN income under that basis. The achieved 47.8¢ margin remains available to the separate reported-margin history, but is not scored in this component experiment. [Casey's fiscal Q1 2027 filing](https://www.sec.gov/Archives/edgar/data/726958/000072695826000085/casy-20260731.htm).

## Frozen challenger

Specification `data/caseys_specific_spec_v1.json` was saved before fitting or scoring. The challenger forecasts the ex-RIN proxy with the existing fiscal-period expanding YoY model: four market features, ridge penalty 2, prior-year fiscal anchor and half-strength market adjustment. It adds the arithmetic mean of the four latest previously published RIN proceeds-per-gallon observations. No target-quarter RIN figure, margin or blending volume is an input to its own forecast.

Require at least eight earlier published supported component targets and a valid fiscal prior-year anchor. Training publications must strictly predate the target period end. Market data stop at that end. Records missing evidence remain excluded instead of being filled from later annual tables. Own-target and future-market invariance tests verify these safeguards.

The archived Casey geographic weights are unchanged. This experiment does not reconstruct historical company state/gallon exposure, estimate Fikes acquisition effects, or purchase data. It preserves those limitations rather than inventing weights. Historical market prices are current vintages, so publication filtering is not strict PIT validation.

## Identical quarter comparisons

Fourteen fiscal quarters are scoreable, F2023Q3 through F2026Q4. All have start dates after January 2021; no earlier-regime performance is established by this component test.

- Existing expanded-history model: MAE 2.530¢, RMSE 2.994¢, correct YoY direction 6/14.
- RIN-split challenger: MAE 2.092¢, RMSE 2.602¢, correct direction 9/14.
- Prior-year-only baseline: MAE 2.486¢, RMSE 3.309¢.
- Recent-level seasonal baseline: prior-year margin plus half the average of the last four published YoY changes; MAE 2.613¢, RMSE 3.414¢.
- Recent-eight MAE: existing model 2.549¢ versus RIN challenger 1.950¢.

The matched existing-model predictions reproduce the archived peer predictions exactly. These 14-quarter errors must not be compared directly with the earlier 42-quarter headline error of 2.80¢.

### Same history control

After the initial results, an additional diagnostic control was added using the **same supported training quarters**, fiscal engine and market features but reported margins without separating RINs. It is not a retuned challenger or a post-result winner-selection rule.

This control has MAE 2.178¢, RMSE 2.572¢ and correct direction 7/14. The RIN split therefore adds only 0.086¢ of MAE improvement over that control, while RMSE increases to 2.602¢. About 0.353¢ of the original 0.439¢ headline MAE difference is also achieved by the no-split shorter-history control. That arithmetic demonstrates confounding, not causal attribution of the remainder entirely to RINs.

Recent-eight MAE for the no-split control is 2.092¢ versus 1.950¢ for the split. Both paired-improvement lower bounds are negative: -0.478¢ versus the original model and -0.238¢ versus the matched-history control. The promotion gate fails against both. These normal-approximation diagnostics are not adjusted for all prior research in the project.

## Large errors and ordinary quarter cost

One original error at least 5¢ is present in this eligible subset:

- F2026Q4 actual 46.9¢: existing forecast 40.413¢, RIN-split forecast 42.439¢. Error falls from 6.487¢ to 4.461¢. However the same-history no-split forecast is 42.485¢, slightly closer still; this quarter does not establish a RIN-specific advantage.
- F2023Q4 actual 34.6¢: existing forecast 36.486¢, RIN-split forecast 40.165¢. Error rises from 1.886¢ to 5.565¢, creating a new large miss.

Total errors at least 5¢ remain one versus one. Worst error falls from 6.487¢ to 5.565¢. Across the other thirteen originally ordinary quarters, MAE improves from 2.226¢ to 1.909¢, but includes that newly large error. This does not demonstrate reliable tail improvement, and older large misses without component coverage remain untested.

## Artifacts and reproduction

Canonical evaluation: `data/caseys_specific/2026-10-08_evaluation_v2/`. It contains frozen inputs/raw hashes, source reviews, component records, predictions archived before error calculation, training/RIN-source quarter trails, exclusions and all paired results. V1 is preserved; v2 adds the same-history diagnostic without changing challenger forecasts or its frozen specification.

```sh
.venv/bin/python -m musa_nowcast.caseys_specific \
  --out data/caseys_specific/NEW_UNIQUE_RUN
.venv/bin/python -m pytest -q tests/test_caseys_specific.py
```

No live Casey estimate was generated, no model was promoted, and no MUSA forecast, disclosure taxonomy or risk threshold changed. The result supports keeping this challenger for observation, not declaring a forecasting edge from 14 developmental current-vintage quarters.
