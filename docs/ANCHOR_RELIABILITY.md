# Recent-level anchor reliability: frozen challenger V1

Production remains unchanged. This is **DEVELOPMENTAL_CURRENT_VINTAGE_NOT_PIT_VALIDATION** research, not prospective validation or proof of investment returns.

## Rules frozen before this run

[Specification](../data/anchor_reliability_spec_v1.json) was snapshotted before evaluation. This is a within-run preregistration only: the historical errors were already explored. No thresholds, blend weights, or activation rules were chosen by optimizing the six known misses.

The alternative anchor equals the latest four published completed-quarter margins' mean plus an average seasonal offset. A seasonal offset is an earlier same-calendar-quarter margin minus the four-quarter mean ending in that earlier quarter. Use up to three prior years and require at least two complete seasonal windows.

Blend 50% prior-year anchor and 50% alternative anchor. Add the **unchanged archived production market adjustment**. No residual correction is fitted. Apply to every eligible quarter, regardless of known error, year, volatility or exceptional-anchor classification. Historical target observations must precede the target quarter and have publication dates before its quarter-end cutoff. Current target actuals are only used for scoring.

Frozen objectives: MAE, RMSE, absolute-error frequency **>=5 cents**, worst error and ordinary-quarter damage. Original large/ordinary groups are defined by production errors, never challenger errors. The alternative has not passed the existing promotion gate.

## Results

All 22 modern production-test quarters, 2021Q1–2026Q2, are covered. Modern MAE changes **3.133 to 3.113 cents**, RMSE **4.019 to 3.969 cents**, and >=5-cent errors **6/22 to 4/22**. Worst absolute error falls **9.792 to 8.821 cents**. These are modest aggregate changes, not a convincing replacement.

For the six original large misses, MAE falls **6.625 to 5.374 cents** and RMSE **6.802 to 6.039 cents**. Four improve and two worsen. Quarter-level results below are forecasts, not error magnitudes; all values are retail cents per gallon:

- 2021Q2: actual 21.8; production 26.98; challenger 22.62 — improved.
- 2021Q4: actual 25.5; production 19.19; challenger 21.32 — improved.
- 2022Q1: actual 23.3; production 28.48; challenger 31.15 — worsened.
- 2022Q3: actual 39.3; production 29.51; challenger 30.48 — improved, still a large miss.
- 2023Q3: actual 28.7; production 35.38; challenger 32.35 — improved.
- 2026Q2: actual 35.1; production 28.50; challenger 28.17 — worsened.

The price is substantial: original ordinary-quarter MAE rises **1.823 to 2.266 cents** (about 24%), RMSE **2.205 to 2.825 cents**. **2023Q2 becomes a new large miss:** actual 27.0, production 30.016, challenger 33.807. Directional accuracy declines 20/22 to 18/22; recent-eight-quarter MAE rises 2.154 to 2.774 cents. The historical confidence lower bound is negative and the gate fails.

Older regimes are not pooled into that headline. In 15 earlier low-margin quarters, MAE changes 2.393 to 2.237 and RMSE 2.928 to 2.762, with two large errors under either forecast. Across four 2020 transition quarters, MAE worsens 7.726 to 9.097; RMSE changes 9.889 to 9.604, while large errors rise two to four. The first three archived test quarters lack two seasonal windows and remain explicitly blocked.

## Exceptional-margin persistence limitation

The frozen exceptional definition compares the prior-year margin against the two older same-season margins, using a >=5-cent gap. Persistence means the eventual target remains >=5 cents from that older reference in the same direction. It does **not** mean the target repeats the prior-year peak.

Under that definition, six modern cases are PERSISTED and zero are REVERSED_OR_NORMALIZED. Thus the subgroup cannot validate reversal prediction. In particular a decline from a peak can still qualify as persistent elevated margins relative to the older baseline. The definition was not changed after seeing this result. Preserve continuous quarter-level margins for review; any narrower reversal hypothesis needs a new frozen research specification and new evidence, not a favorable relabeling.

## Company-specific pricing evidence

No verified paired station prices were obtained in this run. The company store locator, FAQ and legal pages returned HTTP 403 to the research browser on 2026-10-08. No access-control bypass or hidden endpoint was attempted. The company's searchable [FAQ](https://www.murphyexpress.com/murphyusa/faqs) says its website/app prices update approximately every five minutes; this identifies a potential live source, not permission for automated collection or a historical archive.

[GasBuddy's current terms](https://help.gasbuddy.com/hc/en-us/articles/40439396627991-Updated-Terms-of-Service-Effective-June-22nd-2026) prohibit automated price scraping using outside scripts or agents. That is not an authorized free automated substitute.

The existing manual-only intake remains available, but the station-pair registry is empty. To unblock it, obtain permitted, timestamped pump/sign observations or screenshots provided by a human, with station identity/address, grade, cash/card basis and rewards treatment, plus nearby competitor observations within 15 minutes. Hash the raw evidence and preserve observed, available and captured timestamps. These are station-panel observations, not observed company-wide gallon weights or delivered acquisition costs. Collection permission and historical coverage remain unresolved; no synthetic prices were inserted.

[Source-check trail](../data/anchor_reliability/company_pricing_checks_2026-10-08.json) records access failures and search-only leads separately. These discovery checks are not raw station-price evidence or completed permission review.

## Reproduction and archive

Run `.venv/bin/python -m musa_nowcast.anchor_reliability --out data/anchor_reliability/NEW_UNIQUE_RUN`.

[Canonical results](../data/anchor_reliability/2026-10-08_v1/results.json), frozen input copies, SHA-256 provenance and pre-scoring anchor inputs are in the run directory. [Implementation](../musa_nowcast/anchor_reliability.py) and [tests](../tests/test_anchor_reliability.py) preserve the all-quarter rule and explicit missing-evidence blocks. The existing current-vintage production backtest supplies market adjustments; this does not reconstruct strict historical market vintages. Neither the production model nor the current-quarter forecast is changed.
