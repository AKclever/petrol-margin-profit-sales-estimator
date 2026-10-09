# Multi company earnings event replay

A local research workflow now archives dated earnings evidence and generates separate, overlap-aware margin shadows for MUSA, Casey's and Couche-Tard. Historical information transfer has mixed results: a small MUSA improvement, a Casey deterioration and almost no Couche-Tard change. No model passes the existing promotion gate.

## Information flow

Each company retains its own market-based baseline and target definition. MUSA retail margin is not Casey's RIN-inclusive fuel margin or Couche-Tard's US company-operated before-payment-fee margin. Peer results enter as surprises relative to their own earlier-trained baseline, not as absolute margins averaged across companies.

When a dated report arrives, eligible unreported companies receive new checkpoints. Selection requires positive overlap with the target fiscal period, and periods and source hashes stay attached. Calendar overlap is an exposure proxy, not observed company gallons. No overlap or insufficient historical training produces an explicit unchanged state; an earnings release is not forced to move every company's estimate.

This first workflow covers **completed-period pre-earnings nowcasts**. Baseline market inputs are not used for dates before the period ends. In-quarter forecasts and two-quarter-ahead forecasts need separately archived, as-of baseline inputs; they are not implemented by pretending completed-period data existed earlier.

## Frozen update rule

The specification `data/earnings_event_replay_spec_v1.json` was saved before scoring. For each recipient/donor pair, fit one through-origin ridge loading from at least eight earlier published matching observations in the same start-date regime. Penalty 10 and loading bounds zero to one are fixed. A zero loading is preserved, not replaced to manufacture an update.

The donor surprise is weighted by its calendar overlap fraction with the recipient period. The recipient correction is half the average of all eligible weighted transfers. It is recomputed from the original baseline at each checkpoint; the same report is never added repeatedly. This is a small transfer model, not a fitted shared latent state-space model.

Earlier recipient outcomes must be published before the current cutoff and their periods must end before the current recipient starts. Historical donor selections use those earlier recipients' own pre-report cutoff, not later releases discovered with hindsight. Pre-2020, 2020 and 2021-onward start-date regimes are calibrated separately. Acquisition and accounting differences remain limitations, not hidden cents-per-gallon corrections.

All releases on the same date are grouped. Date-only evidence is eligible from the next-day cutoff; only publications strictly before that cutoff enter. A checkpoint with cutoff equal to the recipient reporting date is explicitly **before that date's reports**; the recipient actual is excluded. Report order within a day is not inferred.

## Historical results

The archive contains 128 targets: 44 MUSA, 42 Casey and 42 Couche-Tard predictions. It uses the unchanged expanded-history peer forecasts, not the newer failed challengers. Casey F2027Q1 is not spliced in from a differently trained model merely to extend the archive.

All-target results include unchanged forecasts when transfer is blocked. On modern target periods:

- MUSA, 22 quarters: MAE 3.133¢ to 3.057¢. Fourteen support transfers; on those identical rows, MAE 2.303¢ to 2.183¢.
- Casey, 21 quarters: MAE 2.605¢ to 2.697¢. Thirteen support transfers; on those rows, 2.649¢ to 2.797¢.
- Couche-Tard, 22 quarters: MAE 4.153¢ to 4.158¢. Fourteen support transfers; on those rows, 3.457¢ to 3.465¢.

Across the full older-plus-modern history, MUSA MAE is 3.331¢ to 3.294¢, Casey 2.798¢ to 2.842¢ and Couche-Tard 4.151¢ to 4.138¢. These combined figures are descriptive; no blind cross-regime calibration is performed. Each company's baseline and shadow comparison uses identical targets.

All company/modern promotion gates fail. MUSA's improvement is modest, not a demonstrated forecasting edge. Original large misses remain substantial: Q3 2023 moves from 35.383¢ to 35.309¢ against 28.7¢ actual; Q2 2026 from 28.495¢ to 28.980¢ against 35.1¢ actual. Q3 2022 remains unchanged because transfer training is insufficient.

The replay records 101 potential overlapping earnings-trigger checkpoints, of which 42 change the estimate. These are repeated observations within target quarters, **not 101 independent backtest quarters**. Among modern event-trigger checkpoints, ten Casey and twenty-one Couche-Tard checkpoints change; no modern MUSA checkpoint changes after its initial completed-period checkpoint. Existing eligible peer information can still alter MUSA's initial shadow, but this archive supplies no incremental modern overlapping pre-report update afterward. Final checkpoints can also update previously trained loadings as earlier recipient outcomes become available.

Historical market data are current vintages, publication dates are date-only, and baseline creation timestamps were not archived at the historical cutoffs. Therefore this is `DEVELOPMENTAL_CURRENT_VINTAGE_PUBLICATION_FILTERED_NOT_STRICT_PIT`. Source ordering alone cannot upgrade it to prospective validation. The exact archived raw-byte availability and company geography limitations remain.

## Local workflow

Reproduce the full replay into a new directory:

```sh
.venv/bin/python -m musa_nowcast.earnings_event_replay replay \
  --out data/earnings_event_replay/NEW_UNIQUE_RUN
```

A custom dataset uses the same `records` schema as the canonical `dataset.json`. Each target requires company, quarter, fiscal start/end, target basis, baseline prediction, baseline information cutoff and source URL/hash. For unreported targets, use null actual and null publication date. For scoring, preserve seasonal baseline. Never replace the archived baseline with a forecast produced after its result.

To append supplied, reviewed earnings evidence and produce new shadows:

```sh
.venv/bin/python -m musa_nowcast.earnings_event_replay ingest \
  --ledger data/prospective/earnings_events.jsonl --event REVIEWED_EVENT.json
.venv/bin/python -m musa_nowcast.earnings_event_replay update \
  --dataset CURRENT_BASELINES.json --ledger data/prospective/earnings_events.jsonl \
  --as-of YYYY-MM-DD --out data/prospective/earnings_checkpoints/NEW_UNIQUE_RUN
```

An event uses the target schema plus reported actual, publication date, capture timestamp and raw source path. Ingestion checks the raw SHA-256, target basis and finite values, rejects conflicting duplicates and is idempotent for identical re-ingestion. Advisory file locks protect concurrent local appends. Updating merges matching reported outcomes without replacing their baseline; baseline/period conflicts fail. Source hashes are checked again.

Each update freezes copies and hashes of the exact dataset, event ledger, specification and code into a new directory. Unreported completed periods receive checkpoints; already reported periods do not. Reusing an output directory fails. An unreported company's actual never enters its own prediction. This command generates research shadows only and does not modify production files.

The workflow still needs reviewed release extraction and supplied current baseline files. It is **not an automatic earnings-release watcher, continuous market updater, cloud deployment or independent PIT verifier**. Those integrations must preserve dated raw inputs, baseline creation timestamps and the same evidence checks. No scheduler, paid service or GitHub push was added in this implementation.

## Artifacts and tests

Canonical replay: `data/earnings_event_replay/2026-10-08_v3/`. It retains input snapshots, the normalized dataset, all checkpoints frozen before scoring, donor loadings and training pairs, exclusions, final scorecards and paired event diagnostics. Earlier runs remain intact; v2/v3 strengthen local ingestion/update guards without changing model predictions or specification.

```sh
.venv/bin/python -m pytest -q tests/test_earnings_event_replay.py
```

Tests cover own/future-outcome invariance, publication cutoffs, overlap, pre-period blocking, no compounding, basis/nonfinite guards, append-only idempotence and conflicts, immutable update outputs and archived training trails. Production, the official Q3 MUSA forecast and existing disclosure/risk taxonomies remain unchanged.
