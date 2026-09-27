# MUSA fuel-margin tracker and nowcast

This repository combines an auditable regional fuel-cost tracker with a dependency-free
Python model for producing a **directional,
uncertainty-aware** estimate of Murphy USA's quarterly fuel economics from public market
data. It is deliberately a calibration tool rather than an assertion that EIA spot prices
equal MUSA's acquisition cost.

## Cost-proxy workflow

```bash
python3 tracker.py build --prices data/example_prices.csv --config data/series_catalog.csv --output output/proxy.csv
python3 tracker.py validate-spots --history data/history_template.csv
python3 -m unittest discover -s tests -v
```

`build` selects a rack observation only when the series is marked reliable and has at least
80% of expected observations in the trailing 90 days. Otherwise it uses the region's
configured EIA spot fallback and adds separately supplied terminal basis, freight, and
ethanol-blending estimates. Missing adjustments are never silently treated as zero: the
output is withheld and explains why.

The example prices are illustrative plumbing data, not investment data. Replace them with
licensed/vendor rack history and dated estimates before use. See [the methodology](docs/METHODOLOGY.md)
and [data dictionary](docs/DATA_DICTIONARY.md).

Before a spot series may be used in a live estimate, `validate-spots` estimates a
first-difference model against MUSA's reported quarterly retail fuel margin. It reports
coefficients, R², adjusted R², leave-one-out cross-validated R², directional accuracy, and
sample size. The gate requires at least 20 quarters, adjusted R² ≥ 0.10, cross-validated R²
greater than zero, and at least 55% directional accuracy. A failure keeps spot series in an
explanatory-only role.

## Margin-nowcast workflow

The nowcast is designed to answer whether a quarter appears closer to 30¢, 35¢, or 40¢
while making the model's limitations visible:

- constructs a gallon-weighted (or best available proxy-weighted) regional basket;
- refuses to silently reweight weeks with missing regions;
- distinguishes spread, falling-price capture, rising-price squeeze, and volatility;
- calibrates those features to reported retail margins with regularized regression;
- predicts the year-over-year margin change from year-over-year market-feature changes and
  shrinks that change halfway toward the same-quarter prior-year margin;
- performs expanding-window validation using only actuals available before each test quarter;
- compares against both historical-mean and same-quarter prior-year baselines;
- requires at least eight test quarters, a 10% MAE improvement over the stronger baseline,
  and at least 55% year-over-year directional accuracy both across the full test and over the
  latest eight test quarters before setting `validated: true`;
- requires the approximate 95% lower bound on paired MAE improvement to remain above zero;
- widens its interval when the current quarter is incomplete;
- models supply/RIN economics as historical low/base/high scenarios, not false precision;
- optionally converts all-in cents per gallon and expected gallons into dollars; and
- emits Markdown for analysts or JSON for a spreadsheet/dashboard pipeline.

It uses only the Python standard library at runtime. The bundled market observations and
company figures are sourced snapshots with provenance; illustrative figures remain confined
to explicit templates and tests.

### Input files

Prices and margins are expressed in **cents per gallon**. Every weekly row must use the same
tax and product conventions. Ideally, `wholesale_cpg` is an aligned regional rack/acquisition
proxy. Spot prices may be used, but the resulting basis risk must be documented.

#### `market.csv`

```csv
week,region,retail_cpg,wholesale_cpg
2026-06-29,Gulf Coast,301.2,214.7
2026-06-29,Midwest,309.8,220.1
2026-06-29,East Coast,315.4,225.6
```

Use one observation per region per week, dated to the ISO-week Monday. The loader rejects
non-Monday dates and duplicate region/week pairs. Quarter features use only complete
Monday-through-Friday market weeks contained within the reporting quarter, which prevents
prices published after quarter-end from leaking backward.

#### `weights.csv`

```csv
region,weight
Gulf Coast,0.55
Midwest,0.30
East Coast,0.15
```

Weights must be positive and sum to 1. Prefer gallon exposure. If only store counts are
available, record that limitation alongside the generated forecast.

#### `actuals.csv`

```csv
quarter,start,end,retail_margin_cpg,supply_rin_cpg,gallons_million
2024Q1,2024-01-01,2024-03-31,30.4,3.8,1102.0
```

At least six quarters are accepted for input checks, but 16 or more consistently defined
quarters are needed to exercise the eight-quarter trust gate. Dates must match MUSA's
reporting calendar. `supply_rin_cpg` is the difference
between all-in fuel contribution and retail margin under a consistent definition.
`gallons_million` is optional and currently retained as source context; the live forecast's
gallons assumption is supplied separately.

For retailers that disclose only retail fuel margin, `supply_rin_cpg` may be blank. The
backtest then evaluates the retail-margin target alone, and forecast output omits the
MUSA-specific supply/RIN and all-in scenario rows. Never enter zero merely to represent an
undisclosed field.

### Run a nowcast

First download and archive the official EIA weekly series. An EIA API key is required:

```bash
python -m musa_nowcast.eia \
  --api-key "$EIA_API_KEY" \
  --start 2019-01-01 \
  --end 2026-09-27 \
  --output data/market.csv \
  --provenance data/market.provenance.json
```

The downloader pairs the EIA Gulf Coast, Midwest, and East Coast weekly retail series with
Gulf Coast or New York Harbor spot fallbacks, converts dollars per gallon to cents per gallon,
normalizes differing EIA observation dates to ISO weeks, and writes a provenance sidecar.
These remain **spot proxies**, not rack or landed MUSA costs. Replace the default regional
weights in `data/weights_template.csv` with the best available gallon-exposure estimates.

The repository's `data/market.csv` is a reproducible snapshot generated on 2026-08-11 from
EIA's public historical XLS workbooks when no API key was available. The original workbooks
are archived under `data/raw/eia/2026-08-11`, and their URLs, SHA-256 hashes, observation
ranges, normalization rule, and matched-week counts are in `data/market.provenance.json`.
`data/weights.csv` uses MUSA's 2025 Form 10-K store counts grouped into the three configured
EIA/PADD regions. `data/weights.provenance.json` records the state mapping and the 60 Rocky
Mountain/West Coast stores excluded because no matching series is configured. Store count is
still only a proxy; replace it if regional gallon-exposure estimates become available.

`data/actuals.csv` contains company-reported quarterly values from 2019Q1 onward. Its field
definitions, extraction date, issuer-release URLs, and disclosure notes are recorded in
`data/actuals.provenance.json`. Refresh both files together when a new quarter is reported,
using the three-month columns from MUSA filings or earnings exhibits. Preserve the original
exhibits and record any restatement or definition change; never fill a missing company figure
with an estimate. `data/actuals_template.csv` remains available as a blank schema.

Then run the nowcast:

```bash
python -m musa_nowcast.cli \
  --market data/market.csv \
  --weights data/weights.csv \
  --actuals data/actuals.csv \
  --quarter 2026Q3 \
  --start 2026-07-01 \
  --end 2026-09-30 \
  --as-of 2026-09-20 \
  --gallons-million 1200
```

Add `--json` for machine-readable output. The command exits with a clear validation error
when inputs are incomplete or inconsistent.

### Geographic retail challenger

`MUSA_GEO_RETAIL_CHALLENGER_V1` uses point-in-time SEC state-store counts and the finest
available official EIA retail series (state, then East Coast subdivision, then PADD), while
leaving the production wholesale proxies and four model features unchanged. It downloads
official XLS files directly and does not require an EIA API key or browser automation:

```bash
python -m musa_nowcast.geo fetch --start 2019-01-01 --end 2026-09-27
python -m musa_nowcast.geo evaluate --as-of 2026-09-27
```

The preserved test did **not** pass. On the identical 22-quarter backtest, GEO-A had 3.33 cpg
MAE and 81.8% directional accuracy versus production's 3.13 cpg and 90.9%. Its Q3 2026 retail
estimate is 29.44 cpg versus production's 29.54 cpg. It remains experimental and production
is unchanged. See [`docs/GEO_CHALLENGER.md`](docs/GEO_CHALLENGER.md) for the frozen design,
explicit PADD 4/5 exclusions, artifacts, gate, and commands.

### Casey's generalization test

`data/caseys/actuals.csv` contains 28 company-reported quarterly fuel margins from F2020
through F2026. Casey's fiscal year runs from May 1 through April 30, and its disclosed target
is fuel margin in cents per gallon excluding credit-card fees. The issuer states that the
fuel category excludes wholesale fuel and terminal activity. Exact source releases, field
definitions, overlap checks, and the Fikes acquisition break are recorded in
`data/caseys/actuals.provenance.json`.

Run the reproducible Casey's backtest with:

```bash
python -m musa_nowcast.cli \
  --market data/market.csv \
  --weights data/caseys/weights.csv \
  --actuals data/caseys/actuals.csv \
  --company "Casey's" \
  --backtest
```

The same pre-specified model used for MUSA **does not pass** for Casey's. Across 20
expanding-window test quarters, its MAE is 3.12 cents per gallon versus 3.12 for the
same-quarter prior-year baseline, with 50.0% directional accuracy. Over the latest eight
quarters, MAE is 2.53 cents versus 2.57 for the strongest baseline, again with 50.0%
directional accuracy. Mean paired improvement is only 0.01 cents and its approximate 95%
lower bound is -1.15 cents. The tiny unrounded MAE edge is neither material nor stable, so
`validated` remains false.

The historical weights deliberately use a Midwest-only proxy. The 2026 Form 10-K does not
disclose quarterly gallon exposure by state, and Fikes changed the footprint during F2025.
Stress tests using 93.3% Midwest / 6.7% Gulf Coast and 90% / 10% produce the same trust-gate
failure; details are in `data/caseys/weights.provenance.json`. This makes the negative result
robust enough to reject the current specification, but not to promote those proxy weights for
a production Casey's forecast.

With all 13 complete F2027 Q1 market weeks, the failed model emits an experimental estimate
of 42.70 cents per gallon and a wide 36.34-49.06 range. That number must not be treated as a
validated earnings signal. Casey's should remain on the prior-year-quarter baseline unless a
new, pre-specified model using better geographic/rack inputs passes a fresh leakage-safe test.

The reported interval is a directional 90%-style band based on expanding-window backtest
RMSE, with an additional incomplete-quarter penalty. It is **not** a statistically exact confidence
interval: public proxies omit procurement basis, inventory accounting, local pricing actions,
and contract-specific RIN monetization.

## Interpretation safeguards

1. Do not compare the proxy's absolute retail-minus-wholesale spread directly with MUSA's
   reported margin. Only the calibrated model performs that translation.
2. A `validated: false` result is a stop sign. `beats_baseline` alone is insufficient because
   the trust gate also requires a material improvement, enough test quarters, and directional
   accuracy. Treat a failed output as a market dashboard, not a predictive model.
3. Do not replace the supply/RIN scenario with a generic fixed addition unless historical
   disclosures demonstrate that stability.
4. Recreate each historical forecast using only data available before that earnings release.
   Revised data can otherwise introduce look-ahead bias.
5. Archive every weekly input and model output so forecasts cannot be rewritten after earnings.
6. Margin per gallon is not earnings. Provide a separate, documented gallons assumption when
   estimating total dollar contribution.

## Development

```bash
python -m pytest
python -m compileall -q musa_nowcast tests
```

Public endpoints change, and repeatable investment research requires versioned raw inputs. The
EIA downloader writes the selected series and retrieval metadata, but callers should also version
the generated CSV and provenance file. Company-reported quarterly observations still require
analyst review because disclosure labels and definitions can change between filings.
