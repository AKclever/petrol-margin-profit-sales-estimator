# Weekly retail-adjustment challenger V1

Implemented as `musa_nowcast.weekly_adjustment`, separately from production, timing challengers,
regime risk, partial-quarter replay rules and the frozen Q3 pre-earnings stack. The specification
`data/weekly_adjustment_spec_v1.json` was written before this model was fitted. The Q3 price path
and previous historical errors were already known when its mechanisms were designed; this is
not independent validation, a historical PIT backtest or a genuinely prospective Q3 challenger.

## Replacement-cost and retail-delay mechanisms

For each region and week, replacement-cost proxy is 50% current wholesale spot plus 50% prior
weekly wholesale spot. It is not observed MUSA delivered acquisition cost: freight, taxes,
inventory terms and negotiated supplier economics are unobserved. EIA retail prices likewise
are regional regular-gasoline benchmarks, not MUSA's company-specific gasoline/diesel prices.
The calibration absorbs systematic differences; it does not identify each missing cost component.

The model measures the adjustment lag in the observed regional price path rather than forecasting
unseen MUSA pump prices. In a rising cost week, any cost increase not matched by a retail increase
creates a squeeze impulse. In a falling cost week, any cost decrease not matched by a retail
decrease creates a capture impulse. Separate states retain half of their prior value each week
and add the respective new impulse. States do not reset at quarter boundaries. Eight consecutive
valid transitions are required for initialization; residual startup influence is below 1/256.
Missing internal market weeks cause a block rather than a price fill.

This preserves ordering: the same price observations in a different sequence produce different
state histories. A sharp drop after a squeeze can create a capture state while the earlier squeeze
state still decays. These are engineering assumptions with fixed one-week half-life, not fitted
causal pass-through estimates.

## Gallon-weighted quarterly calibration

The three weekly features are retail less replacement-cost proxy, **negative** squeeze state,
and capture state. Weekly volume weights use national finished-gasoline products supplied,
multiplied by days of the ISO week inside the quarter. Regional allocation uses configured
store-count exposure weights. The combined weights sum to one. These are explicit proxies,
not observed company weekly or regional gallons.

The official EIA demand workbook is archived with its raw hash and first-capture timestamp:
https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WGFUPUS2&f=W
The reported weekly daily rate is assigned uniformly within the model's ISO-week bin. Its native
week-ending convention and ISO retail-price bin are an alignment approximation, not exact
transaction-level fuel-volume timing.

All calendar quarter days are represented. The initial partial week is included. Where the
final partial week has no complete in-quarter paired price observation, prices and demand from
the preceding complete week are persisted and every such day is marked imputed. This narrowly
defined boundary approximation is not a long-horizon flat-price forecast or an internal-gap fill.
For Q3 2026, 89 days have in-quarter weekly price support and the final **3 days are imputed**.
Weekly averages still are not daily observations for those 89 days.

Only quarterly reported company retail margins supervise the model. A standardized ridge model
fits year-over-year quarterly margin changes to year-over-year weighted feature changes, with
alpha 2, nonnegative coefficients on the three signed features, an unpenalized intercept,
fixed 0.5 shrinkage and the previous year's same-quarter reported retail margin as anchor.
Nonnegative ridge is solved by enumerating its eight possible active sets, not by searching
lag assumptions or research variants against forecast errors.

The fitted linear mapping allocates a margin to each region/week relative to the prior-year
aggregate. The gallon-weighted weekly allocation must exactly reproduce the quarterly prediction.
These weekly allocations are **latent model outputs**, not identified MUSA weekly margins.
Many weekly cost/pass-through explanations could fit the same quarterly targets.

## Evaluation and Q3 result

Complete successful output: `data/weekly_adjustment/q3_2026_v1_run2`.

- Q3 2026 challenger retail margin: **26.1671 cents/gallon**.
- Production rerun on the same price/weight/company inputs: **28.94 cents/gallon**.
- Modelled weighted squeeze state: **9.9150 cpg**.
- Modelled weighted capture state: **4.8469 cpg**.
- Fitted independent squeeze coefficient: **zero** under the sign-constrained fit.
- Spread and capture coefficients remain active. The quarterly data do not support a separate
  incremental squeeze coefficient under this specification; squeeze effects may already be
  represented by the contemporaneous spread. This does not mean the economic squeeze disappeared.

The allocated weekly regional-weighted margin reaches about **37.24 cpg in the August 3 bin**,
versus roughly 23-26 cpg across many other bins. That illustrates sequence-sensitive dynamics,
not a claim about actual company weekly results.

Expanding-window evaluation holds out company targets and compares only the same 21 eligible
quarters with production:

- Challenger MAE: **3.7893 cpg**, versus production **3.1219 cpg**.
- Challenger RMSE: **4.6944 cpg**, versus production **4.0482 cpg**.
- Directional accuracy: **61.90%**, versus production **90.48%**.
- Recent-eight MAE: **2.3614 cpg**, versus production **2.1535 cpg**.
- Fixed historical gate: **failed**. No promotion or production-point adjustment.

Q1 2019 is explicitly excluded because the January-starting market history does not provide the
required pre-quarter warmup. Production's full backtest has 22 quarters; this identical-row
comparison has 21. The first execution encountered this startup boundary before fitting;
its raw demand capture and failure record remain under `q3_2026_v1`. The eligibility handling
was corrected without changing lag, feature, calibration or outcome-dependent rules, and
the successful evaluation used a new directory.

Historical price/demand series were captured now, and configured historical comparison weights
are static current weights. Therefore these held-out errors are **current-vintage retrospective
research diagnostics**, not historical publication-vintage proof. Existing history also informed
the research hypotheses. The worse metrics are retained; there was no post-result retuning.

The previous frozen 29.54 cpg official pre-earnings selection remains untouched, as do all prior
replays and forecast checkpoints. The 26.17 cpg figure belongs only to this newly designed shadow.
Q3 actual/error fields remain null. Do not apply production's 3.13 cpg MAE as a calibrated
uncertainty interval for these weekly latent allocations.

## Use and tests

```sh
python -m musa_nowcast.weekly_adjustment \
  --market data/market.csv --weights data/weights.csv --actuals data/actuals.csv \
  --output /path/to/new-append-only-output
```

Existing output directories are refused. The run archives demand bytes, source metadata,
model specification, input/code snapshots, fitted coefficients, held-out predictions and
weekly regional allocations. Market CSV should be an archived complete-pair snapshot.
For a new live checkpoint the market input's capture must predate its information cutoff;
this V1 CLI is explicitly the completed Q3 2026 research exercise, not a general PIT scheduler.

Tests cover asymmetric state decay, sequence sensitivity, missing-data refusal, startup warmup,
sign constraints, 92-day/weight reconciliation, end-stub exclusion of future prices and exact
weekly-to-quarter prediction reconciliation. Full suite: **82 tests passing**.
