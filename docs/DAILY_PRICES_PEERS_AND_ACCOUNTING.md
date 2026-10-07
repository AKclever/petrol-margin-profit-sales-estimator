# Daily prices, Couche-Tard peer surprise, and targeted accounting review

October 7, 2026. Free primary-source research. Production is unchanged. The
earlier frozen 29.54-cent Q3 production checkpoint remains separate from the
28.94-cent rerun on the current market snapshot. Neither has been replaced.
Q3 actuals remain blank. The original 22-quarter disclosure audit is untouched.

## Daily-price capture: working collector, historical retail backtest blocked

`musa_nowcast/daily_prices.py` archives daily EIA NYH and USGC conventional
gasoline spot prices, raw XLS files, hashes, observation dates, conservative
availability and capture timestamps. Source-series identity and duplicate dates
are checked. It also parses explicitly dated AAA regular-price state snapshots
from a supplied local HTML file. First capture is not historical publication
time. An old observation downloaded now is current-vintage research, not PIT
evidence of what existed years ago.

The October 7 capture contains **18,353 wholesale observations** across the two
series and **51 retail observations**, one for each state plus DC on October 7.
Raw acquisition is in `data/daily_prices/2026-10-07_v1/`; the final guarded
parser reprocessing archive is `data/daily_prices/2026-10-07_v4/`. Reprocessing
retains the original conservative capture time and identifies its source
archive. Intermediate versions remain unchanged. Specification was frozen
before analysis in `data/daily_prices_spec_v1.json`.

[EIA daily prices](https://www.eia.gov/dnav/pet/pet_pri_spt_s1_d.htm),
[AAA public prices](https://gasprices.aaa.com/).

There is **no verified free historical daily state-retail dataset** in this
capture. We did not invent daily history from the site's week/month comparison
figures, interpolate EIA Monday prices, or treat today's prices as old vintages.
Consequently `backtest_status = BLOCKED_DAILY_RETAIL_HISTORY` and
`daily_margin_forecast = null`. Sustained retail-spread expansion/compression
cannot yet be tested historically. AAA prices are regional regular averages,
not MUSA prices or delivered fuel costs. Taxes and product basis also prevent
interpreting an unadjusted spot/pump spread as reported company margin.

The exact-date join rejects filling and requires a supplied state-to-wholesale
proxy mapping. A matched pair's availability is the later of its two source
availability timestamps, not merely the retail timestamp. No unsupported state
mapping or MUSA gallon weights have been introduced.

The public AAA page and robots file were checked once for feasibility. Robots
permits the homepage and requests a ten-second crawl delay, but that is not a
data license. No applicable bulk-use authorization was established. Unrelated
AAA club terms are not asserted to govern this national site. **Recurring AAA
collection remains disabled**, pending a permission reference and scope; no
login, challenge bypass, hidden API, or commercial subscription is used.

### Wholesale path findings, not a margin forecast

Daily wholesale observations do expose movements obscured by weekly averages.
For Q3 2026, Gulf Coast's mean within-week high-low range is **22.57 cents** and
the maximum is **56.80 cents**. NYH's corresponding values are **17.50** and
**41.50 cents**. Each region has 63 daily observations and 14 calendar-week
buckets with at least two observations; boundary weeks are partial. These are
price ranges, not retailer profit and not a fitted predictor of errors.

Among the six largest past misses, Gulf Coast mean within-week ranges were
6.39 cents in Q2 2021, 9.35 in Q4 2021, 21.12 in Q1 2022, 21.94 in Q3 2022,
11.79 in Q3 2023, and 20.01 in Q2 2026. Large misses appear in both less volatile
and more volatile periods, so volatility alone does not identify their sign.
The current-vintage path diagnostics are archived separately from any forecast.

### Scheduling implementation

The existing daily capture accepts `--daily-prices`, or
`MUSA_CAPTURE_DAILY_PRICES=1`, to add daily EIA wholesale evidence while keeping
weekly production inputs unchanged. `deploy/daily_capture.sh` now supplies that
environment variable for a future deployment. AAA is not enabled in that job.

```bash
.venv/bin/python -m musa_nowcast.daily_capture --local-root data/prospective/daily --daily-prices
```

This session did not deploy, purchase, or schedule a cloud service. Existing
billing and deployment requirements in `deploy/DAILY_CAPTURE.md` still apply.
The collector is ready; a recurring cloud job is not claimed to be running.

## Couche-Tard: small retrospective improvement, failed gate

`musa_nowcast/couchetard_peer.py` captures issuer release indexes and original
period releases. Final archive: `data/couchetard_peer/2026-10-07_v3/`. All **33
original-release quarter rows** reconcile before-payment-fee margin minus fees
to after-fee margin within rounding. Fiscal dates and 12-, 13-, or 16-week
lengths are retained, as are acquisition/divestiture source paragraphs. The
target is **US company-operated road-fuel margin before payment fees**, not the
broader US road-fuel metric.

Fiscal-year quarter labels define seasonal anchors, avoiding errors where the
start month shifts across a calendar-quarter boundary. Peer predictions use
only earlier reported targets and market observations through that peer period.
Fixed equal East Coast/Midwest/Gulf Coast weights are an explicitly provisional
US exposure proxy, not company gallon shares. Acquisition context is retained
but not quantitatively adjusted; geography and acquisitions remain limitations.

The one-feature residual correction uses the latest already-published peer
period overlapping MUSA, alpha 2 ridge, eight minimum earlier available MUSA
residuals and 50% shrinkage. No absolute competitor margins are copied. No
Casey's/Couche-Tard ensemble was fitted. Source availability is date-only;
historical market vintages and original historical byte identity are unverified.
This is retrospective current-vintage research, not prospective validation.

On the same **12 quarters**, Q3 2023-Q2 2026:

- Production MAE: **2.4003 cents**; Couche-Tard shadow: **2.3402 cents** (2.50% improvement).
- Direction accuracy: **83.3%** versus **75.0%**, worse for the shadow.
- Recent-eight MAE: **2.1535** versus **2.0344 cents** (5.53% improvement).
- Mean paired benefit: **0.0601 cents**; paired 95% lower bound: **-0.1448 cents**.
- Removing the single best improvement quarter reduces mean benefit to about **0.0112 cents**.

**Promotion gate: failed.** Do not compare these MAEs to the full-history
production MAE or to Casey's different eligible sample.

Current peer actual is 53.87 cents versus its expanding forecast 46.2277, a
7.6423-cent surprise. The September 1 release covers April 27-July 19, overlapping
MUSA Q3 for **19 calendar days**, not observed gallon share. It yields a
**30.0441-cent Q3 retail research shadow**, a +1.1041-cent correction to the
same-input 28.94 production rerun. August-September are not measured by this
peer report. [Latest original release](https://corporate.couche-tard.com/2026-09-01-ALIMENTATION-COUCHE-TARD-ANNOUNCES-ITS-RESULTS-FOR-ITS-FIRST-QUARTER-OF-FISCAL-YEAR-2027).

V1 retains the initial parser failure. V2 retains a narrower ten-quarter result
that missed a combined date/label table row. V3 fixes that source parsing,
captures complete history, and archives all inputs. The interim 2.06-to-2.21
comparison is superseded by V3's complete twelve-row comparison; parameters
were not retuned to improve its result.

## Deeper accounting: useful findings, no retail adjustment

`scripts/capture_deeper_accounting.py` discovers issuer-hosted call links through
the public quarterly-results page's read-only report service. It archives six
SEC filings (five 10-Qs and the Q4 2021 10-K) and seven call/commentary PDFs.
Reviewed findings: `data/accounting_miss_audit/2026-10-07_deeper_v2/reviewed_findings.json`.
Scope is inventory notes/policies and relevant fuel-cost, pricing and synergy
call passages, not every possible filing or management communication.

**Q2 2026 provides an important supply decomposition:** controllable activities
including RINs +7.2 cents, uncontrollable inventory-related exposure **-2.0**,
terminal/wholesale +0.3, totaling +5.5. Thus inventory exposure was a supply
headwind. It must not be treated as a retail tailwind or as the explanation for
the retail forecast's 6.60-cent miss. This clarifies the earlier release-only
review's broad inventory-timing description.
[Issuer commentary](https://s22.q4cdn.com/506259022/files/doc_financials/2026/q2/MurphyUSA_Q2_2026_Quarterly_Commentary_vFinal.pdf).

**Q1 2022 discusses internal spot-to-rack transfer pricing.** Management
describes about 2.7 cents supply/RIN contribution after excluding timing and
inventory effects versus 10.7 reported; it qualitatively says retail is
understated. That does not provide a numeric retail restatement. Our inference
is that internal transfer-pricing conventions create another difference between
public spot spreads and reported retail margin; the call does not disclose a
complete formula to reconstruct that difference.
[Issuer-hosted call](https://s22.q4cdn.com/506259022/files/doc_financials/2022/q1/1Q22-Earnings-Transcript-MUSA.pdf).

**Q4 2021 identifies genuine company-specific changes.** Over $8 million of
2021 synergies were achieved, largely within total fuel contribution, through
pricing tactics and improved supply contracts. This is an annual combined
benefit, not a separately quantified Q4 retail adjustment.
[Issuer-hosted call](https://s22.q4cdn.com/506259022/files/doc_financials/2021/q4/Q4-2021-Transcript.pdf).

**QuickChek cost-basis wording needs care.** The June 2021 note describes FIFO
gasoline; the 2021 annual policy describes weighted-average petroleum. We
preserve this discrepancy rather than assert a verified policy change or
silently apply one basis to all history. Balance-sheet LIFO reserve levels are
not quarter retail expense; cumulative December comparisons are not clean
quarter-to-quarter flows. No reserve was divided by gallons as a margin fix.
[June 2021 filing](https://www.sec.gov/Archives/edgar/data/1573516/000157351621000044/musa-20210630.htm),
[2021 annual filing](https://www.sec.gov/Archives/edgar/data/1573516/000157351622000006/musa-20211231.htm).

Across the reviewed six quarters, **no isolated quantified retail inventory
adjustment was identified**. This is scoped non-identification, not proof none
exists. Weekly acquisition costs remain unrecovered. Post-results explanations
are not quarter-end forecast inputs. The stronger conclusion is that daily
company pricing and sourcing information matter—not that an accounting
correction has now solved the margin forecast.
