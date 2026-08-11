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

The first version is useful enough to answer whether a quarter appears closer to 30¢, 35¢,
or 40¢ while making the model's limitations visible:

- constructs a gallon-weighted (or best available proxy-weighted) regional basket;
- refuses to silently reweight weeks with missing regions;
- distinguishes spread, falling-price capture, rising-price squeeze, and volatility;
- calibrates those features to reported retail margins with regularized regression;
- performs leave-one-quarter-out validation against a historical-mean baseline;
- widens its interval when the current quarter is incomplete;
- models supply/RIN economics as historical low/base/high scenarios, not false precision;
- optionally converts all-in cents per gallon and expected gallons into dollars; and
- emits Markdown for analysts or JSON for a spreadsheet/dashboard pipeline.

It uses only the Python standard library at runtime. No market observations or company
figures are bundled because fabricated sample data can too easily be mistaken for an
investment data set.

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

Use one observation per region per week. The date should represent a consistent weekly
observation convention. The loader rejects duplicate region/week pairs.

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

At least six quarters are required; 8–12 or more consistently defined quarters are strongly
preferred. Dates must match MUSA's reporting calendar. `supply_rin_cpg` is the difference
between all-in fuel contribution and retail margin under a consistent definition.
`gallons_million` is optional and currently retained as source context; the live forecast's
gallons assumption is supplied separately.

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

Copy `data/actuals_template.csv` to `data/actuals.csv` and enter reported quarterly values
directly from MUSA filings or earnings exhibits. The repository intentionally does not fill
blank company figures or ship guessed investment data. Record the filing URL and extraction
date in research notes and preserve the original exhibit.

Then run the nowcast:

```bash
python -m musa_nowcast.cli \
  --market data/market.csv \
  --weights data/weights.csv \
  --actuals data/actuals.csv \
  --quarter 2026Q3 \
  --start 2026-06-29 \
  --end 2026-09-27 \
  --as-of 2026-09-20 \
  --gallons-million 1200
```

Add `--json` for machine-readable output. The command exits with a clear validation error
when inputs are incomplete or inconsistent.

The reported interval is a directional 90%-style band based on leave-one-quarter-out RMSE,
with an additional incomplete-quarter penalty. It is **not** a statistically exact confidence
interval: public proxies omit procurement basis, inventory accounting, local pricing actions,
and contract-specific RIN monetization.

## Interpretation safeguards

1. Do not compare the proxy's absolute retail-minus-wholesale spread directly with MUSA's
   reported margin. Only the calibrated model performs that translation.
2. A `beats_baseline: false` result is a stop sign. Treat the output as a market dashboard,
   not a predictive model.
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
