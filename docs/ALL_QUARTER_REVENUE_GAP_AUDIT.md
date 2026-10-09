# All-quarter revenue-gap audit

Production is unchanged. No coefficient, probability model, forecast adjustment
or new error threshold was fitted. The previously frozen revenue-gap definition
was applied to all quarters, not just memorable misses.

Final results: `data/revenue_gap_all/2026-10-07_review_v2/summary.json` and
`quarter_rows.json`. Original source checks and raw evidence are in
`data/revenue_gap_all/2026-10-07_v2/`. Earlier captures and reviews remain intact.

## Coverage and reconciliation

- All **30 reported quarters**, Q1 2019 through Q2 2026, have retail-only revenue
  and directly stated same-store gallon growth.
- **26 quarters** have year-over-year revenue gaps, Q1 2020 through Q2 2026.
  The four 2019 gaps remain explicitly blocked because the baseline dataset
  lacks 2018 market observations and actuals. They are not treated as zero.
- All **22 production out-of-fold quarters** have revenue-gap/error comparisons.
- Quarterly retail revenues reconcile to annual revenues for all seven full
  years, 2019-2025. Prior-year revenue comparatives match archived prior-period
  revenues within the rounding tolerance. This is not an exhaustive revision audit.
- All 30 earnings-table retail margins/gallons reconcile to model actuals;
  18 same-store statements are additionally corroborated by the SSS variance
  table. The other 12 still have directly stated growth; no rate was inferred
  from changing store populations or APSM levels.
- Thirty filings, thirty earnings covers and thirty earnings exhibits were
  captured and SHA-256 checked. Q2 2022 was an Item7.01 8-K, explaining the old
  Item2.02-only source-search gap. This audit records it separately without
  modifying the frozen historical disclosure taxonomy or forward benchmark.

The calculation remains:
reported retail revenue/gallon minus prior-year reported retail revenue/gallon
minus the EIA weighted retail price change. Q4 retail revenue uses annual minus
nine-month retail-only revenue. Wholesale revenues are excluded.

## Does the original hypothesis generalize?

Only weakly. For 26 quarters, revenue gap versus same-quarter same-store gallon
growth has Pearson correlation **-0.360** and rank correlation **-0.217**.
That is consistent with a possible relative-pricing/volume mechanism, but weak
rank consistency and unmatched tax/product/geographic bases prevent claiming
that the gap measures MUSA's competitive discount.

In the six previously identified large production misses, mean absolute revenue
gap is **3.33 cents/gallon**. In the other 16 production-test quarters it is
**3.64 cents/gallon**. Gaps are not bigger in the large misses. Their production
margin MAEs are 6.62 and 1.82 cents respectively, so the group distinction is real
but the gap magnitude does not select it.

Across all 22 quarters, gap versus contemporaneous margin error has Pearson
**-0.279**, rank **-0.252**. Within the other 16 quarters, Pearson correlation
is **-0.019**. The striking six-quarter story therefore does not provide a
general same-quarter error correction. These are descriptive associations,
not causal estimates, statistical significance claims or calibrated probabilities.

## A potentially useful lag, not proven forecasting improvement

Previous-quarter gap versus next-quarter actual-minus-production error has
Pearson **+0.406** and rank **+0.398**, across 22 observations. The prior-quarter
filing must be public strictly before the target quarter's end; a missing
quarter cannot be replaced with the last row found. Availability is conservative
SEC filing-date precision, not earnings-release timestamp precision.

Exploratory robustness checks, explicitly **not preregistered**, show Pearson
correlation ranging from +0.282 to +0.582 after omitting each quarter in turn.
Omitting Q2 2026 produces the low end. The recent-eight Pearson figure is +0.870,
but this is a small, easier sample with a highly influential large observation.
Do not select a coefficient, rule or promotion decision from that attractive slice.

The lag is worth preregistering as a **single-feature research challenger**.
It has not yet been trained, backtested for incremental MAE, or promoted.
The market history is current-vintage, not a fully verified historical PIT
archive. Publication filtering of company filings alone does not fix that.
This also does not establish two-quarter-ahead predictive value: prior-quarter
results typically arrive during the target quarter.

## What additional data could improve estimates?

### First choice: company-specific relative pump prices

Build a small fixed panel of MUSA stations and nearby competitors, collected
from sources that permit it or manually observed public prices. Retain cash
versus card, regular versus other grades, base versus member/reward prices,
observation time and source provenance. Pair prices by geography and date;
do not aggregate an opportunistically changing station sample.

This would directly test whether MUSA changed its competitive discount, unlike
the mixed accounting-basis revenue gap. A free panel still requires collection
work, coverage checks and permission; complete free US station-price history
has not been established. Posted prices are not gallon-weighted realized
revenue, and reward funding/reimbursement cannot be inferred from the advertised
discount. [MUSA rewards](https://www.murphyusa.com/murphyusa/get-rewards) document
distinct discount programs, reinforcing the need to separate price bases.

### Best new free forward-data lead: dated RBOB futures settlements

The [USDA National Daily Ethanol Report](https://www.ams.usda.gov/mnreports/ams_3617.pdf)
includes dated NYMEX RBOB gasoline settlements for multiple contract months.
The locally archived October7 report contains October6 settlements for November
2026 through April2027. Page1 was visually checked; the original raw PDF and
SHA-256 are in `data/alternative_data_feasibility/2026-10-07/`.

Despite its title, this daily report is **not** a delivered ethanol-cost series:
its cash bids are corn at ethanol plants. The report lists separate corn,
natural-gas and RBOB futures units. A different downloaded vintage can have a
different printed report date; retain the actual raw bytes rather than treating
the rotating latest URL as a historical archive.

RBOB could supply a documented wholesale-price scenario for future quarters.
It is not MUSA delivered fuel cost, not an expected retailer margin, and not
a substitute for forecasting retail-price adjustment. Historical completeness,
release timing and original exchange-data usage terms still need verification
before bulk acquisition or a claimed PIT forward backtest.

### Free replacement-cost context: regional supply conditions

EIA publishes [regional gasoline stocks by storage facility](https://www.eia.gov/petroleum/supply/weekly/wproductstorage_notice.php)
and [refinery utilization](https://www.eia.gov/dnav/pet/pet_sum_sndw_a_%28na%29_yup_pct_4.htm).
These can test whether the NYH/USGC spot-to-local-cost mapping changes during
regional disruptions. Predefine a small mechanism-specific experiment; do not
add dozens of supply indicators to 22 outcomes. Stock data is not MUSA inventory
and refinery utilization is not a terminal quote or delivered acquisition cost.

EIA [product supplied](https://www.eia.gov/tools/FAQs/faq.php?id=1394&t=10) is a
consumption proxy at the primary supply-chain boundary, not directly measured
MUSA gallons. It may help prospective volume weights but must stay explicitly
modelled and cannot retrospectively manufacture observed gallon shares.

### Implementation order

1. Keep daily evidence capture operational and production frozen.
2. Verify feasibility and permission for a fixed company/competitor pump panel.
3. Preregister a one-feature lagged-gap challenger with strict availability
   and frozen out-of-sample scoring; do not claim the current correlations as edge.
4. For two-quarter-ahead work, investigate dated RBOB vintages and forecast
   **retail response and regional basis separately**, with explicit scenarios.
5. Promote only if a challenger improves matched-cutoff errors robustly and
   subsequently holds up on newly arriving quarters.

The likely opportunity is better measurement of company pricing and local cost
basis, not making a larger model from the same public weekly price averages.
No alternative-data purchase, automated station scraping, forecast change,
cloud deployment or GitHub push was performed in this audit.

## Reproduction

Capture: `.venv/bin/python -m scripts.capture_all_quarter_revenue --output NEW_CAPTURE_DIR`.
Review: `.venv/bin/python -m scripts.review_all_quarter_revenue --capture CAPTURE_DIR --output NEW_REVIEW_DIR`.
Both refuse existing output directories. Input snapshots precede calculations;
raw hashes are verified before parsing; missing evidence stays explicit.
