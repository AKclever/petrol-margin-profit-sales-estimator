# Casey's period-matched peer surprise pilot

October 7, 2026. Research only. Production and the earlier frozen 29.54-cent
Q3 stack remain unchanged. No paid data was used.

## Frozen experiment and evidence

Specification: `data/peer_surprise_spec_v1.json`, written before fitting.
Executable: `python -m musa_nowcast.peer_surprise --output <new-directory>`.
Completed archive: `data/peer_surprise/2026-10-07_v2/result.json` and its
`sources/` and `inputs/` directories. V1 is retained as an incomplete archive:
the calculations finished, but flattening two input paths caused a snapshot
filename collision. V2 corrects snapshot naming; numeric results are identical.

The SEC submissions list locates Item 2.02 filings. Each captured cover must
explicitly name the earnings period-end. Filing date is a conservative public
availability date; report date is not used. Verified 29 Casey's periods and 29
MUSA periods. MUSA Q2 2022 remains unresolved by this specific cover-text
parser and is excluded, not classified as having no disclosure. This does not
resolve or modify the separate 22-quarter partial-disclosure audit.

Each Casey's forecast uses the existing seasonal/change model and at least
eight earlier public targets. Its surprise is actual minus that expanding
forecast, not its absolute margin or year-over-year change. For each MUSA
quarter, select the latest already-public peer period with positive calendar
overlap. Fit a one-feature ridge to at least eight earlier, already-public MUSA
out-of-fold residuals, with alpha 2 and 50% correction shrinkage. No parameter
was tuned after seeing these results. Publication eligibility is enforced, but
historical market vintages, all original target values, static weights and
historical forecast timestamps are NOT PIT verified. This is not prospective
validation or a fully PIT historical backtest; the hypothesis was also informed
by the same historical misses.

## Results

Eligible scored quarters: 11, Q4 2023 through Q2 2026. On exactly these rows,
production MAE is 2.0109 cents and peer-shadow MAE is 1.7905 cents, a 10.96%
reduction. RMSE falls from 2.7364 to 2.4309 cents. Direction accuracy rises from
81.8% to 90.9%.

Recent eight MAE barely moves: 2.1535 to 2.1431 cents, a 0.48% reduction.
Mean paired benefit is 0.2204 cents with a paired 95% lower bound of -0.2538.
The existing promotion gate fails. Do not compare 1.79 with the full-history
3.13-cent production MAE: they cover different quarters. Most early large
misses are not in the evaluation sample, so this does not establish tail-risk
forecasting ability. Q2 2026 error falls from 6.60 to 5.18 cents, but Q2 2025
gets worse, from 4.49 to 4.88 cents. Retain both examples.

## Q3 2026 research checkpoint

Casey's May-July 2026 actual is 47.8 cents versus the expanding-model estimate
42.7021, a +5.0979-cent surprise. The September 8 SEC filing was available
before the September 30 MUSA reference cutoff. It overlaps only July: 31
calendar days, not 31 days of observed MUSA gallons.
[Original release](https://www.sec.gov/Archives/edgar/data/726958/000072695826000084/q1fy2027earningspressrelea.htm).

The pilot adds 1.6667 cents to the 28.94-cent production rerun on identical
current inputs, producing a **30.6067-cent retail shadow**. This is not all-in,
not a replacement for the earlier 29.54 frozen production checkpoint, and not
evidence that August-September margins were strong. Actual and scoring remain
blank. Couche-Tard remains a separate contextual peer pending a consistent
historical US company-operated target series; it was not quietly pooled here.

## Would deeper accounting work help?

Possibly, especially to identify a *quantified retail-specific* adjustment or
different cost basis in a miss quarter. A useful next documentary scope is the
six miss-quarter 10-Q inventory notes and results calls, keeping retail,
supply/RIN and total accounting contribution separate. The previous scoped
review did not prove that no retail adjustments ever existed.

There is still an identification limit: petroleum sales include retail and
wholesale, aggregate COGS includes shipping, and inventory reporting is an
accounting basis rather than a weekly purchase-price series. The annual report
separates retail and wholesale revenue but not matching weekly retail costs.
[2025 annual report](https://www.sec.gov/Archives/edgar/data/1573516/000157351626000090/musa-20251231.htm).

Backing retail costs out of revenue using the already-reported retail margin
would be circular, not an independent predictor. A year-end LIFO reserve level
is not a quarter's inventory expense; do not divide it by gallons and call it a
margin correction. Post-results accounting explanations cannot be treated as
quarter-end information. Deeper review is useful diagnosis, but improved
forecast accuracy must be demonstrated separately.
