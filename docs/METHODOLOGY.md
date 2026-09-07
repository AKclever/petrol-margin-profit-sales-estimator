# Model methodology and limitations

## What is observable—and what is not

The tracker estimates an **observable market-cost proxy**: a reproducible combination of market rack or spot observations and explicit logistics/blending adjustments. MUSA's actual **landed acquisition cost is unobservable** outside the company. It can differ because of contract timing, supplier discounts, inventory accounting, renewable-credit economics, losses, terminal fees, freight contracts, product mix, geography, and hedging. The proxy must therefore never be described as MUSA's cost or used to reverse-engineer reported margin without uncertainty.

The issuer's reported retail fuel margin is the validation target supplied from its filed
results. Preserve the company-specific definition, fiscal calendar, and restatements in the
input notes; do not mix merchandise margin, wholesale gallons, or alternative fuel metrics.
Models and coefficients are validated separately for each issuer.

## Source hierarchy

1. A reliable, geographically matched regional rack series is the market-cost anchor.
2. A nearby rack plus an explicit terminal-basis estimate is second best.
3. EIA Gulf Coast and New York Harbor spot series are fallback explanatory variables only, and remain so unless the historical validation gate passes.

A rack series is reliable only when its catalog record says `reliable=true`, its provenance is auditable, and trailing 90-day completeness is at least 80%. The model records the chosen source and all adjustments for every observation.

## Price construction

For an E10 retail grade derived from a neat-gasoline (E0) quote:

`proxy = 0.90 × market gasoline + 0.10 × ethanol + terminal basis + freight + taxes`

All terms are normalized to dollars per finished gallon. An E10 quote is not blended again. Ethanol, terminal basis, and freight must be dated explicit estimates; a missing required term blocks the estimate rather than becoming zero. Taxes are excluded by default so the proxy can be compared with a fuel margin that excludes retail taxes. Any tax-inclusive use requires an explicit tax series.

Terminal basis is preferably estimated as the trailing median difference between a matched rack and its benchmark (same grade, ethanol specification, and day). Freight represents terminal-to-store transport, including fuel surcharge where applicable. Ethanol is a terminal-equivalent per-gallon quote; document whether RIN value is embedded. The current implementation accepts these adjustments as columns because contracts and geography are user-specific rather than publicly observable.

## Timing and aggregation

Daily records use the observation date, not download date. Quarterly validation uses arithmetic means of available daily observations and the fiscal quarter attached to the reported MUSA metric. Never forward-fill across more than five business days. Avoid look-ahead by archiving the retrieved EIA vintage and vendor file checksum.

Weekly nowcast inputs are normalized to ISO-week Monday. Feature construction admits only
complete Monday-through-Friday market weeks contained within the company reporting quarter;
a weekly spot observation whose Friday falls after quarter-end is excluded. The same rule is
applied to historical tests and live quarters.

## Spot-price validation

Levels can create spurious fit, so the test uses quarter-over-quarter changes. Both spot changes enter together; an intercept is included. The small-sample validation reports in-sample and leave-one-out statistics. Passing the gate shows only historical explanatory usefulness, not causation and not equivalence to acquisition cost. Structural breaks, regional mix changes, and pandemic quarters should be disclosed, with sensitivity runs rather than silently removed.

The live hierarchy changes only after the gate passes on at least 20 aligned quarters with adjusted R² ≥ 0.10, leave-one-out R² > 0, and directional accuracy ≥ 55%. Even after passing, spot remains labelled `spot_fallback`; regional rack remains preferred.

## Nowcast validation and trust gate

The quarter-level nowcast uses ridge regression to estimate the year-over-year margin change
from year-over-year changes in spread, falling-price capture, rising-price squeeze, and
volatility. The predicted change is shrunk by 50% before it is added to MUSA's reported margin
for the same quarter one year earlier. This seasonal anchor reflects the strong recurring
quarterly pattern while allowing current market information to move the estimate conservatively.

Backtesting is expanding-window and time ordered. For every test quarter, the regression is
fit only to earlier company actuals; future actuals never enter that quarter's fit. The model
is compared with both the mean of the then-available history and the same-quarter prior-year
margin. A nowcast is marked `validated: true` only when all of these conditions hold:

- at least eight genuinely out-of-sample test quarters are available;
- MAE is at least 10% lower than the stronger of the two baselines; and
- year-over-year directional accuracy is at least 55%.

The approximate 95% lower confidence bound on the paired per-quarter MAE improvement must
also remain above zero. This guards against declaring success from a small average advantage
that is not stable across test quarters.

The MAE-improvement and directional requirements must also pass independently over the most
recent eight test quarters. This recent-regime gate prevents older volatility, including the
pandemic period, from validating a model that has stopped working in current conditions.

Passing is evidence of historical usefulness, not a guarantee. Revised EIA history can still
create vintage look-ahead, and provisional geographic weights remain a separate reason for
caution. Production evaluation should archive the data vintage used on every forecast date.

## Cross-company validation

Reusing the method for another retailer does not authorize transferring MUSA's fitted
coefficients or declaring success from an in-sample fit. The company must have a consistently
defined quarterly target and enough history to rerun the full expanding-window gate. Its
fiscal dates and geographic exposure must be used directly.

The bundled Casey's test uses the unchanged feature specification, ridge penalty, shrinkage,
and trust thresholds. It has 28 reported quarters and therefore 20 out-of-sample tests. The
model fails because its 3.12-cent MAE is effectively identical to the seasonal baseline,
directional accuracy is 50%, and the paired-improvement lower bound is negative. Gulf-weight
sensitivities do not change that decision. The Casey's output remains experimental unless a
new specification is defined before evaluation and passes a fresh or properly nested test;
tuning features against these same 20 outcomes and reporting the best variant would create
model-selection leakage.

