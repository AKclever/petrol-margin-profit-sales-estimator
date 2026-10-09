# Historical expansion, margin-floor pressure and fuel-basis experiments

Canonical run: `data/history_floor_basis/2026-10-07_evaluation_v6`.
Role: **DEVELOPMENTAL_CURRENT_VINTAGE_RESEARCH_NOT_STRICT_PIT**.
Production forecast, production actuals, market CSV and regional weights are unchanged.
No challenger passed the existing gate. Nothing is promoted.

## Historical expansion

Added 22 original SEC earnings exhibits, Q3 2013–Q4 2018, to a separate
research dataset. With the existing 30 targets this gives **52 reported
quarters, Q3 2013–Q2 2026**. Targets are retail margin, not all-in economics.

Every target retains its source URL, raw SHA-256, conservative publication
date, reported margin, exact gallons where supplied, and reconciliation state.
41 of 52 targets have a retail-contribution/gallons bridge within rounding;
11 are directly reported margins without that exact contribution bridge.
Among the 22 newly added targets, 11 have the bridge and 11 do not.
The latter are usable reported margin targets, not claimed fully reconciled
accounting reconstructions. Exact gallons remain unresolved in 2014Q3,
2014Q4, 2015Q2 and 2015Q3; rounded billion-gallon figures are not promoted
to exact gallons. Original Q4 2017 results are explicitly preliminary.
Subsequent restatements have not been audited.

Sources were original SEC earnings exhibits rather than digitized chart
points from the [historical presentation](https://www.sec.gov/Archives/edgar/data/1573516/000157351621000020/a2021investorpresentatio.htm).
Raw issuer releases are retained as supporting evidence. Q3 2013 includes
the spin-off transition; it is not an assertion of a uniform corporate
perimeter throughout that calendar quarter.

The first eight quarters seed training. Expanded evaluation has **44 OOF
quarters**: 18 earlier-regime quarters (2015Q3–2019Q4), four transition
quarters (2020), and the original 22 modern test quarters (2021Q1–2026Q2).
This does not turn the production champion into a 44-quarter validated model:
the earlier engine starts in 2013 and the later engine preserves production's
2019 training start. There is no pooled accuracy score or blind pooling of
older training observations into modern production.

Baseline mean absolute error is 2.60¢ on the 18 earlier tests, 7.73¢ on the
four 2020 transition tests, and 3.13¢ on the original 22 modern tests.
Across all reported targets, mean margin is 13.56¢ before 2020, 23.25¢ in
2020, and 27.23¢ from 2021 onward. This is descriptive evidence of a changed
level, **not proof that costs caused the change**.

All regular and all-grade market quarters passed exact complete-week
coverage checks. Original earlier outcome publication dates precede their
subsequent target quarter-end cutoffs. EIA histories are nevertheless
today's vintage, and historical release timing/revisions are not reconstructed.
The fixed regional weights are not historical store-footprint estimates.

## Frozen experiments and results

Rules were archived in `data/history_floor_basis_spec_v1.json` before
evaluation. Residual challengers require eight earlier, already published
OOF outcomes within the same regime, ridge alpha 2, and 50% correction
shrinkage. No feature selection, combined challenger or threshold retuning.
Each error comparison below uses identical quarters.

### Margin-floor pressure

Features: previous-quarter YoY change in reported station/store operating
expense per gallon, plus signed negative directly reported same-store
gallon growth. This is **MUSA own cost/volume pressure**, not measured
industry wages or competitors' required margins. Expense includes payment
fees and other effects. QuickChek creates a material acquisition/perimeter
confound in 2021 onward. These are consolidated ratios, not like-for-like
station cost measures. No expense is added mechanically to gross margin.

Pre-2016 expense is blocked because consolidated costs can include ethanol.
Earlier direct SSS disclosure coverage remains incomplete. The older regime
has only seven eligible feature rows, insufficient for eight training
residuals plus a held-out test; 2020 is similarly blocked.

On 14 modern matched tests, production MAE **2.303¢ → 2.309¢** with the
cost/volume challenger: no improvement. Recent-eight MAE improves from
2.154¢ to 2.025¢, but overall directional accuracy falls from 85.7% to 71.4%.
Gate fails; the industry hypothesis is not disproved by this limited own-
company proxy, but this implementation does not justify changing forecasts.

### All-grade gasoline retail

Substitutes EIA all-grade regional gasoline retail for regular gasoline.
Gasoline wholesale, geographical weights, target basis and model remain
unchanged. All-grade EIA composition is **not MUSA's actual grade mix**.
It remains mismatched against conventional regular spot wholesale, so this
tests one component of measurement error, not complete fuel-basis matching.

Modern 22-quarter MAE **3.133¢ → 3.103¢**, less than 1% improvement.
Recent-eight MAE slightly worsens, 2.154¢ → 2.158¢. Earlier 18-quarter MAE
2.598¢ → 2.577¢; 2020 MAE 7.726¢ → 7.707¢. All three regimes fail the gate.
Fresh regular EIA prices match production retail and wholesale to the
specified .001¢ tolerance; the fresh-regular control reproduces baseline
MAE to numerical precision. No revised-vintage advantage is claimed.

### Diesel context

Separate residual feature: fixed-geography weighted YoY change in EIA
diesel retail prices. This is **context only**, not a company diesel weight,
diesel margin forecast, or diesel replacement cost. Gasoline wholesale is
never relabelled diesel acquisition cost.

On 14 modern tests (2023Q1–2026Q2), production MAE **2.303¢ → 1.919¢**,
a 16.7% reduction; recent-eight MAE **2.154¢ → 1.695¢**.
However, full matched-sample directional accuracy falls from 85.7% to 78.6%,
and the paired-improvement confidence interval's lower bound is **−0.191¢**.
The fixed gate fails. On ten older matched quarters, error worsens
**2.526¢ → 2.663¢**, reinforcing the need for separate regimes.
2020 lacks enough same-regime training residuals and is not scored.

This is the most interesting lead of these experiments, not a proven edge.
Freeze it as a research challenger and test future quarters without tuning
to this already examined history. These runs do not authorize a current-
quarter point adjustment or any claim of prospective validation.

## Artifacts and rerun

Original SEC archive: `data/history_floor_basis/2026-10-07_sec_v2`.
Issuer releases and 11 EIA workbooks:
`data/history_floor_basis/2026-10-07_capture_v1`.
Canonical targets, frozen input manifest, normalized markets, detailed
predictions, feature evidence, training-quarter lists, exclusions and
metrics: `data/history_floor_basis/2026-10-07_evaluation_v6`.

Capture attempts and parser-development runs are retained append-only.
Evaluation v1/v2 failed before scoring; v3/v4/v5 are superseded parser-
development artifacts, **not authoritative results**. v6 fixes rounded-
gallon/comparative extraction, contribution labels and preliminary status,
and verifies complete-week coverage. It does not retune experiment features.

```bash
.venv/bin/python -m musa_nowcast.history_floor_basis --out data/history_floor_basis/NEW_UNIQUE_RUN
.venv/bin/python -m pytest -q
```

An existing output directory is refused. Data/code hashes are frozen before
forecast errors are calculated. All 144 tests pass, including temporal
training eligibility, no cross-regime residual pooling, no held-out actual
leakage, rounding safeguards and contribution reconciliation.

Public [EIA fuel-price series](https://www.eia.gov/dnav/pet/pet_pri_gnd_dcus_nus_w.htm)
are benchmarks, not MUSA delivered acquisition costs. Nothing in this
experiment infers supplier invoices or a company grade/diesel mix.
