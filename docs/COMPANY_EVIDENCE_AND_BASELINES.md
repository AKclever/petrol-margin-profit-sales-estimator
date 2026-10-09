# Five company evidence ledger and retail margin benchmarks

The local ledger now combines source-linked MUSA, Casey's and Couche-Tard history with extended ARKO and CrossAmerica history. Actual margins, guidance and business-perimeter context are separate event types. ARKO and CrossAmerica have their first chronological standalone benchmarks; neither model nor any new peer transfer has been promoted. MUSA production remains unchanged.

## Historical coverage

There are 14 reviewed ARKO quarters and 14 CrossAmerica company-operated quarters, covering Q1 2023 through Q2 2026. The extension captured 19 additional releases and normalized 18 of them. CrossAmerica Q4 2022 remains unresolved because the company-operated target could not be identified uniquely under the parser's basis checks. It was not replaced with a combined retail margin or a later comparative disclosure.

ARKO's target excludes the GPMP fixed margin or fee. CrossAmerica's target is company-operated retail margin before credit-card fees, not the combined retail-segment or wholesale margin. The companies are benchmarked separately. No geographic weights, acquisition corrections or margin-basis conversions were invented. Older ARKO footnote numbering changed, but the source definition of the selected retail row was checked explicitly.

Raw HTML, source hashes, publication dates, capture dates and normalized evidence are retained. Existing historical records were imported with a note distinguishing their current import time from original publication. The resulting archive is publication-filtered historical research, not prospective validation or proof of contemporaneously archived source bytes.

## Ledger behavior

The canonical evaluation contains 178 events across MUSA, CASY, ATD, ARKO and CAPL. Each event retains company, kind, quarter, target basis, publication date, capture timestamp, source locator and source hash. Context events retain passages but authorize no numeric correction. Guidance events do not enter actual-margin training.

The ledger is append-only and hash-chained. Identical events are idempotent. A conflicting event with the same company, kind, quarter, basis and publication date is rejected rather than overwritten; corrections require an explicitly distinguished version. Reads validate the hash chain, and writes use a file lock and filesystem synchronization. Date-only cutoffs exclude same-day events.

ARKO's three previously reviewed quarterly assumptions are retained separately from its August 7, 2026 full-year assumption of 45.5–47.5¢. The latter is labeled `FULL_YEAR_NOT_Q3`; it does not become a Q3 estimate or a quarterly training actual. [ARKO Q2 2026 release](https://www.arkocorp.com/news-events/press-releases/detail/213/arko-corp-reports-second-quarter-2026-results).

This is a local evidence and benchmark workflow, not a deployed earnings monitor. Appending an event does not automatically change production or trigger cross-company forecasts.

## Frozen benchmarks

The specification was saved before the first scoring run. Each target uses only same-company, same-basis quarterly outcomes published strictly before its quarter-end cutoff and covering periods ending before its start. At least eight earlier targets and a published prior-year seasonal anchor are required. The three estimates are:

- Seasonal: prior-year same-quarter margin.
- Recent level: mean of the latest four published quarterly margins.
- Blend: equal weights on seasonal and recent level.

All three are scored on identical eligible quarters. Predictions and training provenance were saved before attaching scoring outcomes. No weight, minimum-history requirement or error threshold was selected from performance. These are simple target-history benchmarks, not EIA-calibrated company nowcasts.

## Matched results

Each company has six test quarters, Q1 2025 through Q2 2026. Errors are cents per gallon, and a large error means absolute error at least 5¢.

ARKO:

- Seasonal MAE 4.43¢, RMSE 5.26¢, two large errors.
- Recent-level MAE 3.55¢, RMSE 3.76¢, two large errors.
- Equal blend MAE 3.74¢, RMSE 4.37¢, one large error.

The recent-level estimate has lower average error, but ordinary quarters worsen by 0.53¢ on average relative to seasonal. The blend improves ordinary-quarter error by 0.11¢ and reduces large-error frequency from two of six to one of six. This illustrates why MAE alone is insufficient for selection.

CrossAmerica:

- Seasonal MAE 6.13¢, RMSE 7.20¢, three large errors.
- Recent-level MAE 3.95¢, RMSE 5.25¢, two large errors.
- Equal blend MAE 4.76¢, RMSE 6.02¢, three large errors.

CrossAmerica's recent-level benchmark improves ordinary-quarter error by 2.00¢ on average. However, it still misses Q4 2025 by 9.00¢ and Q2 2026 by 7.85¢. These peers are not demonstrably easy forecasting targets.

Leave-one-out checks score frozen predictions without refitting. The worst remaining average improvement versus seasonal is 0.095¢ for ARKO recent level, 0.347¢ for ARKO blend, 1.83¢ for CrossAmerica recent level and 1.01¢ for CrossAmerica blend. Their positive mean gains do not disappear when any single test quarter is removed, but six observations are too few for reliable generalization. Repeatedly researched history and business-perimeter changes remain important limitations.

## What is ready and what remains

The evidence ledger, additional same-basis history, three standalone benchmarks and reproducible scoring are implemented. The existing Casey's → MUSA shadow and official production model remain separate and unchanged.

There is no validated ARKO or CrossAmerica peer-surprise transfer, no automatic five-company propagation, and no new live Q3 point forecast. A next experiment can compare these frozen baselines against small market calibrations on identical dates, then test whether their unexpected margins add information before a recipient reports. Full-year guidance, later publications and combined-segment margins must remain separate.

## Reproduction and local ingestion

The canonical output is `data/company_baselines/2026-10-08_evaluation_v3`, including `events.jsonl`, `reviewed_targets.json`, `frozen_predictions.json`, input snapshots and `results.json`. Earlier runs are preserved. The benchmark specification is `data/company_baseline_spec_v1.json`.

```bash
.venv/bin/python -m musa_nowcast.company_baselines --out data/company_baselines/NEW_EVALUATION
.venv/bin/python -m musa_nowcast.company_evidence_ledger --ledger PATH_TO_LEDGER --event PATH_TO_EVENT_JSON
.venv/bin/python -m pytest -q tests/test_company_baselines.py
```

An evaluation refuses to reuse an existing output directory. Its captures are fixed inputs, not a live data refresh. The ingestion command appends a supplied, validated event; it neither fetches nor infers company disclosures.
