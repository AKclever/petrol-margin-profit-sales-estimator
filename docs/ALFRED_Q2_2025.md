# June 16, 2025 market vintage reconstruction

The user-supplied acquisition kit was inspected and run with the official FRED API credential
supplied in process memory. The key is not written to source, a secrets file, raw archives or
source URLs. The original Downloads kit is unchanged. The adopted script is
`scripts/musa_alfred_q2_2025_vintage_fetch.py`; it requires `FRED_API_KEY`, refuses to overwrite an
existing capture directory, defaults to training history from 2019 and validates nonempty,
complete responses for the requested vintage. Its date ceilings are specific to June 16, 2025.

Raw observations, vintage-date lists, CSVs and redacted request provenance are archived under
`data/incoming/alfred_vintages/2025-06-16`. API requests use
`realtime_start = realtime_end = 2025-06-16`. Capture date remains October 7, 2026.

Run the offline validator and aligner with:

```sh
python -m musa_nowcast.alfred \
  --manifest data/incoming/alfred_vintages/2025-06-16/manifest.json \
  --output data/historical_pit/2025Q2/2025-06-16
```

It verifies raw/provenance hashes, response vintage, pagination completeness, finite levels,
date windows, weekdays, exact observation ceilings, normalized values and series identity. It
aligns all five source series into complete three-region ISO-Monday market rows. The June 9 retail
observation cannot be paired with June 13 wholesale: that wholesale observation is unavailable
in this vintage. Thus the latest complete market week is June 2 (wholesale period ending June 6).

The three PADD retail inputs are regular **all formulations**, not conventional-only. This is
the same basis as the production EIA retail identifiers. Wholesale inputs are conventional
regular, matching the configured EIA spot series. The previous eia.py comment saying retail was
conventional-only was corrected; no prices, features or production coefficients were changed.

This validates **date-level market-vintage reconstruction**. An observation's returned
`realtime_start = 2025-06-16` describes membership in the requested snapshot; it is not evidence
that every historical value was first published on that date. Intraday publication timestamps
remain null. Cutoff membership in the list of revision dates is not required for an arbitrary
snapshot date (ALFRED explicitly supports arbitrary vintage dates).

The aligned file is isolated from live market.csv. No current revised observations, final
Q2 gallons or eventual Q2 margin were fed into the reconstruction. The new validation record
supersedes the market-data blocker for subsequent research, while prior blocked mechanical
replay records remain historical records. A scored replay still requires a registered gallons
method, a registered remaining-period margin method and PIT evidence for training actuals and
weights. A current-code historical experiment is `RETROSPECTIVE_PIT_RULE_REPLAY`, not prospective
validation. No shadow or same-time production forecast is claimed by this acquisition step.

Sources:

- https://alfred.stlouisfed.org/help/downloaddata
- https://alfred.stlouisfed.org/series?seid=GASREGECW
- https://alfred.stlouisfed.org/series?seid=WGASNYH
- https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMM_EPMR_PTE_R10_DPG&f=W

## Completed separate research rule replay

The acquisition-only validation above remains unchanged. A separate, scored research replay
now lives in `data/historical_pit/2025Q2/2025-06-16/rule_replay_v1`. Its evaluation role is
`RETROSPECTIVE_MECHANICAL_REPLAY`, with methodology origin `RETROSPECTIVE_PIT_RULE_REPLAY`.
These rules were specified in October 2026, not registered in June 2025. The outcome was already
known to the researcher; freezing the prediction before the separate scoring command does not
make this a blind experiment or prospective validation.

The rule specification is `data/historical_pit/q2_2025_rule_spec.json`. No coefficients or rules
were selected by comparing alternative Q2 predictions against its outcome. Production code,
strict replay rules, taxonomy and previous blocked replay records are unchanged.

### Evidence and methods

The archive contains 24 dated EIA WPSR Table 1 releases and 21 company earnings releases covering
all 25 training quarters from 2019Q1 through 2025Q1. Each company margin was checked against the
three-month table's explicit current/prior-year columns and quarter-end month, not just a number
found somewhere on the page. Sources were retrieved now; issuer publication dates establish
historical availability at date-level resolution. These are not original contemporaneous captures,
and dated issuer pages alone cannot prove that a page was never subsequently edited.

The first parser failed one 2021 Q4 table because spacer rows put its year header farther down.
That failure remains in `replay_sources_v1/sources.json`. The corrected, raw-backed check is
appended in `verification_v1.json`; the original trail was not rewritten.

The current production weights refer to year-end 2025 and are therefore ineligible. This replay
uses the archived 2024 10-K (filed February 20, 2025), verifies its existing raw hash, re-extracts
state counts and normalizes only the same three configured regions. Both training and predictions
use those weights. The comparator is **the production formula using PIT weights**, not a forecast
that actually existed at that historical timestamp, nor the old backtest with future weights.

The expected April-May gallon share is **65.9731%**, labelled `PIT_MODELLED_GALLON_SHARE`.
It is a national-demand proxy, not a MUSA company-observed or validated company-volume estimate.
Archived weekly finished-gasoline products supplied supplies the expected volume profile. Unknown
June weeks use 52-week-prior demand scaled by observed QTD demand growth. Weekly daily rates are
allocated uniformly across each week when splitting quarter/disclosure boundaries. This is an
explicit within-week allocation assumption, not substitution of a bare calendar fraction.
No final Q2 2025 company gallons, July 2025 release or today's revised demand history enters it.

`MUSA_REMAINING_PERIOD_MARGIN_V1` forecasts **June 1-30 only**, using the last complete paired
market week (June 2) and flat forward-filled regional prices for unavailable paired weeks.
It transfers the frozen quarterly four-feature ridge change mapping (alpha 2, shrinkage 0.5)
to June-only feature differences versus June 2024, with the 2024Q2 retail margin as seasonal anchor.
The remaining margin is **27.5363 cents/gallon**. Transferring quarterly coefficients and a quarterly
anchor to a monthly target is an **unvalidated research assumption**. In particular, the anchor
is not an observed June 2024 retail margin. This result does not establish monthly forecasting skill.

### Frozen result and separate scoring

`forecast.json` retains null outcomes/errors and the raw, normalized, specification and model
hashes. Its actual creation timestamp is October 2026; its information cutoff is June 16, 2025.
The May 31 disclosure period end, June 16 publication date, forecast creation timestamp and
information cutoff are separate fields. `training.json` retains the fitted regression, verified
training margins, region weights and features; `gallon_proxy_days.json` retains every demand
allocation. The scoring command checks all frozen hashes before fetching the July 30 outcome.
It writes `scoring/score.json` without modifying the frozen forecast.

The conditional research result is:

- Mechanical shadow: **28.8978 cpg**.
- Same-cutoff production formula with PIT weights: **33.3154 cpg**.
- Company Q2 2025 actual: **29.2 cpg**.
- Shadow absolute error: **0.3022 cpg**.
- Comparator absolute error: **4.1154 cpg**.
- Incremental absolute-error improvement: **3.8132 cpg**.

This one case is an illustration under newly specified proxy/transfer assumptions, not proof
of a systematic forecasting advantage. The original strict replay remains blocked because
company-observed April-May absolute gallons are missing. The existing earlier modelled replay
record also remains unchanged; the new rule replay does not retroactively upgrade its status.

Use fresh directories to reproduce; every archive/output refuses overwrite:

```sh
python -m musa_nowcast.pit_replay capture --sources /path/to/new-source-archive
python -m musa_nowcast.pit_replay capture-disclosure --sources /path/to/new-source-archive
python -m musa_nowcast.pit_replay verify --sources /path/to/new-source-archive
python -m musa_nowcast.pit_replay predict --sources /path/to/new-source-archive --output /path/to/new-replay
python -m musa_nowcast.pit_replay score --forecast /path/to/new-replay/forecast.json --output /path/to/new-score
```

Network recapture may produce different HTML bytes, so the retained original hashes are the
audit evidence for this run. Offline prediction uses the retained source archive.
