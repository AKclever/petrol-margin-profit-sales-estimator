# MUSA margin regime-risk monitor V1

`MUSA_MARGIN_REGIME_RISK_V1` is a research-only diagnostic that does not alter the frozen
production point forecast. It addresses the observed hypothesis that market-to-margin translation
risk rises during transitions, rather than relitigating the production model using the same small
quarterly sample.

It reports four pre-specified mechanisms:

- `RISING_SQUEEZE_RISK`: retail trails qualifying wholesale increases; possible production
  overestimate risk.
- `FALLING_CAPTURE_EXPANSION`: retail trails qualifying wholesale declines; possible production
  underestimate risk.
- `ANCHOR_REVERSAL_RISK`: an extreme same-quarter prior-year anchor conflicts with the current
  wholesale move; the production shrinkage anchor may be mechanically unreliable.
- `STRUCTURAL_CAPTURE_UNCERTAINTY`: adaptive feature distance is high or the trailing reported
  MUSA margin floor differs materially from earlier reported history.

Thresholds are frozen in `musa_nowcast/risk.py`: qualifying weekly move 5¢, capture gap 4¢,
anchor extreme 80th/20th percentile, anchor reversal 25¢, structural margin shift 5¢, and high
out-of-distribution distance 2σ. They must not be retuned based on Q3 2026 or later outcomes.

Run it alongside—not instead of—the production nowcast:

```bash
python -m musa_nowcast.risk \
  --start 2026-07-01 --end 2026-09-30 --as-of 2026-09-30 \
  --output data/risk_research/q3_2026.json
```

The initial research question is prospective: do elevated flags precede larger production
absolute errors, and do the squeeze/capture flags correctly anticipate error direction? No flag
may change the production forecast until that evidence has accumulated over several clean future
quarters.

## Prospective ledger

Freeze a pre-result checkpoint using the official production forecast selected for that quarter,
then score it only after the issuer reports. The expected-error rule is frozen: `ELEVATED` means
`ABOVE_NORMAL_RISK`; it does not prescribe whether the point forecast should move up or down.

```bash
python -m musa_nowcast.risk_ledger checkpoint \
  --quarter 2026Q3 --start 2026-07-01 --end 2026-09-30 --as-of 2026-09-30 \
  --production-forecast-cpg 29.54

python -m musa_nowcast.risk_ledger score \
  --checkpoint data/risk_research/checkpoints/EXACT_CHECKPOINT.json \
  --actual-margin-cpg REPORTED_CPG --reported-at YYYY-MM-DD \
  --source-url OFFICIAL_RELEASE_URL
```

The append-only scorecard preserves the production error, risk levels, OOD distance, historical
support, frozen expected-error class, realized error class, and only the mechanism consistent
with the realized error direction. A bidirectional quarter does not retrospectively invalidate
the opposing mechanism.
