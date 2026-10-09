# MUSA Q3 2026 focused margin estimate

As of October 8, the refreshed frozen-method estimate is **28.94¢ retail margin** and **31.89¢ all-in contribution**. The separate fixed Casey's shadow is **29.80¢ retail**. These results support a working retail view around 29–30¢, not a claim that the quarter can be estimated precisely. The earlier official 29.54¢ checkpoint remains unchanged; no challenger was promoted.

## Management assumption is for the second half

MUSA's August 5 earnings release uses a conditional 35¢ all-in average for the second half of 2026 to illustrate its earnings outlook. It is neither Q3-only guidance nor a partial-quarter retail-margin disclosure. It cannot mechanically anchor Q3 retail margin, and a supply/RIN assumption must not be subtracted to manufacture one. The checked issuer release does not establish what every other call or presentation may have disclosed. [Original earnings release](https://www.sec.gov/Archives/edgar/data/1573516/000157351626000164/exh991_06302026er.htm).

## Market input verification

Five official EIA weekly workbooks were freshly captured, hashed and normalized. All three configured regions now have paired prices through the ISO week beginning September 28. The original repo market file was preserved, along with the official checkpoint and historical actuals.

The frozen complete-week rule includes July 6 through September 21: all 12 expected model weeks. The September 28 spot-price week crosses into October and is correctly excluded. Model coverage of 100% therefore means complete coverage of its weekly convention, not direct daily observation of July 1–5 and September 28–30. Neither the added September 28 row nor October retail data is used to extend Q3 improperly. The refreshed estimate remains 28.94¢.

Static regional weights are still store-count proxies, not MUSA gallon weights. Retail prices include taxes and wholesale prices are spot proxies, so their raw spread is not company retail margin. Historical observations are current vintage, not a reconstructed strict PIT backtest.

## Point estimate and supported shadows

- Earlier official production checkpoint: 29.54¢ retail.
- Refreshed frozen method: 28.94¢ retail; historical production MAE 3.13¢ and RMSE 4.02¢.
- Timing A, one-week lag: 29.35¢ retail.
- Timing B, current/prior equal weights: 27.86¢ retail.
- Timing C, trailing three weeks: 28.15¢ retail.
- Fixed Casey's update: 29.80¢ retail, a +0.86¢ correction to the refreshed estimate.

Casey's May–July 2026 margin was 47.8¢ against the repo pilot's existing 42.7021¢ own-company estimate. Its September 8 publication overlaps MUSA only in July. The frozen fixed transfer is 0.5 × (31/92) × the 5.0979¢ surprise. Calendar overlap is an exposure proxy, not observed gallons. The most recent Casey's quarter was absent from the older event-replay dataset; its separately archived pilot forecast supplies the donor baseline and is explicitly identified in the output.

This is the simple fixed rule evaluated in the directional diagnostics, not the older fitted pilot's +1.67¢ correction. That older pilot's 30.61¢ output is not the same method and is not reused as the current fixed shadow. No new transfer coefficient was fitted. [Casey's original release](https://www.sec.gov/Archives/edgar/data/726958/000072695826000084/q1fy2027earningspressrelea.htm).

The refreshed all-in bridge adds the frozen historical 2.95¢ supply/RIN component to 28.94¢. Holding retail fixed, historical supply/RIN sensitivity values of 1.70¢ and 5.92¢ imply 30.64¢ and 34.86¢ all-in. These are conditional component scenarios, not Q3 supply forecasts or calibrated probability bounds. Management's 35¢ second-half assumption is a different object.

## Weekly sequence and sensitivity

The regional weighted spread proxy averages 39.55¢ in July, 49.26¢ in August and 31.98¢ in September. The August average is influenced by the August 3 week at 83.71¢; the minimum complete-week spread is 26.53¢ on September 14. Expansion was not uniformly sustained throughout the quarter.

Equal-week aggregation gives a 41.70¢ market spread proxy. Equal-month aggregation gives 40.26¢, a 1.44¢ difference. This is an explicitly labeled weighting diagnostic, not an alternative MUSA forecast or an estimate of company gallon allocation. There is no verified current-quarter MUSA weekly gallon allocation with which to declare either weighting correct.

Falling-cost capture impulses and rising-cost squeeze impulses both appear in the proxy path. Their totals cannot be netted into company profit: they are overlapping price-change diagnostics, not volume-weighted realized margins or delivered acquisition costs.

The existing risk layer remains **ELEVATED / BIDIRECTIONAL**, with HIGH rising squeeze, HIGH falling capture, HIGH structural uncertainty and LOW anchor reversal. Feature distance is 3.33σ, with six comparable historical regimes. The model's mechanical retail error band is 22.35–35.53¢; it is not a newly calibrated Q3 tail interval. Timing-shadow dispersion of only 1.49¢ does not justify a narrow uncertainty range, because the methods share the same imperfect inputs.

## Conclusion

The evidence supports retaining roughly 29¢ as the central retail estimate, with Casey's providing a modest upward shadow toward 30¢. It does not establish 35¢ retail or resolve whether MUSA captured the favorable weeks more effectively than the regional proxy. The main unresolved uncertainty is company-specific pricing and acquisition economics, not missing complete model weeks.

Canonical archive: `data/q3_focus/2026-10-08_v3/results.json`, input snapshots and raw source hashes. The raw EIA capture is preserved in V2; V2 stopped before completion when the direct SEC request returned 403. V3 reuses those exact workbook bytes and the existing issuer-release archive, whose management scope was also checked against the live SEC page. V1 retains the initial normalized market refresh.

```bash
.venv/bin/python -m musa_nowcast.q3_focus --source-snapshot data/q3_focus/2026-10-08_v2 --out data/q3_focus/NEW_RUN
.venv/bin/python -m pytest -q tests/test_q3_focus.py
```
