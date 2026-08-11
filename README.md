# MUSA geographic exposure sensitivity

This repository replaces the look-ahead-biased practice of applying one latest
store footprint to every historical period. `data/geographic_exposure.csv` has
one row per state and quarter, so openings are reflected in the period in which
they are assumed to occur.

## Inputs and estimation status

MUSA does not disclose state-level gallons in the supplied project materials.
Consequently, every volume weight is explicitly marked `volume_weight_estimated=true`.
The quarterly state store series is also a reconstructed working assumption and
is marked `store_count_estimated=true`; replace it with dated company location
files or a verified filing extract before using the result as an investment
conclusion. The component estimates are:

* state/quarter store count, linearly interpolated between explicit 2023Q1 and
  2025Q4 assumptions in `generate_inputs.py`;
* state traffic index (relative visits/throughput opportunity);
* MUSA format mix (`express_share`);
* metropolitan mix (`metro_share`); and
* `regional_volume_index`, the placeholder for disclosed regional-volume clues.

Indices are relative, not gallons. All state margin values are scenario proxies,
not reported MUSA margins. Keeping these fields separate makes the assumptions
auditable and easy to replace.

## Weighting schemes and uncertainty

`model.py` runs five plausible schemes: stores only; traffic adjusted; traffic
plus format; fully adjusted; and a regional-information-heavy tilt. Format and
metro effects are capped through modest multipliers rather than treated as direct
gallon ratios. For each scheme, the state margin proxy is weighted separately in
each historical quarter. Its difference from that quarter's store-only reference
is applied to the supplied 30.0 cpg base margin.

The reported final estimate is the equal-quarter average for 2023Q1–2025Q4.
Geographic-weight uncertainty is **max minus min final estimate across schemes**,
not a statistical confidence interval. Run:

```sh
python generate_inputs.py
python model.py
python -m unittest discover -s tests -v
```

The checked-in `outputs/geographic_sensitivity.csv` gives every quarter/scheme
result, while `outputs/geographic_uncertainty.json` gives the final range and
spread. To integrate with a larger model, call `model.run(base_margin_cpg=...)`
and replace equal-quarter aggregation with the model's actual quarterly gallons.
