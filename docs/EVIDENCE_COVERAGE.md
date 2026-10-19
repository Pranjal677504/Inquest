# Evidence coverage review

The current grader separates structural validity, diagnosis/repair correctness, and a coarse evidence-relevance check. Accepted diagnosis does not require a positive relevance score. Relevance means that at least one cited, successful observation matches the case's allowed tool class and a gold service. It does not check claim-level entailment, distinguish supporting evidence from counterevidence, or verify that a proposed repair was executed.

## Coverage gap in existing data

The public `authored-v1-015` cache outage declares only `logs` as a gold tool class. A valid cache `health_check` returning `status=down` therefore earns no relevance credit, even though it supports an outage hypothesis. That observation alone still does not establish the exact failure mechanism or the effectiveness of failover. Alerts have no relevance mapping either; detecting a symptom is different from distinguishing its initiating cause.

These are limitations of the metric and case metadata. A zero relevance score cannot universally be translated into “no useful evidence.” Conversely, a nonzero score does not prove that the cited text supports the reported mechanism.

## Decision for the fresh suite

- Preserve all historical dataset bytes, grading code, scores, and run fingerprints.
- Include health in the new cases' gold tool lists when health provides useful evidence, rather than retroactively adjusting old case metadata.
- Keep the legacy metric name and semantics. Suite hashes identify the changed case definitions; do not pool relevance percentages across suites as though the evidence contracts were identical.
- Keep causal review explanations and support/counterevidence probe roles on the evaluator side. They are not added to the agent prompt or public observations.

`authored-v2-013` explicitly includes cache health in its allowed evidence. A regression check verifies that the new observation receives credit while the old case retains its log-only definition. This is a case-coverage correction in new data, not a new grader or a rescoring of a previous model run.

## Separate future metric work

An additional evidence metric would need its own versioned specification, manually reviewed positive/negative examples, treatment of contradictory citations, missing evidence and alternate valid causes, and parallel reporting alongside the legacy metric. A broad whitelist expansion or an unvalidated LLM judge would not establish causal support. No such metric is implemented or claimed in this update.
