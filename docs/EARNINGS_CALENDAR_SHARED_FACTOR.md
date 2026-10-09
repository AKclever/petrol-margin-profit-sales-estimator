# Earnings calendar and shared retailer factor results

Neither new shadow reliably improves the large misses. The later earnings-calendar cutoff adds no new selected overlapping peer period in the modern archive; its modern predictions are unchanged. A shared monthly retailer-surprise factor slightly worsens modern pre-report accuracy. Keep production unchanged.

Both experiments use current-vintage market histories and dated company releases. They enforce release ordering but are not strict historical PIT validation or prospective evidence. Existing publication, fiscal-overlap, target-basis and acquisition limitations remain as described in [the evidence audit](HISTORICAL_EVIDENCE_EXTENSION.md).

## Frozen experiments

The specification `data/earnings_calendar_factor_spec_v1.json` was saved before the first scoring run. It defines two research approaches with quarter-end and final pre-report checkpoints, rather than four candidates selected afterward. No penalties, eligibility rules or shrinkage were retuned against their errors.

Inputs are the existing v3 peer predictions and archived MUSA production predictions. Peer surprises are reported margins minus earlier-trained predictions on each peer's own basis. Casey's RIN-inclusive reported fuel margin, Couche-Tard US company-operated before-payment-fee margin and MUSA retail margin remain distinct. Absolute margins are not averaged together.

### Earnings calendar update

At quarter-end, eligible peer releases must predate quarter-end. At the final checkpoint, they must predate MUSA's report date. Date-only publication evidence cannot be used on MUSA's reporting day. Select the latest published period with positive overlap for each peer, preserving its actual fiscal dates and overlap days.

The correction retains the earlier challenger: ridge penalty 10 on the two peer surprises, half-strength adjustment, and eight earlier published complete MUSA residual rows within the same regime. Every training row uses its own historical checkpoint. Outcomes published at or after the current cutoff, including the target outcome, are excluded from fitting.

### Shared monthly retailer factor

A penalized interval model estimates 24 monthly surprise states plus separate company offsets:

```text
reported company surprise
= company offset + period-weighted shared monthly factor + noise
```

Inputs are published peer surprises and earlier published MUSA production residuals. All shared loadings are fixed at positive one; the model does not learn unrestricted loadings from this small sample. Squared penalties of 2 apply to monthly levels, adjacent-month differences and company offsets. Half the estimated target-quarter factor plus MUSA offset is added to production.

Actual calendar-day overlap determines interval weights; these are exposure proxies, not observed gallons. Fiscal periods are not reassigned to calendar quarters. Monthly states are latent allocations, not observed MUSA weekly or monthly margins. Separate offsets preserve company differences only approximately; this is not a fully identified acquisition-cost model.

Require eight earlier published same-regime MUSA residuals, four fully window-contained observations from each peer, and at least one published peer observation overlapping the target. Earlier low-margin, 2020-transition and 2021-onward regimes remain separate. At each checkpoint, the model fits only already published observations; no target outcome or full-history hindsight smoother is used. Its 24-month window ends in the checkpoint month, so checkpoint changes include rolling-window effects as well as information updates.

## Modern results

All four checkpoints score the same 14 quarters, Q1 2023 through Q2 2026. Production MAE is 2.303¢ and RMSE is 3.120¢ on those rows, not the full 22-quarter production sample.

- Earnings-calendar quarter-end and pre-report shadows: identical MAE 2.155¢ and RMSE 3.026¢. Directional accuracy is 10/14 versus production's 12/14. There is no incremental modern improvement from moving the cutoff later.
- Shared-factor quarter-end shadow: MAE 2.287¢, RMSE 3.199¢ and direction 11/14. The tiny MAE improvement accompanies worse RMSE.
- Shared-factor pre-report shadow: MAE 2.335¢, RMSE 3.219¢ and direction 10/14. Its average absolute error is 0.048¢ higher than its quarter-end version.

Every modern checkpoint fails the existing promotion gate. All retain two errors of at least 5¢. Lower paired-improvement bounds are negative; they are descriptive normal-approximation statistics, not adjusted for all research conducted in this project.

## Original large misses

Only two of the six modern large misses are scoreable. The other four remain blocked by insufficient earlier same-regime training; no old observations were blindly pooled to remove that restriction.

- Q3 2023 actual 28.7¢: production 35.383¢, calendar shadow 35.487¢, shared-factor pre-report shadow 35.445¢. Absolute errors are 6.683¢, 6.787¢ and 6.745¢ respectively. Both new pre-report approaches worsen the original miss.
- Q2 2026 actual 35.1¢: production 28.495¢, calendar shadow 29.142¢, shared-factor pre-report shadow 28.226¢. Absolute errors are 6.605¢, 5.958¢ and 6.874¢. The calendar shadow retains its existing modest improvement; the shared factor worsens the miss.

For these two quarters, production MAE is 6.644¢, calendar MAE 6.372¢ and shared-factor pre-report MAE 6.810¢. For the twelve ordinary modern quarters, corresponding MAEs are 1.579¢, 1.452¢ and 1.589¢. Original large-error membership is a descriptive subset, never an activation rule or a verified no-disclosure classification.

## Earlier regimes and new information

The pre-report calendar model scores five earlier quarters: production MAE 3.444¢ versus shadow 3.635¢. Its quarter-end version scores only two, so their headline metrics are not a paired comparison. Among the two common earlier rows, later-checkpoint error improves by 0.428¢ in Q3 2019 and worsens by 0.181¢ in Q4 2019.

Three previously unavailable overlapping peer selections occur in the earlier archive, in Q2 2016, Q2 2017 and Q2 2018. Their surprise signs match MUSA's eventual error twice out of three. None is a modern observation; three cases cannot validate a signal. The sign diagnostic is not used to activate, fit or select either model.

The pre-report shared factor scores ten earlier quarters: production MAE 2.526¢ versus shadow 2.653¢. Its quarter-end version scores nine: 2.802¢ versus 2.974¢. Both fail the gate. Neither approach has scoreable 2020-transition quarters.

The calendar result narrows the claim: this particular peer archive supplies no additional overlapping modern report between quarter-end and MUSA earnings. It does not prove that all later disclosures are useless. The factor result rejects this fixed unit-loading, monthly interval formulation as a production replacement; it does not establish that every cross-company model is impossible.

## Reproduction

```sh
.venv/bin/python -m musa_nowcast.earnings_calendar_factor \
  --out data/earnings_calendar_factor/NEW_UNIQUE_RUN
.venv/bin/python -m pytest -q tests/test_earnings_calendar_factor.py
```

Canonical output is `data/earnings_calendar_factor/2026-10-08_v2/`: immutable input copies/hashes, forecasts frozen before scoring, calendar selections, factor observations and fitted states, exclusions, paired checkpoint comparisons and results. The initial v1 run is preserved; v2 repairs MUSA source-hash provenance and includes sign diagnostics for newly available pairs, without changing any prediction or model specification.

Production forecasts, risk/disclosure taxonomies and scoring thresholds are unchanged. No new live Q3 estimate, paid data, external publication or GitHub push was made.
