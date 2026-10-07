# MUSA uncertain-quarter estimator V1

`MUSA_UNCERTAIN_QUARTER_ESTIMATOR_V1` is a prospective shadow estimator. It mechanically combines
a source-verified **retail-margin** QTD/current-period disclosure with a remaining-period estimate
using observed **gallon share**, never calendar-day share. Retail-plus-retail and all-in-plus-all-in
combinations are allowed in their separate estimators; mixed-basis combinations are rejected.
Numeric ranges propagate as low/high scenarios;
qualitative evidence and absent verified numeric evidence return no partial-quarter estimate.

It does not change the production forecast, fit disclosure coefficients, or emit calibrated tail
probabilities. Those require the separately governed historical audit and prospective evidence.

## Replay discipline

Replays are labelled `RETROSPECTIVE_MECHANICAL_REPLAY`, never prospective validation. They require
separate disclosure-period end, disclosure availability, and remaining-market `as_of` timestamps.
Missing observed gallon share or a point-in-time remaining-period estimate blocks the calculation;
calendar-day fractions and revised market history are forbidden substitutes. Ranges must preserve
`shadow_low <= shadow_central <= shadow_high`. The seeded Q2 2025 replay is intentionally blocked
until PIT gallons and a June 16 remaining-period market vintage are archived.

`musa-uncertain-quarter --replay-json <record.json>` preserves the source record and writes either
an explicit PIT-data block or the low/central/high mechanical shadow. It never fills a missing
field from a calendar proxy.

## Separate modelled-gallon-share research route

Strict replay accepts only `OBSERVED_COMPANY_GALLON_SHARE`. A distinct command,
`musa-uncertain-quarter --modelled-gallon-share-replay-json <record.json>`, accepts
`PIT_MODELLED_GALLON_SHARE` only when the record contains all of:

- `gallon_share_as_of` no later than the disclosure cutoff;
- a frozen `gallon_share_model_version`; and
- `gallon_share_input_hashes` for the PIT inputs.

This evidence type is not an observed company gallon share. The output remains
`RETROSPECTIVE_MECHANICAL_REPLAY`; it must never be labelled prospective validation. A
historical current-vintage market file without original availability timestamps cannot support a
remaining-period or production forecast reconstruction.
