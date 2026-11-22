# Threshold guide: agree the rule before you look

This guide gives no default numbers. The right thresholds depend on the application and on what a failure costs the user, and the tool does not set defaults for a verdict. Do not quote "typical" or "industry" thresholds. Help the user choose their own and write them down **before** any run whose result could change their mind.

## What to decide, in this order

1. **Primary metric (one, at most two).** What single thing must improve for the change to count? For retrieval-only work on the free track, a lexical metric such as Hit@3 or MRR. For answer quality, one semantic metric such as faithfulness. Everything else is secondary.
2. **Per-question pass rule.** `ragkit compare` can test paired pass/fail flips with `--pass-metric <metric> --pass-threshold <0 to 1>`. Pick the score at which one answer counts as acceptable. Ask the user what a "bad enough to matter" answer looks like, and look at a few real dev-split examples at different scores to choose the cut-off. Use the dev split to choose it, never held-out.
3. **What counts as an improvement.** For example: "the paired bootstrap 95% interval for the primary metric's mean difference is entirely above zero". The user chooses the rule; write the exact wording.
4. **Guard metrics.** Name any metric that must not get worse (for example unanswerable-question abstention), and how much worse is unacceptable.
5. **What counts as no evidence, and what counts as a regression.** An interval that includes zero is "no evidence of a change", not "no change".
6. **Run budget and stopping rule.** The cap in USD, and the number of repeats. Decide now so a bad first result does not tempt another paid run.

## Ceilings for speed, errors and cost

Besides the quality rule, the user can set ceilings in `thresholds.yaml`. These are limits the measurements must stay under, for example the slow end of answer times (`latency_p95_ms`), the share of questions that fail (`error_rate`), the share of unusable answers (`invalid_rate`) and the cost of one question (`cost_per_query_usd`). The user chooses the numbers, from what their own users would accept. Do not suggest "typical" values.

- A value that could not be measured is **unassessable** and never counts as passing. Cost cannot be measured unless the app reports input and output token counts and the user gives prices in a pricing file.
- With few questions, the slow-end time is close to the single slowest answer. Say so.
- Cost here covers the app under test only. It is an estimate from token counts, not a bill, and it excludes the judge and hosting.

## Write it down

Save a short file (for example `thresholds.md`) next to the frozen dataset with the date, the dataset hash, the metrics, the pass rule, the improvement rule, the guard metrics and the budget. Commit it before running the held-out split. Quote it in the report unchanged.

## Reading the results honestly

- With about 20 held-out questions, intervals are wide and exact tests have little power when few questions change outcome. A non-significant result means "not enough evidence", and a significant one is still exploratory.
- A change in one secondary metric is not a win. If the primary metric did not meet the rule, the verdict is not "improved", whatever else moved.
- If the thresholds are changed after seeing held-out results, say so in the report and treat the result as invalid for a verdict.
- Judge scores are noisy: look at the spread across repeats and at the failures one by one.
