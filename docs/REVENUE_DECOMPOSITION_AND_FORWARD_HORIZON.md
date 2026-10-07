# Revenue diagnostics and two-quarter-ahead benchmarks

Production forecast logic is unchanged. The specification was frozen before
calculating these results: `data/revenue_forward_research_spec_v1.json`.
Run with `.venv/bin/python -m scripts.run_revenue_forward_research --output NEW_DIRECTORY`.
The script refuses output-directory reuse and snapshots its specification,
code, actuals, availability ledger and market inputs before evaluation.

## Six largest production misses

Archived results: `data/revenue_forward/2026-10-07_v2/revenue_diagnostics.json`.
These quarters were selected by an earlier error audit, not by this experiment.

The revenue proxy is the prior-year reported **retail-only** petroleum revenue
per gallon plus the change in the existing weighted EIA retail basket. Q4
retail revenue is annual revenue minus nine-month revenue, separately for both
years. Total petroleum revenue, including wholesale activity, is never used.

All figures below are cents per gallon. Error sign is **actual minus production**.
Revenue gap sign is **reported revenue minus revenue proxy**.

- 2021 Q2: production error −5.18; revenue gap −1.68; implied-cost residual +3.50;
  reported same-store gallons +22.4%.
- 2021 Q4: production error +6.31; revenue gap +1.57; implied-cost residual −4.74;
  reported same-store gallons +1.4%.
- 2022 Q1: production error −5.18; revenue gap +4.11; implied-cost residual +9.29;
  reported same-store gallons +3.8%.
- 2022 Q3: production error +9.79; revenue gap −6.91; implied-cost residual −16.71;
  reported same-store gallons +9.0%.
- 2023 Q3: production error −6.68; revenue gap +5.33; implied-cost residual +12.01;
  reported same-store gallons −4.7%.
- 2026 Q2: production error +6.60; revenue gap +0.35; implied-cost residual −6.25;
  reported same-store gallons +0.5%.

The accounting identity reconciles exactly:
actual margin minus production = revenue-proxy error minus implied-cost residual.
The residual uses actual margin in its construction. It is **not independently
observed acquisition cost**, and cannot prove that procurement caused a miss.

The strongest useful observation is that the large Q2 2026 margin miss occurred
despite the revenue-change proxy being close to reported revenue-per-gallon
change. Correcting retail prices alone would not reconcile that miss under this
proxy. Q3 2022 and Q3 2023 have revenue gaps opposite their margin-error signs;
that also argues against a simple universal retail-price correction.

The Q3 2022 combination of a negative revenue gap and strong same-store growth,
followed by the reversed combination in Q3 2023, is consistent with a changing
relative-pricing hypothesis. It does **not** establish one: taxes, gasoline-grade
and diesel mix, regional exposure, acquisitions and gallon versus time weighting
can all change the gap. Six error-selected quarters cannot support a reliable
discount/volume regression. No such coefficient was fitted.

MUSA explains that pass-through taxes are excluded from revenue in its
[Q2 2026 filing](https://www.sec.gov/Archives/edgar/data/1573516/000157351626000166/musa-20260630.htm).
The EIA input is a weekly surveyed retail price, with its own sampling and
weighting [methodology](https://www.eia.gov/petroleum/gasdiesel/gas_proc-methods.php).
Exact tax/product reconciliation is unavailable. Therefore the gap is an
**accounting-basis proxy gap**, not an observed pump-price discount.

## How good are two-quarter-ahead estimates?

The existing production model is a **realized-market nowcast**, not a validated
two-quarter-ahead forecast. Its market features contain observations from the
quarter being estimated. Its usual approximately 3.13¢ MAE cannot be quoted as
forward accuracy.

This new experiment defines two-quarter-ahead as a target two calendar-quarter
index steps beyond the cutoff quarter: for example, Q3 at March 31. It uses only
company results with verified original publication dates strictly **before**
the cutoff. It never uses target-quarter prices or unpublished interim results.
At March 31, Q1 results normally are not yet known.

Nineteen common targets are eligible, from Q3 2021 through Q2 2026. Q2 2023 is
excluded because the publication date of its required prior-year anchor remains
unverified. Q2 2022 may be scored as an outcome but cannot enter a forecast's
known-results set until its original publication date is verified.

Three benchmarks were preregistered; none was selected or tuned into production:

- Same quarter last year: **4.45¢ MAE**, 5.88¢ RMSE, worst miss 15.30¢.
- Median of all previously published same-season quarters: **6.31¢ MAE**,
  7.82¢ RMSE, worst miss 20.30¢.
- Mean of the last four published quarters: **4.16¢ MAE**, 5.75¢ RMSE,
  worst miss 17.60¢.

On precisely these 19 targets, the existing realized-market nowcast has
**3.02¢ MAE** and 4.03¢ RMSE. It has more information and is not a fair forward
competitor; the comparison illustrates the value of information arriving later.

The recent eight targets are easier: same-season last year 2.65¢ MAE;
same-season median 3.75¢; trailing-four mean 3.02¢. This does not justify picking
a new champion after looking at the results. Historical regime shifts create
large forward misses, even when recent performance looks reassuring.

These results are **retrospective publication-filtered benchmarks**, not strict
PIT validation: the actual-margin dataset still lacks a complete original-value
revision audit. Dates are date-only; cutoff-day disclosures are conservatively
excluded. Benchmark error averages are not calibrated confidence intervals.

Practical conclusion: free public data supports a useful forward baseline, but
not a claim of consistently precise two-quarter-ahead MUSA retail margins.
Treat forward estimates as scenario anchors, then update with current-quarter
market data and compatible company disclosures. A future forward challenger
should beat these same-cutoff benchmarks in frozen walk-forward tests, not the
realized-market nowcast using future observations.

## Next evidence priority

Extend retail-only revenues and directly reported same-store growth to every
quarter, including ordinary-error quarters, before assessing the pricing-gap
hypothesis. Keep daily retail capture and company evidence separate from this
post-results accounting diagnostic. No forecast adjustment, probability model,
paid data purchase or cloud deployment was made.
