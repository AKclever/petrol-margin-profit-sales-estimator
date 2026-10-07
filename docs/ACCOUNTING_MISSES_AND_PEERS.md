# Free accounting reconciliation and early-reporting peers

As of October 7, 2026. Production and all prior frozen forecasts are unchanged.
No subscriptions were purchased. This is retrospective documentary diagnosis,
not a fitted correction, prospective validation or completion of the original
22-quarter disclosure audit.

## Scope and evidence

All six largest absolute production misses were selected using the unchanged
22-quarter expanding-window production backtest. Checked evidence consists of
the original issuer earnings releases and archived 2021, 2022, 2023 and 2025
annual filings for accounting definitions. This is not an exhaustive review of
every quarter-specific 10-Q, call and presentation. Absence of a quantified
adjustment below means it was not identified in this scoped review, not that
none existed.

Raw HTML, hashes, source checks, extracted tables and reviewed calculations are
in `data/accounting_miss_audit/2026-10-07_v1/`. Acquisition metadata remains
unchanged; `reviewed_audit.json` appends a corrected May 3, 2022 publication date
for Q1 2022 and a verified August 7, 2026 date for ARKO. A historical public
publication date does not establish that today's captured HTML was never edited.
Earnings-result explanations are post-quarter evidence, not usable at the
quarter-end reference cutoff. That reference is not an archived forecast timestamp.

## Accounting findings

Every checked retail margin agrees with the model's actual input. Retail fuel
contribution divided by retail gallons reproduces each reported cents-per-gallon
margin within rounding. Retail contribution plus supply excluding RINs plus the
reported RIN/other contribution reconciles to total fuel contribution in all six.
There is no discovered target-definition error that explains these large misses.

Consolidated petroleum sales minus petroleum COGS is not retail-only profit.
Shipping, eligible taxes, wholesale activity and other fuel revenues must be
considered. The remaining sales/COGS bridge requires $0.8m-$1.2m of other fuel
revenue per reviewed quarter (roughly 0.07-0.10 cents per retail gallon), not a
5-10-cent explanation. The exact quarterly composition is not isolated here;
the annual filing identifies collection allowances and miscellaneous revenue.
The annual reconciliation explicitly includes RINs and other revenue.
[2025 annual accounting definitions and reconciliation](https://www.sec.gov/Archives/edgar/data/1573516/000157351626000090/musa-20251231.htm).

The 2021/2022 annual notes distinguish LIFO costing at Murphy stores from
weighted-average petroleum costing at QuickChek. The acquisition changes
exposure and accounting comparability; no numerical effect on a model error is
claimed. General LIFO policy is stated in the 2023/2025 notes. The checked
sources do not provide weekly retail acquisition-cost observations.

## Six misses: retail explanations versus supply explanations

- **Q2 2021:** production 26.98, retail actual 21.80 cents. Management attributes
  weaker retail margins to rising fuel prices and compares against record 2020
  results. Higher RIN prices offset negative spot-to-rack margins in supply.
  The acquisition of QuickChek adds another comparability issue. Supply/RIN
  effects cannot be added to repair a retail-only prediction.
  [Original results](https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/2021/Murphy-USA-Inc.-Reports-Second-Quarter-2021-Results/default.aspx).
- **Q4 2021:** production 19.19, actual 25.50. Retail improved despite dynamic
  pricing; management separately reports lower supply contribution from timing
  and inventory-pricing effects. A late wholesale reversal is consistent with
  capture, but the release does not identify a numerical retail lag effect.
  [Original results](https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/2022/Murphy-USA-Inc.-Reports-Fourth-Quarter-2021-Results/default.aspx).
- **Q1 2022:** production 28.48, actual 23.30. Retail improved year-on-year despite
  rising commodity prices, but by less than the model predicted. The 10.7-cent
  supply/RIN contribution is separate; inventory timing/pricing is cited for
  that business. A strong all-in result is not proof of equally strong retail.
  [Original results](https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/2022/Murphy-USA-Inc.-Reports-First-Quarter-2022-Results/default.aspx).
- **Q3 2022:** production 29.51, actual 39.30. Management explicitly links retail
  strength to falling commodity prices. Supply/RIN was negative 1.7 cents;
  timing/pricing in the falling market hurt supply. Retail strength and supply
  weakness coexist; averaging them into one mechanism would conceal this.
  [Original results](https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/2022/Murphy-USA-Inc.-Reports-Third-Quarter-2022-Results/default.aspx).
- **Q3 2023:** production 35.38, actual 28.70. Management contrasts retail with
  the prior year's falling-price benefit. Supply/RIN improved to 5.8 cents,
  supported by inventory-pricing adjustments despite weaker spot-to-rack
  spreads. An exceptional seasonal anchor is a plausible model issue, not a
  quantified causal attribution of the miss.
  [Original results](https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/2023/Murphy-USA-Inc.-Reports-Third-Quarter-2023-Results/default.aspx).
- **Q2 2026:** production 28.50, actual 35.10. Management cites persistent
  volatility for retail; it separately cites inventory timing and market pricing
  for supply/RIN, which contributed 5.5 cents. The latter does not explain away
  the 6.60-cent retail miss. No weekly company-cost path is recovered.
  [Original results](https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/2026/Murphy-USA-Inc--Reports-Second-Quarter-2026-Results/default.aspx).

## Peers available before MUSA's Q3 results

**Casey's (CASY) is the easiest implementation candidate.** On September 8 it
reported 47.8-cent retail fuel margin versus 41.0 a year earlier for May-July
2026, excluding credit-card fees and wholesale/terminal activity. This period
contains July but not August or September. The repo already has 28 historical
quarter targets and an issuer-specific experimental backtest. That model's
3.12-cent MAE is essentially equal to its seasonal baseline and its direction
accuracy is 50%; it is not validated. No new Casey's forecast is issued here.
[Latest primary release](https://www.sec.gov/Archives/edgar/data/726958/000072695826000084/q1fy2027earningspressrelea.htm).

**Couche-Tard (ATD) is the second candidate.** Its September 1 report covers 12
weeks ending July 19. US company-operated fuel margin before electronic-payment
fees was 53.87 cents versus 44.81. Its broader US road-fuel measure is 52.61,
which must not be substituted for the company-operated target. The overlap with
MUSA Q3 is July 1-19 only. A separate US target history, dated exposure weights,
acquisition controls and fiscal-calendar alignment are needed before modeling.
[Latest primary release](https://corporate.couche-tard.com/2026-09-01-ALIMENTATION-COUCHE-TARD-ANNOUNCES-ITS-RESULTS-FOR-ITS-FIRST-QUARTER-OF-FISCAL-YEAR-2027).

**ARKO is less straightforward.** On August 7 it reported same-store retail fuel
margin of 48.7 cents versus 45.7 for April-June. It has retail/wholesale/fleet
segments and ongoing conversions of retail stores to dealers. That release
contains no MUSA-Q3 days and was after MUSA's August 5 Q2 release. An earlier
same-calendar-Q3 release advantage is not established; do not assume it.
[Latest checked primary release](https://www.arkocorp.com/news-events/press-releases/detail/213/arko-corp-reports-second-quarter-2026-results).

Calendar overlap is not observed gallon share. Absolute peer margin levels are
not interchangeable with MUSA retail or all-in margin. Both September reports
are evidence consistent with a strong earlier industry margin environment,
not a measurement of MUSA's subsequent Q3 economics.

## Recommended next research step, not yet implemented

Use a **period-matched peer residual**, rather than copying a peer's margin or
its year-on-year change. Estimate the peer's own expected margin using only
earlier data and the market weeks in its fiscal reporting period. Its reported
minus expected margin could reveal industry strength not captured by market
proxies. Record that surprise at publication time, keep geography/definitions
separate, and test whether it predicts later MUSA errors. Peer changes alone
may simply repeat wholesale information already in production.

No coefficients, thresholds, peer weights or point-forecast changes are fitted
from these examples. Start with Casey's and Couche-Tard as evidence channels;
neither September report describes the late-Q3 reversal. The retail production
rerun remains 28.94 cents. The 29.80-cent residual challenger remains research-only.
