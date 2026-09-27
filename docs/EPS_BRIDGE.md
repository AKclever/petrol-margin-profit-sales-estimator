# MUSA operating-to-EPS bridge V1

`MUSA_OPERATING_TO_EPS_BRIDGE_V1` converts production fuel economics and separately sourced
operating assumptions into an EPS nowcast and same-time consensus gap. It does not alter or
re-estimate the fuel model.

## Locked Q3 2026 fuel inputs

| Input | Value | Status |
| --- | ---: | --- |
| Retail fuel margin | 29.54 cpg | Production |
| Supply/RIN | 2.95 cpg | Production |
| All-in fuel margin | 32.49 cpg | Production |

Timing A/B/C remain shadow information and the D6 result remains a scenario. The bridge rejects
any Q3 input row that substitutes those experimental values.

## Calculation

```text
fuel contribution = gallons × all-in cents per gallon ÷ 100
total contribution = fuel contribution + merchandise contribution
EBITDA proxy = total contribution
               - store operating expense excluding payment fees
               - payment fees
               - SG&A
EBIT = EBITDA proxy - D&A
pretax income = EBIT - interest expense + other income/expense
net income = pretax income × (1 - tax rate)
EPS = net income ÷ diluted shares
surprise gap = EPS - same-time Street consensus
```

Payment fees are separate in V1, so the store-operating-expense input must exclude them. Blanks
never become zero. The command withholds EPS until volume, merchandise contribution, operating
costs, tax, shares, and consensus are all populated from documented forecasts or guidance.

## Current status and command

The current Q3 input row contains only the locked fuel values. The output is therefore
`BLOCKED_MISSING_INPUTS`, with the missing fields enumerated in
`data/eps_bridge/q3_2026_output.json`.

```bash
python -m musa_nowcast.eps_bridge \
  --input data/eps_bridge/q3_2026_inputs.csv \
  --output data/eps_bridge/q3_2026_output.json
```

Populate `q3_2026_inputs.csv` only with values whose source and as-of date are preserved. A
historical operating dataset and the separate volume champion should be brought into this
repository before backtesting or treating the bridge as an investable earnings nowcast.
