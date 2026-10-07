# Additional fixed-rule research replays and the October 7 checkpoint

Two additional completed-month disclosures were located in issuer-hosted earnings-call PDFs,
archived, text-checked and visually reviewed. The original disclosure taxonomy, 22-quarter audit
statuses and strict company-observed-gallons replay were not changed. This is a separate research
extension, not a declaration that the 22-quarter documentary audit is complete.

The rules were registered before these new predictions in
`data/historical_pit/additional_replay_spec_v1.json`. The new module is
`musa_nowcast/additional_replays.py`; the original Q2 2025 module and frozen outputs are unchanged.
The same alpha 2, shrinkage 0.5, four-feature quarterly change regression, 52-week demand proxy
and flat future price assumption were retained. No parameter search or outcome-driven retuning
was performed.

There are two explicit extensions, not a claim that the initial historical methods existed in 2023:
the remaining forecast may span two months rather than June alone, and approximately stated
management numbers are represented as their stated values in an **approximate research** bucket.
No invented bounds surround those approximate numbers. The quarter-to-shorter-period transfer
assumption remains unvalidated. A named month completed before the call supplies calendar period
boundaries; a still-open month without an explicit observation end does not.

## Q1 2023: the shadow was substantially worse

The February 2, 2023 call discussed completed January retail-only margins at approximately 19 cpg.
This is approximate preliminary management commentary, not an exact audited monthly actual.
Source: https://s22.q4cdn.com/506259022/files/doc_financials/2022/q4/4Q22-MUSA-Earnings-Transcript-Final.pdf
(page 7).

Using the February 2 ALFRED snapshot and demand releases available by that date:

- Modelled January share: 33.4564%.
- Remaining February-March estimate: 14.4418 cpg.
- Mechanical shadow: 15.9668 cpg.
- Same-cutoff production formula with eligible weights: 22.0621 cpg.
- Eventual actual: 23.2 cpg.
- Absolute errors: shadow 7.2332 cpg; comparator 1.1379 cpg.
- Incremental improvement: **minus 6.0953 cpg**.

The 2022 year-end 10-K was not yet filed at the cutoff; the latest eligible store weights therefore
come from the 2021 filing. All 16 training quarters through 2022Q4 were verified against eligible
issuer releases. The actual outcome was checked only in the separate scoring step against:
https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/2023/Murphy-USA-Inc.-Reports-First-Quarter-2023-Results/default.aspx

This is an important failed example. Roughly two-thirds of the quarter remained dependent on the
remaining-period model, which substantially underestimated it. Do not remove it or change the rules
to improve this result.

## Q2 2024: a small improvement, but both estimates missed badly

The May 2, 2024 call discussed completed April preliminary retail margins at approximately 24.5 cpg.
Source: https://s22.q4cdn.com/506259022/files/doc_financials/2024/q1/Q12024_MurphyUSA_EarningsCallTranscript.pdf
(page 6).

Using the May 2 ALFRED snapshot and eligible demand releases:

- Modelled April share: 32.2325%.
- Remaining May-June estimate: 23.4485 cpg.
- Mechanical shadow: 23.7874 cpg.
- Same-cutoff production formula with eligible weights: 23.3640 cpg.
- Eventual actual: 29.7 cpg.
- Absolute errors: shadow 5.9126 cpg; comparator 6.3360 cpg.
- Incremental improvement: **plus 0.4234 cpg**.

The latest eligible weights come from the 2023 10-K. All 21 training quarters through 2024Q1
were verified. The existing provenance's comparative 2023Q4 source was published in 2025 and
was rejected for this cutoff. Its original February 7, 2024 release was instead acquired and checked.
The actual outcome was separately verified against:
https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/2024/Murphy-USA-Inc.-Reports-Second-Quarter-2024-Results/default.aspx

## What the three examples say

Including the previous Q2 2025 replay, these three selected research cases have descriptive average
absolute errors of **4.4827 cpg for the shadow** and **3.8631 cpg for the comparator**. This is not a
representative validation sample: two disclosures are approximate, one is a more precise QTD result,
observed shares differ, the outcomes were already known to the researcher and the methods were
specified retrospectively. Neither the sample means nor a two-out-of-three improvement count
supports fitted probabilities, model promotion or a point-forecast adjustment.

Each prediction retains null outcomes in `replay/forecast.json`. Each score is appended separately
in `replay/scoring/score.json`. Both new forecasts and every input hash were checked against their
score records. Raw PDF, ALFRED JSON, WPSR CSV, coefficients, demand allocations and verified company
inputs are retained in `data/historical_pit/additional_replays_v1`. Availability is date-level public
call/source-release evidence, not a claim that these files were captured at the historical time.

## Current quarter: Q4 2026, not Q3

The latest daily capture completed on October 7, 2026. Retail observations reach October 5, but
the two required wholesale series reach September 25. The latest complete paired market week is
September 21. The production quarter feature rule begins on the first Monday inside a quarter;
therefore there are **zero complete Q4 feature weeks**. The unchanged production estimator correctly
remains blocked. No fresh production point forecast or calibrated Q4 interval is claimed.

The separate early-quarter research artifact is `data/prospective/early_q4_2026_v1/forecast.json`:

- Prior-year Q4 seasonal reference: **31.00 cpg**, a reference rather than a market-based forecast.
- Full-quarter flat-price research shadow: **21.70 cpg**.
- Production Q4 forecast: **null / blocked**.
- Company-anchored partial-quarter shadow: **null**, not produced by this exercise.

The 21.70 cpg figure assumes the last complete pre-quarter regional price pairs persist across
the whole quarter. It does not use observed Q4 wholesale/retail pairs. Given the failed Q1 2023
remaining-period result, this scenario is especially unsuitable for promotion to production.
Do not apply the 3.13 cpg production MAE as a calibrated uncertainty interval for this scenario.

For the recently completed **Q3 2026**, the fresh-capture production nowcast is **28.94 cpg retail**
(model interval 22.35-35.53 cpg), with 12/12 configured complete weeks. The separate supply/RIN
base scenario is 2.95 cpg, giving an all-in scenario of 31.89 cpg. This is a new October 7 checkpoint;
it does not overwrite the previously archived 29.54 cpg forecast. No Q3 actual was used or scored.

The fresh capture is under
`data/prospective/daily/2026-10-07T100115Z_4317dfd499d6450c98a7e9b42bff1075`.
The code still records historical training vintages here as current-capture history, not as
historical PIT validation. Existing inherited backtest trust-gate fields do not validate either
the new early-Q4 scenario or the approximate mechanical replays.

## Reproduction

Set `FRED_API_KEY` in the process environment, never in source or archived URLs. Use new output
directories: existing evidence is never overwritten.

```sh
python -m musa_nowcast.additional_replays capture --root /path/to/new-replay-archive
python -m musa_nowcast.additional_replays predict --root /path/to/new-replay-archive
python -m musa_nowcast.additional_replays score --root /path/to/new-replay-archive
python -m musa_nowcast.additional_replays live --manifest /path/to/live-market/manifest.json --root /path/to/new-live-shadow
```

The current live command is specific to this Q4 2026 early-quarter research checkpoint; the normal
weekly production workflow remains `musa_nowcast.prospective` / `musa_nowcast.daily_capture`.
