# Prospective information capture V1

Q4 2026 onward lives under `data/prospective/`. Historical production backtests, disclosure
audits and blocked replays remain in their existing historical directories. Q2 2025 remains
`RETROSPECTIVE_MECHANICAL_REPLAY` / `BLOCKED_PIT_EVIDENCE_INSUFFICIENT`.

## Weekly workflow

Run a fresh capture before each checkpoint:

```sh
musa-prospective capture-market
musa-prospective checkpoint --quarter 2026Q4 --start 2026-10-01 --end 2026-12-31 \
  --market-manifest data/prospective/market/<capture>/manifest.json
```

The first command prints the manifest path needed by the second. Each capture is exclusive-create
and retains exact EIA workbook bytes, SHA-256 hashes, original observation dates, normalization,
and capture/availability timestamps. Without original release timestamp evidence, `available_at`
is conservatively the first capture timestamp. Later captures never backdate availability or
overwrite earlier observations. Publication time is not inferred from a week label.

The checkpoint archives production and risk outputs, exact CSV/evidence bytes, code snapshots,
input hashes, disclosure state, gallons state, remaining-period forecast and partial shadow.
No complete quarter weeks can produce a production block early in the quarter. Download failure
leaves an incomplete capture without a manifest; do not use that directory for a checkpoint.

Historical data downloaded today are the training vintage known at this capture. This does not
convert any historical backtest into a PIT validation. Capture begins on the actual execution
date; nothing is backdated to October 1. These commands do not install a recurring scheduler.

## Gallons preregistration

`musa-prospective freeze-gallons --input <gallons.json>` freezes a single initial record per quarter.
The input must include `quarter`, `quarter_start`, a timezone-qualified `information_cutoff`,
`methodology_version`, `update_rule`, `input_hashes`, and `expected_gallon_share_by_month` mapping
the three YYYY-MM months to fractions summing to one. Derive these from a registered gallons
methodology, not calendar lengths or the illustrative percentages in a discussion. All methods
and source evidence should be retained with the provided input artifact. An October 7 initial
freeze is labelled `LATE_INITIAL_FREEZE`, not a quarter-start forecast.

No initial record can be replaced. V1 does not support updates until an executable, preregistered
update rule exists. Monthly shares support only full-month QTD disclosures; partial-month
disclosures need a separate registered weekly/daily gallon allocation. These are modelled shares,
always labelled `PIT_MODELLED_GALLON_SHARE`, never observed company gallons.

## Remaining-period forecasts and disclosures

The repository currently has no frozen gallons model or registered
`MUSA_REMAINING_PERIOD_MARGIN_V1` implementation. V1 records explicit blocks until those
components are supplied; the whole-quarter production nowcast cannot silently stand in for a
June/November remainder forecast.

Provide a remaining-period forecast artifact with `--remaining <file.json>`: `quarter`,
`period_start`, `period_end`, `target`, `margin_cpg`, `methodology_version`,
`forecast_created_at`, `information_cutoff`, and `input_hashes`. Archive this weekly even without
disclosures. Weekly forward forecasts cover the next day through quarter end. For assimilation,
the artifact must cover the entire undisclosed period (including elapsed days after the disclosed
period), not just days after the checkpoint. Preserve each separately when those periods differ.

Provide company evidence with `--disclosure <file.json>`: `quarter`, `period_start`, `period_end`,
`target`, `margin_low_cpg`, optional `margin_high_cpg`, `available_at`, `information_cutoff`,
`raw_path`, and `raw_sha256`. The raw bytes are copied and verified. No supplied source means
`NOT_CHECKED`, not an assertion that management made no disclosure.

Use `--gallons <frozen record>` to attach the previously frozen shares. Retail numeric QTD
evidence can be assimilated only with a matching retail remaining estimate, matching quarter
periods and evidence available at the checkpoint cutoff. Qualitative or all-in disclosures remain
context. Actuals remain blank until the separate score command is run after earnings.

## Scoring

```sh
musa-prospective score --checkpoint <checkpoint.json> --actual-cpg <retail_actual> \
  --reported-at <earnings_timestamp_with_timezone> \
  --source <archived_earnings_release> --source-url <issuer_url>
```

Scores use frozen predictions, preserve source bytes and hashes, and cannot overwrite a prior
score for that checkpoint. Report production and shadow absolute errors and their difference.
Missing shadow forecasts remain unscored; no post-result estimate is substituted. Multiple
weekly checkpoints of one quarter are correlated observations, not independent validation trials.
