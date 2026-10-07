# MUSA partial-quarter margin research V1

`MUSA_PARTIAL_QUARTER_MARGIN_V1` is a disclosure ledger and tail-risk research object. It is
not a replacement for the frozen production point forecast and it does not emit probabilities
until enough clean prospective observations exist to calibrate them.

`data/partial_quarter_disclosures.csv` preserves contemporaneous management evidence using only
four categories: `NUMERIC_CURRENT_MONTH`, `NUMERIC_QTD`, `QUALITATIVE_CURRENT_MONTH`, and
`QUALITATIVE_REGIME`. Numeric anchors retain the disclosed metric and date range. Qualitative
statements remain categorical; they must never be translated into a fabricated cents-per-gallon
input.

The intended eventual sequence is: disclosed partial-quarter anchor, observed market path for the
remaining weeks, mechanical market state (`RISING_SQUEEZE`, `NORMAL_CAPTURE`,
`FALLING_CAPTURE_EXPANSION`, or `WHIPSAW`), then a calibrated tail distribution. Until
prospective calibration exists, output is limited to the anchor and an `UNCALIBRATED` tail-risk
classification. Q2 2025 and Q2 2026 are historical examples used to define the research object,
not valid evidence for promotion.

Future collection must archive the original release/call material, publication time, observation
period, exact metric definition, and source URL before earnings. Q4 2026 onward is the first
clean prospective evaluation period.

## PIT history audit

`data/partial_quarter_disclosure_history.csv` is the 22-quarter production-backtest audit frame.
`SOURCE_VERIFIED / TRUE` means contemporaneous evidence was reviewed and classified. A quarter is
only eligible for `SOURCE_VERIFIED / FALSE / NONE` after the relevant pre-cutoff releases, updates,
calls, and conference materials have been reviewed. `PENDING_SOURCE_AUDIT / UNRESOLVED` is neither
evidence of absence nor a model input.

The ledger keeps presence separately from content, plus disclosure target and exact quarter
fraction observed. Evidence strengths are frozen: `NUMERIC_ACTUAL_QTD`,
`NUMERIC_EXPECTED_CURRENT_MONTH`, `NUMERIC_GUIDANCE`, `QUALITATIVE_CURRENT_TREND`, and
`QUALITATIVE_GENERAL`. The completed ledger may be used for descriptive auditing only; it may not
be used to tune thresholds or fit a tail-probability model on these same 22 outcomes.

`data/partial_quarter_disclosure_audit.csv` freezes the documentary procedure for each row. The
mandatory source order is: earnings releases; investor presentations and operations updates;
earnings-call transcripts; SEC 8-K/10-Q filings; then conference or investor-day materials. A
negative conclusion requires all five source types, the search window, cutoff timestamp, URLs,
archived source hashes, and completion timestamp. Only then may the row become
`COMPLETED_NO_DISCLOSURE_FOUND / FALSE`; a source found after the cutoff is real evidence but
must be marked unusable for that historical forecast.

`data/partial_quarter_source_checks.csv` is the append-only, source-level trail. Each checked
source gets its own locator, publication/availability dates, cutoff, matched-disclosure result,
raw-evidence identifier, hash, and audit result. These row-level checks support four terminal
quarter states: `DISCLOSURE_USABLE_AT_CUTOFF`, `DISCLOSURE_EXISTS_BUT_NOT_USABLE_AT_CUTOFF`,
`COMPLETED_NO_DISCLOSURE_FOUND`, and the non-terminal `PENDING_SOURCE_AUDIT`.
