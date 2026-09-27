# Prospective margin shadow scorecard

Margin-model research is in maintenance mode. Production and the three frozen timing
challengers run prospectively at each checkpoint; their specifications may not be changed in
response to results.

## Archive a checkpoint

Run this after refreshing market data and before MUSA reports the quarter:

```bash
python -m musa_nowcast.shadow checkpoint \
  --quarter 2026Q3 \
  --start 2026-07-01 \
  --end 2026-09-30 \
  --as-of 2026-09-28
```

The command refuses to overwrite a checkpoint or create one if the quarter already appears in
`actuals.csv`. It stores a JSON snapshot under `data/shadow/checkpoints` and appends four rows
to `checkpoint_ledger.csv`. Each row records the forecast, range, coverage, latest market week,
checkpoint path, and SHA-256 hash.

The first Q3 2026 checkpoint records:

| Model | Retail margin |
| --- | ---: |
| Production | 29.54 cpg |
| Timing A | 29.49 cpg |
| Timing B | 27.98 cpg |
| Timing C | 28.04 cpg |

Maximum dispersion is 1.56 cpg. The checkpoint uses 11 of 12 expected weeks and market data
through 2026-09-14.

## Append the reported result

After MUSA reports, first enter the filing-derived result in `data/actuals.csv` with its
provenance. Then score a specific frozen checkpoint:

```bash
python -m musa_nowcast.shadow score \
  --checkpoint data/shadow/checkpoints/EXACT_CHECKPOINT.json \
  --actual-cpg REPORTED_CPG \
  --reported-at YYYY-MM-DD \
  --source-url OFFICIAL_FILING_OR_RELEASE_URL
```

Scoring appends one row per model to `data/shadow/scorecard.csv`, including absolute error and
year-over-year directional correctness. It rejects conflicting actuals, missing source URLs,
post-result checkpoints, and duplicate scoring. One quarter is descriptive; model promotion
still requires repeated prospective evidence and a separately frozen decision rule.
