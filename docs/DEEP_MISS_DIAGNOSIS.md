# Deep diagnosis of the six original large misses

## Outcome

We found **confirmed model-level failure mechanisms and a documented cost-basis mismatch**, not one universal, quantified economic root cause. Production is unchanged. No correction, probability model, forecast selection or tuned threshold was introduced.

The four most useful findings are: (1) some economically named variables receive counterintuitive fitted signs; (2) half-shrinkage limits the response to unusual anchors; (3) regional coastal spot prices do not match the company's reported retail rack-cost basis; (4) company pricing responds to competitor economics, not just wholesale moves. These are distinct issues and cannot be collapsed into one volatility adjustment.

This is retrospective diagnosis using current-vintage market history and post-result explanations, not historical forecast validation. The already-explored history is not an untouched holdout.

## What was actually checked

All **22** modern archived production-test predictions were reproduced within 1e-8 cents. Their prior-year anchors, fitted four-feature slopes, centered contributions, intercepts, market paths and reported revenue gaps are retained. All **16 ordinary quarters** remain in quantitative comparison; all **six large misses** have targeted original filing/call evidence from the existing archive, whose raw hashes were verified.

Four additional issuer-hosted documents were captured for three ordinary comparison quarters: Q2 2022, Q4 2022 and Q1 2026. These are purposive extreme-market controls, not random controls. Their relevant pricing/cost passages were reviewed; the Q1 2026 prepared-remarks cost-basis page was visually checked against the PDF. This does not amount to reviewing every call for all 22 quarters or finishing the exhaustive disclosure audit.

[Diagnostic archive](../data/deep_miss_diagnosis/2026-10-08_v1/diagnosis.json), [source checks](../data/deep_miss_diagnosis/2026-10-08_v1/source_checks.json), [located documentary findings](../data/deep_miss_diagnosis/2026-10-08_v1/reviewed_findings.json), [frozen specification](../data/deep_miss_diagnosis_spec_v1.json). Source text hashes and character offsets permit reconstruction; no unobserved invoice prices or weekly company margins were manufactured.

## 1. Confirmed statistical mechanism: fitted signs do not enforce the economic story

Production is prior-year retail margin plus half a ridge-model prediction of year-over-year change. Its four explanatory variables are spread, falling capture, rising squeeze and volatility. Their names do not constrain their coefficients.

In **Q1 2022**, the reproduced forecast is 28.479 cents versus actual 23.3. The centered rising-squeeze contribution is **+8.517 cents**, volatility adds +2.556, spread contributes -0.339, falling capture +0.263 and the intercept +1.981, on top of the 15.5-cent anchor. Thus a variable intended to describe squeeze is a dominant *upside* component of this fitted forecast. This confirms how the prediction is produced, not that the variable causes an economic uplift.

In **Q2 2026**, the prior-year anchor is 29.2 and the prediction is 28.495, versus actual 35.1. The regional spread change is -21.413 cents. Its centered contribution is **-4.017 cents**; greater falling capture contributes **-0.872**, volatility +2.853, rising squeeze +0.156 and the intercept +1.176. The signal mapping predicts deterioration when the company actually improves.

There is no sign-constrained economic interpretation of these coefficients. Correlated features, baseline shifts and few quarterly labels are plausible reasons, but this diagnosis does not prove which one generated each coefficient. A centered contribution also depends on training means and correlated regressors; it is an arithmetic decomposition, not a causal cents attribution.

Positive rising-squeeze slopes occur in **all six large and all 16 ordinary** quarters; negative falling-capture slopes occur in **2/6 large and 14/16 ordinary**. Therefore these signs are not themselves a successful large-error selector. Previously tested constrained weekly challengers also failed, so imposing signs alone is not an established fix.

## 2. Confirmed attenuation: exceptional anchors need more movement

Production correctly identifies the direction but moves too little in four original large misses:

- **2021Q2:** anchor 31.7; forecast 26.981; actual 21.8. The exceptionally high comparison year requires a 9.9-cent decline, but production moves only 4.719 cents.
- **2021Q4:** anchor 15.4; forecast 19.191; actual 25.5. The comparison year is low; the market adjustment captures only 3.791 of the actual 10.1-cent increase.
- **2022Q3:** anchor 24.0; forecast 29.508; actual 39.3. Production captures only 5.508 of a 15.3-cent increase.
- **2023Q3:** anchor 39.3; forecast 35.383; actual 28.7. Production captures only 3.917 of a 10.6-cent normalization.

For diagnosis only, restoring the full existing market adjustment improves these four errors: 5.181→0.462, 6.309→2.519, 9.792→4.284 and 6.683→2.767 cents. But **Q1 2022 deteriorates to an 18.157-cent miss**, and Q2 2026 worsens too. Across all 22, MAE worsens **3.133→3.359**, RMSE **4.019→5.209**; ordinary-quarter MAE worsens **1.823→2.400**, with two new large misses. No counterfactual forecast was promoted.

Half-shrinkage contributes to underreaction, but protects against a bad raw mapping. Removing it globally would not solve the problem.

## 3. Confirmed measurement mismatch: retail cost is not coastal spot cost

The [Q1 2026 prepared remarks](https://s22.q4cdn.com/506259022/files/doc_financials/2026/q1/MurphyUSA_Q126_PreparedRemarksTranscript.pdf), page 3, explain that approximately half the company's retail volume passes through its supply capabilities and is transferred to retail at a **market-based rack price**. The other approximately half was purchased under rack contracts. Those proportions describe this disclosure, not assumed historical weights for every miss.

This is more specific than merely saying supplier invoices are missing: the *reported retail-margin target* reflects a rack-market basis, while our proxy uses coastal wholesale spot prices. Procurement/logistics gains and inventory timing can sit in the separate fuel-supply result. Coastal spot-to-rack movements, geography, product formulation and delivered terms remain unobserved components; we did not reconstruct their sizes.

The [Q1 2022 call](https://s22.q4cdn.com/506259022/files/doc_financials/2022/q1/1Q22-Earnings-Transcript-MUSA.pdf) also discusses internal spot-to-rack transfer pricing, rising-price retail pressure and timing-related supply contribution. Neither that explanation nor a favorable supply contribution authorizes moving supply pennies into the retail target.

This establishes a structural proxy mismatch. It does **not** prove rack basis explains the entire 5–10-cent retail forecast residual, or provide historical company cost observations.

## 4. Documentary mechanisms by quarter

**2021Q2:** the [issuer call](https://s22.q4cdn.com/506259022/files/doc_financials/2021/q2/Murphy-USA-Inc.,-Q2-2021-Earnings-Call,-Jul-29,-2021.pdf) describes rising-price conditions, higher industry breakevens and QuickChek pricing integration. Combined with the 2020 anchor, these support a regime/comparability explanation. Acquisition mix and policy wording are real issues, but no effect size explains the full miss.

**2021Q4:** the [call](https://s22.q4cdn.com/506259022/files/doc_financials/2021/q4/Q4-2021-Transcript.pdf) links annual synergies to pricing tactics and renegotiated supply terms. The approximately $8 million annual synergy scale is not an isolated Q4 retail benefit. For perspective, a 6.309-cent margin error on 1,119.5 million gallons represents roughly $70.6 million; assigning $8 million entirely to that quarter's retail would illustrate only about 0.71 cents. This is a scale comparison, not an allocation or an upper bound on an amount described as exceeding $8 million.

**2022Q1:** the call's rising-price retail pressure supports the opposite economic interpretation from the model's large positive squeeze contribution. Reported retail/supply timing separation reinforces target-basis caution. The [10-Q](https://www.sec.gov/Archives/edgar/data/1573516/000157351622000022/musa-20220331.htm) does not yield a verified retail inventory adjustment to repair the prediction.

**2022Q3:** management links retail expansion to falling supply prices and a higher industry baseline in the [call](https://s22.q4cdn.com/506259022/files/doc_financials/2022/q3/3Q22-MUSA-Earnings-Transcript.pdf); the [release](https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/2022/Murphy-USA-Inc.-Reports-Third-Quarter-2022-Results/default.aspx) corroborates the declining-price benefit. Price-path capture plus baseline interaction is a supported mechanism, not a complete quantitative attribution.

**2023Q3:** the [release](https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/2023/Murphy-USA-Inc.-Reports-Third-Quarter-2023-Results/default.aspx) identifies the extraordinary declining-price 2022 comparison. The [call](https://s22.q4cdn.com/506259022/files/doc_financials/2023/q3/Q32023_MurphyUSA_EarningsCallTranscript.pdf) also describes three Friday price shocks followed by recovery. These support normalization and within-quarter timing explanations, without proving how many error cents belong to each.

**2026Q2:** [prepared commentary](https://s22.q4cdn.com/506259022/files/doc_financials/2026/q2/MurphyUSA_Q2_2026_Quarterly_Commentary_vFinal.pdf) describes higher competitor margin requirements and a retail-margin step-up. The [Q&A](https://s22.q4cdn.com/506259022/files/doc_financials/2026/q2/MurphyUSA_Q226_QuestionAnswerTranscript.pdf) explains opposing April/May price moves and associated volume differences. These undermine a homogeneous quarter assumption and a fixed retail/spot mapping. The separately reported -2-cent supply inventory exposure is not a retail tailwind.

## Ordinary-quarter checks and what did not explain the misses

Volatility alone fails the comparison. **2026Q1** has a 108.4-cent wholesale increase and 16.9-cent average absolute weekly movement, yet production error is only 0.08 cents. **2022Q2** and **2022Q4** also have large wholesale moves, with errors 2.77 and 0.94 cents. Meanwhile **2021Q2** has only 4.0-cent weekly volatility and a 5.18-cent miss. Large versus ordinary average volatility is 10.18 versus 8.05 cents: contextual evidence, not a calibrated causal distinction.

The [Q2 2022 call](https://s22.q4cdn.com/506259022/files/doc_downloads/2022/07/Q2-2022-Earnings-Transcript-MUSA.pdf) discusses rapid pump pass-through and active price/volume tactics; the [Q4 2022 call](https://s22.q4cdn.com/506259022/files/doc_financials/2022/q4/4Q22-MUSA-Earnings-Transcript-Final.pdf) discusses supply and pricing capabilities. Similar mechanisms are present without large errors.

The absolute reported revenue-gap proxy averages **3.33 cents in large misses versus 3.64 cents in ordinary quarters**. It is confounded by tax, mix and geography, and not a verified MUSA pump discount. This does not single out selling-price mismatch as the universal cause.

The checked accounting review identifies **zero quantified retail-specific inventory adjustments**, not proof that no accounting issue existed. LIFO reserve balances are stocks, not quarterly retail expense corrections. Supplier acquisition costs remain unobserved; residual costs inferred using actual margins would be circular.

## A disclosure discovery changes the research framing

The newly captured [April 30, 2026 Q&A](https://s22.q4cdn.com/506259022/files/doc_financials/2026/q1/MurphyUSA_Q126_Q-ATranscript.pdf) contains approximate April-to-date retail commentary around 30 cents/low-30s, followed by a separate all-in range. Exact observed-period end, numerical bounds and gallon shares are unresolved; the books were not closed.

This goes to a [new pending candidate queue](../data/deep_miss_diagnosis/2026-10-08_v1/new_disclosure_candidates.json), not straight into the estimator. Existing frozen taxonomy and original audit states were not rewritten. **Do not call Q2 2026 a verified no-disclosure quarter.** Source availability is dated April 30, but no exact intraday release time is assumed.

## What this changes

The highest-value next information target is the **rack-versus-spot basis and company-versus-local-market pricing**, not a generic volatility scalar. Model identification also needs attention: correlated variables must not be interpreted economically just because their names sound economic. A constrained challenger, a retail/supply joint economic framework or a baseline-by-price-path interaction would still require an independent test; the diagnosis does not authorize fitting any of them now.

Complete the no-disclosure audit before selecting that subgroup. Preserve the unexplained cents rather than adding an ad hoc correction for each historical story. The present work narrows the problem and identifies concrete failure mechanisms, but does not establish a dependable tail forecast.

Reproduce numeric diagnosis with `.venv/bin/python -m musa_nowcast.deep_diagnosis --out data/deep_miss_diagnosis/NEW_UNIQUE_RUN`. Documentary assessments are append-only in the canonical run and retain source locators; they are not inferred automatically from keywords.
