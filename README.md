# MUSA regional fuel-cost tracker

This repository implements a deliberately conservative market-cost proxy for Murphy USA (MUSA). It prefers observed regional rack prices and uses EIA spot prices only as explanatory fallbacks. It does **not** label the result as MUSA's landed acquisition cost.

## Quick start

```bash
python3 tracker.py build --prices data/example_prices.csv --config data/series_catalog.csv --output output/proxy.csv
python3 tracker.py validate-spots --history data/history_template.csv
python3 -m unittest discover -s tests -v
```

`build` selects a rack observation only when the series is marked reliable and has at least 80% of expected observations in the trailing 90 days. Otherwise it uses the region's configured EIA spot fallback and adds separately supplied terminal basis, freight, and ethanol-blending estimates. Missing adjustments are never silently treated as zero: the output is withheld and explains why.

The example prices are illustrative plumbing data, not investment data. Replace them with licensed/vendor rack history and dated estimates before use. See [the methodology](docs/METHODOLOGY.md) and [data dictionary](docs/DATA_DICTIONARY.md).

## Historical validation gate

Before a spot series may be used in a live estimate, `validate-spots` estimates this first-difference model against MUSA's reported quarterly retail fuel margin:

`Δ margin_t = α + β_GC Δ Gulf_t + β_NYH Δ NYH_t + ε_t`

The command reports coefficients, R², adjusted R², leave-one-out cross-validated R², directional accuracy, and sample size. The gate requires at least 20 quarters, adjusted R² ≥ 0.10, cross-validated R² > 0, and ≥ 55% directional accuracy. Failure leaves both spot series explanatory-only; it does not authorize them as landed-cost substitutes. No historical outcome is claimed in this repository because MUSA margin observations and point-in-time EIA extracts are not checked in. Supply those observations in `history_template.csv` to make the test reproducible.

