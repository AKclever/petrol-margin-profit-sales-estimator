# Model methodology and limitations

## What is observable—and what is not

The tracker estimates an **observable market-cost proxy**: a reproducible combination of market rack or spot observations and explicit logistics/blending adjustments. MUSA's actual **landed acquisition cost is unobservable** outside the company. It can differ because of contract timing, supplier discounts, inventory accounting, renewable-credit economics, losses, terminal fees, freight contracts, product mix, geography, and hedging. The proxy must therefore never be described as MUSA's cost or used to reverse-engineer reported margin without uncertainty.

MUSA's reported retail fuel margin is the validation target supplied by the user from its filed results. Preserve the filed definition and restatements in the input notes; do not mix merchandise margin, wholesale gallons, or alternative fuel metrics.

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

## Spot-price validation

Levels can create spurious fit, so the test uses quarter-over-quarter changes. Both spot changes enter together; an intercept is included. The small-sample validation reports in-sample and leave-one-out statistics. Passing the gate shows only historical explanatory usefulness, not causation and not equivalence to acquisition cost. Structural breaks, regional mix changes, and pandemic quarters should be disclosed, with sensitivity runs rather than silently removed.

The live hierarchy changes only after the gate passes on at least 20 aligned quarters with adjusted R² ≥ 0.10, leave-one-out R² > 0, and directional accuracy ≥ 55%. Even after passing, spot remains labelled `spot_fallback`; regional rack remains preferred.

