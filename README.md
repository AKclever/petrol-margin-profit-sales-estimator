# MUSA retail-margin wholesale-cost model

This repository contains a small, dependency-free reference implementation for
building and selecting wholesale-cost variables for Murphy USA (MUSA).  The
important modeling choices are deliberately explicit and testable rather than
being hidden in a spreadsheet.

## Data conventions

All input dates are **observation dates**, not download or publication dates.
Values must be expressed in the same cents-per-gallon unit before calling the
model.

| Series | Observation date | Value used / averaging convention |
| --- | --- | --- |
| EIA weekly U.S. regular retail gasoline | EIA survey date (normally Monday; retain EIA's actual holiday-shifted date) | Published U.S. all-formulations regular price. It is effective from that observation date up to, but not including, the next observation date; no interpolation. |
| MUSA retail price, when available | Date to which the company/store observation applies | Gallon-weighted store price. A weekly input is effective until the next observation, as above. Never substitute the filing publication date. |
| Daily wholesale/rack price | Supplier/market local-date close stated by the source | One observation per trading day. Duplicate same-day quotes are volume weighted when volume exists, otherwise equally averaged. Weekends/holidays use the latest price known by the retail observation date (an as-of join), preventing look-ahead. |
| Daily Gulf Coast spot proxy | Platts/EIA market-date close | Same close, duplicate, and non-trading-day rules as daily wholesale/rack prices. Spot prices are a proxy and must not be mixed with delivered rack prices without a separately identified basis/freight variable. |

Trailing `3d` and `7d` variables mean the last 3 or 7 **available trading-day
observations**, inclusive of the retail observation date. `lag_1w` and `lag_2w`
mean the latest wholesale close known on or before 7 or 14 calendar days before
the retail date. `same_day` means the latest close known on or before the retail
date. These conventions are implemented in `margin_model/features.py`.

## Model selection and quarterly aggregation

`rolling_origin_scores` compares same-day, trailing-average, weekly-lag, and
distributed-lag candidates only on observations strictly later than each
training window. Thus a lag is not selected because it happens to explain a
single reported quarter. Select the lowest mean out-of-sample error, retaining
fold-level scores for audit. Distributed-lag candidates let cost realization be
spread across current, one-week, and two-week wholesale prices; their weights
are estimated on each training fold and constrained to sum to one.

Quarter boundaries are loaded from `data/musa_fiscal_quarters.csv`; do not infer
quarters from filing dates or 13-week shortcuts. `weighted_quarter_average`
treats a weekly value as effective on `[observation_date, next_observation_date)`
and weights it by the exact number of calendar days overlapping MUSA's inclusive
fiscal-quarter boundaries. This handles partial weeks at both quarter edges.

Run the checks with:

```bash
python -m unittest discover -s tests -v
```

