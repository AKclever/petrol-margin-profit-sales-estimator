# Additional company evidence for fuel margin research

ARKO and CrossAmerica are the next direct retail-margin research candidates. Global Partners belongs in a separate distribution and retail context pool. Marathon Petroleum supplies refining context, not a comparable pump margin. Archrock, Energy Transfer and Liberty Energy should not be added as direct retail-fuel forecasting peers.

The evidence pool is separate from the three-company forecast replay. No production estimate, transfer coefficient or automated forecast universe changed. There is not yet enough reviewed history to claim forecasting accuracy for the new companies.

## Captured history and timing

The archive contains six ARKO quarterly retail targets from Q1 2025 through Q2 2026 and four CrossAmerica targets for Q2 2025, Q4 2025, Q1 2026 and Q2 2026. Each target retains its fiscal period, publication date, capture timestamp, margin basis, source URL and raw SHA-256. Prior-year comparisons are retained with the availability date of the release containing them; they are not backdated into fictitious historical forecasts.

None of these ten completed-quarter reports qualifies before the matching MUSA report under strict date-only ordering. CrossAmerica Q2 2026 and MUSA both reported August 5; that case remains ineligible until intraday ordering is verified. Later releases can still inform subsequent periods, but their usefulness must be tested rather than assumed.

ARKO's earlier guidance is a different channel. Its Q1, Q2 and Q3 2025 releases supplied next-quarter retail-margin assumptions of 42.5–44.5¢. All three existed before MUSA reported the respective target quarter. The eventual ARKO margins were 44.9¢, 43.6¢ and 44.5¢. Midpoint errors were 1.4¢, 0.1¢ and 1.0¢; two of three were inside the range. These are management assumptions used in EBITDA guidance, not independent model predictions or MUSA guidance. Three cases do not establish predictive edge. [ARKO Q1](https://www.arkocorp.com/news-events/press-releases/detail/181/arko-corp-reports-first-quarter-2025-results), [Q2](https://www.arkocorp.com/news-events/press-releases/detail/186/arko-corp-reports-second-quarter-2025-results), [Q3](https://www.arkocorp.com/news-events/press-releases/detail/191/arko-corp-reports-third-quarter-2025-results).

The original capture attempted 16 releases, captured 13 and retained three timeout failures. Two CrossAmerica failures were resolved through separate SEC captures, without overwriting the failed attempts. Energy Transfer's raw capture remains unresolved; its business screen is supported by the official release viewed through web research. Current raw captures are not proof that identical source bytes were archived at historical publication time.

## Candidate definitions

### ARKO

ARKO provides an identifiable quarterly retail fuel margin and gallon series. Its reported fuel contribution excludes an internal fixed margin or fee paid to GPMP, so this target must remain distinct from MUSA retail margin. Store-to-dealer conversions change the perimeter; same-store statistics are useful context but must not be silently substituted for total-company targets. The Q2 2026 margin is 48.6¢, not a basis-matched estimate of MUSA's margin. [ARKO Q2 2026](https://www.arkocorp.com/news-events/press-releases/detail/213/arko-corp-reports-second-quarter-2026-results).

ARKO is the first candidate for a standalone own-margin experiment once older releases establish a consistent fee definition and enough earlier training quarters. The numeric next-quarter assumptions deserve a separate dated guidance experiment.

### CrossAmerica Partners

CrossAmerica separates company-operated, commission-agent, combined retail-segment and wholesale margins. For Q2 2026, company-operated margin before credit-card fees is 51.3¢; combined retail margin before fees and commissions is 49.2¢; wholesale margin is 11.1¢. These are different targets, not interchangeable versions of one margin. The normalized primary target is company-operated retail before credit-card fees. Asset sales and conversions require explicit perimeter context. [CrossAmerica Q2 2026](https://www.sec.gov/Archives/edgar/data/1538849/000119312526335332/capl-ex99_1.htm).

This is a plausible second standalone retail-margin experiment. It cannot inherit MUSA geographic weights or calibration without evidence.

### Global Partners

Global Partners reports gasoline-distribution product margin separately from station operations within its GDSO segment. Q2 2025 gasoline-distribution margin was $137.9 million, while total GDSO margin was $207.9 million. Dividing total GDSO margin by gallons would mix station-operation income into the fuel target. Distribution economics and classes of trade differ from a company-operated pump margin. [Global Partners Q2 2025](https://ir.globalp.com/news/news-details/2025/Global-Partners-Reports-Second-Quarter-2025-Financial-Results/).

Two historical releases are archived for definition work. GLP is worth an own-target feasibility experiment, but the target should be distribution economics, not a purported MUSA-equivalent retail margin.

### Marathon Petroleum

Marathon reports Refining and Marketing margin per refinery-throughput barrel. Its earnings and operating commentary can provide supply context, but dividing by 42 does not turn refinery economics into a retailer's margin. Keep MPC outside the direct retail transfer pool. A refining-margin forecasting project would be a separate problem. [Marathon results](https://ir.marathonpetroleum.com/investor/news-releases/news-details/2026/Marathon-Petroleum-Corp--Reports-Fourth-Quarter-and-Full-Year-2025-Results/default.aspx).

### Energy Transfer

Energy Transfer reports midstream segment EBITDA and transport, processing and terminal volumes. These could provide context for specific infrastructure events, but they are not comparable retail fuel margins. Subsidiary exposure also must not be counted as an independent retail observation without checking consolidation. [Energy Transfer results](https://ir.energytransfer.com/news-releases/news-release-details/energy-transfer-reports-fourth-quarter-2025-results).

### Archrock and Liberty Energy

Archrock's compression-service economics and Liberty's completion and power-service economics are different from gasoline retailer margins. Earlier reporting alone does not make them useful peer surprises. Retain their screened status, but do not expand this margin model to forecast them. [Archrock results](https://investors.archrock.com/news/news-details/2026/Archrock-Reports-Fourth-Quarter-and-Full-Year-2025-Results-and-Provides-2026-Financial-Guidance/default.aspx), [Liberty results](https://libertyenergy.com/fourth-quarter-and-full-year-2025-financial-and-operational-results/).

## Experiment gates

The next step is older dated ARKO and CrossAmerica history, followed by separate own-company baselines with simple seasonal and recent-level benchmarks. Freeze calibration, geographic assumptions, target definition and publication rules before scoring. Use chronological evaluation and identical coverage for MAE, RMSE and large-error comparisons. Do not promise that these companies will be easier to predict before measuring them.

Only after an own-company baseline exists can a peer surprise be defined and tested against MUSA. Test guidance separately from achieved-margin surprises; never average absolute company margins into MUSA's estimate. Keep prior-quarter information separate from contemporaneous overlap. No fitted transfer was produced from these ten rows.

## Repository artifacts

Company policy: `data/expanded_peer_company_policy_v1.json`. Reviewed targets and guidance: `data/expanded_peer_evidence/2026-10-08_review_v2/reviewed_evidence.json`. Initial and fallback captures remain in separate directories under `data/expanded_peer_evidence`.

```bash
.venv/bin/python -m musa_nowcast.expanded_peer_evidence --spec data/expanded_peer_evidence_spec_v1.json --out data/expanded_peer_evidence/NEW_CAPTURE
.venv/bin/python -m musa_nowcast.expanded_peer_evidence --review --out data/expanded_peer_evidence/NEW_REVIEW
.venv/bin/python -m pytest -q tests/test_expanded_peer_evidence.py
```

The review command deliberately reads the two frozen capture runs. A new capture is not silently substituted into the historical review. Each output directory is exclusive and refuses overwrite.
