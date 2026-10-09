# Miss evidence workstreams — October 8, 2026

Production unchanged. No new correction coefficient or probability model is
fitted. This work separates a **source inventory**, reviewed reported peer
targets, live evidence capture, and future validation. It does not claim all
historical causes or all source audits are resolved.

## 1. All-quarter diagnostic evidence inventory

`data/miss_evidence/2026-10-08_v1/quarter_diagnostics.json` covers all **52**
reported MUSA quarters, with **208** separate dimension records:
company selling-price context, wholesale-proxy mismatch, market timing,
and accounting/perimeter evidence. It includes 44 historical OOF predictions;
the first eight seed quarters have no fabricated production errors.

Each quarter retains original earnings-release URL, SHA-256, publication date,
audit timestamp and dimension-specific source passages. Timing diagnostics
preserve wholesale movement, volatility, falling capture, rising squeeze
and largest weekly moves. Revenue gaps/SSS use the previously audited values;
older missing revenue reconstructions remain null, not zero.

**This is a source-level triage inventory, not a completed causal audit.**
Keyword matches are review candidates, not confirmed explanatory adjustments.
All 52 quarters retain `causal_explanation = UNRESOLVED` pending adjudication
against filings/calls as necessary. There are zero newly confirmed quantified
retail-specific accounting adjustments. Supplier invoices are not observed;
reported margin is not used to manufacture an acquisition-cost observation.
Original release-only coverage does not constitute an exhaustive filing,
transcript or historical disclosure-presence search.

## 2. Older peer evidence

Raw archive: `data/older_peer_evidence/2026-10-08_v1`.
Canonical reviewed artifact: `data/older_peer_evidence/2026-10-08_review_v4/review.json`.
Earlier review attempts are retained; v1/v2 failed before forecasts, v3 is
superseded by v4's all-quarter descriptive comparison.

Captured **49 Casey's original exhibits** (including multiple earnings and
prepared-remarks sources for some periods) and **17 Couche-Tard releases**.
The review reconstructs **18 Casey's quarterly reported margins** and
**13 Couche-Tard quarter/fee-reconciled margin records** from those older
sources. These are source observations, not necessarily all net additions
to the existing peer dataset; some periods overlap. Unparsed exhibits,
fiscal-period/basis gaps and conflicting figures are not labelled absent.

Casey's achieved quarterly margin is isolated from its annual goal and
merchandise margin. Its reported fuel margin includes RIN economics where
disclosed; it is **not a pure MUSA retail-margin target**. Couche-Tard records
retain US company-operated before-payment-fee margin, payment fees, fiscal
length/dates and acquisition context. The original accounting bridge is
checked, but full manual source/basis review remains pending where labelled.
Fiscal-quarter anchor gaps cause blocked forecasts, never substitution of a
different quarter's prediction.

Separate current-vintage expanding peer models now produce 35 Casey's and
33 Couche-Tard historical surprises, with earlier training and publication
filters. No MUSA correction is fitted. Market vintages and historical peer
exposure remain unverified; these are not strict PIT validation results.

Both peers now have eligible published surprise evidence for **all six**
original large-miss quarters. Both signs agree with the eventual original
production error in **4/6** large-miss quarters, but also **11/16** other
modern quarters. Thus this simple directional agreement is **not distinctive
to large misses** in this history.

The discordant large misses are worth preserving: Q4 2021 peer surprises
were negative even though MUSA production underestimated actual; Q1 2022
peer surprises were positive even though production overestimated actual.
This is a descriptive sign check, not a fitted forecast or probability.
There is no new sign threshold or regime-specific coefficient.

Older peer coverage helps test the evidence channel. It does **not** by itself
remove the all-feature model's minimum eight earlier same-regime complete-
residual requirement or the diesel survey break. No 2021 full-joint forecast
is manufactured by pooling later outcomes or blindly pooling older regimes.

## 3. Pump-price feasibility and manual intake

[MUSA's FAQ](https://www.murphyusa.com/murphyusa/faqs) says its website/app
station prices are refreshed frequently. This is a real company-price lead,
not proof of a free historical archive or an automated-research license.
[Published terms](https://www.murphyusa.com/murphyusa/legal) give a limited
personal-use license; automated collection permission has not been established.
No app reverse engineering, login, price scraping or paid purchase was done.

`data/pump_price_panel_plan_v1.json` defines a proposed 12 fixed pairs,
four each in East Coast, Midwest and Gulf Coast. **The station registry is
empty and blocked**, because verified identities and collection rights have
not been established. No invented stations or company gallon weights.
The manual intake command requires frozen MUSA/competitor identities and
addresses, source identity evidence, shared grade/payment/reward basis,
individual station timestamps within 15 minutes, and hashed raw evidence.
It archives immutable input copies and a paired price difference; that
difference is not a representative realized company price.

```bash
.venv/bin/python -m musa_nowcast.evidence_intake manual-price \
  --panel VERIFIED_FIXED_PANEL.json --observation MANUAL_OBSERVATION.json \
  --out data/pump_prices/NEW_UNIQUE_CAPTURE
```

Automated collection remains disabled. Actual station observations or written
source permission are needed to progress beyond this research/intake stage.

## 4. Numeric company disclosure handling

Fresh local issuer RSS capture archived **10** linked official releases.
`data/miss_evidence/2026-10-08_v1/live_disclosure_review_queue.json` records
checked sources and margin passages separately. The detected numerical
passages are in Q1/Q2 earnings results; they are not verified Q4 retail QTD
disclosures. Other channels remain unchecked, so this is not a completed
no-disclosure finding. All candidates require period, target and numerical
basis review. The daily capture implementation now creates this queue itself.

The existing prospective assimilation checks remain unchanged: retail target,
valid numeric bounds, observed period dates separate from disclosure
availability, raw source hash, explicit gallon-share evidence, and a
same-cutoff forecast of the exact undisclosed remainder. All-in disclosure
and qualitative commentary cannot enter the retail weighted average.

There is **no new live company-anchored estimate**. Q4 lacks a verified
numeric retail disclosure and registered live gallon-share/remaining-period
artifacts. These remain blocked rather than replaced by calendar weights or
an invented remainder forecast. Prior verified historical disclosures are
preserved without rewriting the frozen taxonomy or the 19 pending historical
source audits.

## 5. Prospective risk testing

Fresh local run:
`data/prospective/daily/2026-10-08T082621Z_8515efa8ed9d47d780d50aa71429d754/run.json`.
Source capture completed, including daily EIA wholesale history. Numerical Q4
production/risk forecasts remain blocked: no complete weighted market week
between October 1 and quarter end is yet available. No zero or proxy forecast
was substituted.

The fixed evaluation rule is archived in
`data/miss_evidence_workstream_spec_v1.json`: the first complete checkpoint
captured 3–7 UTC days after quarter end, before reported earnings, is the
primary trial. Daily/weekly checkpoints are secondary repeated observations.
Choose the checkpoint by this rule, never by best realized error.

`musa_nowcast.evidence_intake prospective` inventories archived checkpoints,
binds the selection code/spec hashes, selects at most one primary per quarter,
and groups later verified scores by their frozen NORMAL/ELEVATED risk state.
Current inventory has **four archived checkpoints, zero eligible primary
selections and zero primary scores**. Empty risk-group MAEs stay null. Risk
thresholds are unchanged; no predictive value is claimed yet.

Cloud deployment remains unactivated: authenticated billing-enabled project
is still required. Local evidence capture occurred today, but unattended
daily capture cannot be claimed. No cloud billing or paid resources were
enabled. Existing deploy instructions are updated for the review queue and
prospective selection rule.

## Verification and next outstanding work

159 tests pass: all-quarter scope, unchanged unresolved findings, quarterly
versus annual peer margin extraction, publication filters for the six misses,
manual-only price intake, fixed primary selection and non-assimilation of
unreviewed disclosures. Production CSVs/model and forecast logic are unchanged.

Outstanding documentary work: adjudicate candidate explanations against
filings/calls, resolve older peer parse/basis gaps and validate acquisitions.
Outstanding external evidence: verified pump station pairs/observations or
collection permission, eligible live numerical disclosure and registered
gallons/remainder inputs. Outstanding deployment: billing-enabled cloud access.
Those are explicit limits—not completed negative audits or model failures.
