# MUSA geographic retail challenger V1

`MUSA_GEO_RETAIL_CHALLENGER_V1` tests whether finer public retail-price geography improves
the validated production model. It is a frozen challenger, not a replacement for production.

## Frozen design

- Retail prices use the official EIA weekly regular-gasoline series in this order: state,
  PADD 1 subdivision for East Coast states, then PADD.
- Weekly store weights use the most recent MUSA state-store table that had been filed by that
  date. The tables come from 2017-2025 Forms 10-K and are not backfilled with today's footprint.
- The wholesale side is unchanged: New York Harbor for East Coast exposure and U.S. Gulf
  Coast for Gulf Coast and Midwest exposure.
- PADD 4 and PADD 5 stores receive zero model weight and an explicit exclusion reason because
  the production model has no validated wholesale proxy for those regions. Included weights
  are renormalized; the detailed weekly file retains excluded stores and counts.
- The feature set remains `spread`, `falling_capture`, `rising_squeeze`, and `volatility`, with
  the same ridge penalty, 50% change shrinkage, and expanding-window fitting as production.
- City prices, fuel-formulation adjustments, new features, and parameter tuning are outside V1.

## Reproduce

No EIA API key or browser automation is required. The fetch command downloads official EIA
historical XLS files and SEC filing HTML, archives the exact bytes, and writes SHA-256 hashes:

```bash
python -m musa_nowcast.geo fetch \
  --start 2019-01-01 \
  --end 2026-09-27 \
  --output-dir data/geo \
  --raw-root data/raw/geo

python -m musa_nowcast.geo evaluate \
  --geo-dir data/geo \
  --market data/market.csv \
  --weights data/weights.csv \
  --actuals data/actuals.csv \
  --output-dir data/geo_research \
  --quarter 2026Q3 \
  --start 2026-07-01 \
  --end 2026-09-30 \
  --as-of 2026-09-27
```

The installed entry point is equivalent: `musa-geo fetch` and `musa-geo evaluate`.

## Promotion gate and preserved result

The comparison uses the identical 22 out-of-sample quarters for both models. Promotion
requires at least 10% lower full-sample MAE, no loss of directional accuracy, a positive
paired-improvement 95% lower bound, and the same improvement and direction conditions over
the latest eight quarters.

The 2026-09-27 run failed every material improvement test:

| Measure | Production | GEO-A |
| --- | ---: | ---: |
| Full-sample MAE | 3.13 cpg | 3.33 cpg |
| Directional accuracy | 90.9% | 81.8% |
| Recent-eight MAE | 2.15 cpg | 2.30 cpg |
| Recent-eight direction | 75.0% | 62.5% |
| Q3 2026 retail estimate | 29.54 cpg | 29.44 cpg |

Mean paired improvement was -0.20 cpg and its approximate 95% lower bound was -0.49 cpg.
`data/geo_research/gate_status.json` therefore records `NOT_PROMOTED`. The negative result is
retained; the production model and its 29.54 cpg retail estimate remain unchanged.

## Artifacts and availability caveat

`data/geo/geo_state_weekly.csv` is the auditable state/week construction;
`data/geo/geo_basket.csv` is the weekly model input. `state_store_counts.csv` and
`state_series_map.csv` document filing vintages and mappings. `geo.provenance.json` records
source URLs, hashes, ranges, row counts, and the frozen research-spec hash.

SEC weights are point-in-time by filing date. The current EIA workbooks do not preserve the
original publication/revision vintage for each historical observation, so repeated future
captures should remain archived. That limitation applies even though champion and challenger
were evaluated on the same current EIA vintage.
