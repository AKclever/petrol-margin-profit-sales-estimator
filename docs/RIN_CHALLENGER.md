# EPA D6 RIN candidate layer

This layer is separate from the validated retail-margin model. It downloads the official EPA
EMTS weekly RIN price and transaction-volume tables, preserves immutable raw exports with
SHA-256 hashes, and constructs a D6-only weekly candidate series.

## Reproducible workflow

From the repository root:

```powershell
python -m musa_nowcast.rin fetch
python -m musa_nowcast.rin evaluate
```

The fetch command connects directly to EPA's anonymous Qlik Engine endpoint; it does not use
browser automation or a browser extension. It downloads the price and volume export objects,
joins D6 prices to **separated** transaction volumes by week, transfer year, RIN vintage, and
QAP type, then combines QAP types with a volume-weighted average. RIN vintages remain separate.

Outputs:

- `data/rin_weekly_candidate.csv`: transformed D6 weekly observations.
- `data/rin.provenance.json`: source, object IDs, capture policy, hashes, and row counts.
- `data/raw/epa_rin/<capture timestamp>/`: immutable official CSV exports.
- `data/raw/epa_rin/<capture timestamp>/d6-weekly-normalized.csv`: immutable normalized
  capture with its own SHA-256 hash.
- `data/rin.vintage_diff.json` and `.csv`: latest capture-to-capture revision summary and
  row-level changes. The same files are archived inside each capture directory.
- `data/rin_research/quarter_features.csv`: pre-specified quarterly D6 feature.
- `data/rin_research/checkpoint_ledger.csv`: point-in-time availability audit.
- `data/rin_research/evaluation.csv`: expanding-window exploratory predictions.
- `data/rin_research/gate_status.json`: promotion decision and current prospective read.
- `data/rin_research/manifest.json`: hashes for all research inputs and outputs.

## Pre-registered challenger

The only primary feature is the year-over-year normalized change in the arithmetic mean of
weekly, same-year-vintage D6 VWAP. The target is MUSA's reported supply/RIN contribution. The
baseline is the prior-year same-quarter supply/RIN contribution. A single zero-intercept
coefficient is fitted using only preceding quarters in each expanding-window prediction.

No D4, generation, available-RIN balance, ethanol, or geographic-price feature is included.
The validated retail-margin model and its supply/RIN scenario remain unchanged.

## Point-in-time limitation

EPA's live export provides historical observations but not the original release timestamp or
revision vintage of each row. Therefore the downloader conservatively assigns the capture time
as `available_at` for every observation. The historical backtest is reported as exploratory and
cannot pass the leakage-safe gate. Repeated future captures create the prospective vintage
record needed for a valid point-in-time evaluation.

Each provenance record also contains the source dataset, first and latest observation weeks,
raw and normalized hashes, row count, frozen research-spec hash, and unique build ID. Vintage
diffs ignore capture timestamps and compare only price and transaction volume, so a new capture
does not falsely classify every historical row as revised.
