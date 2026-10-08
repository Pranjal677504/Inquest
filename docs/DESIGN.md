# Design decisions

These notes describe incident construction, the implemented tool interface, and the rationale for planned agent architecture. Planned choices remain open to revision after implementation and evaluation.

## Ownership and review

Pranjal Prajapati is the project maintainer. The maintainer sets scope and priorities, accepts design changes, reviews verification evidence, and decides when a release is ready. Proposed changes should explain their purpose, alternatives, tests, and limitations so they can be reviewed and discussed.

## Implemented choices

| Choice | Rationale | Alternative and trade-off | Evidence or limitation |
|---|---|---|---|
| Synthetic incident bundles | Makes failures cheap to generate and repeat without running infrastructure | Live fault injection provides greater operational realism but needs services, deployment management, and repeatable infrastructure | Synthetic success alone cannot establish production usefulness |
| Eight-service fixed graph | Provides explicit dependencies and interpretable failure propagation | Configurable graphs broaden coverage but add generator and agent-knowledge complexity | Shortest-hop behavior is tested; topology variation is planned |
| Breadth-first graph traversal | Finds shortest hop distances in the unweighted dependency graph | Weighted paths would model unequal relationships but need justified edge weights | Tests check known callers, callees, and unknown-service errors |
| One root cause per case | Keeps initial diagnosis and grading unambiguous | Concurrent causes better reflect some incidents but require a richer answer contract | Multi-cause diagnosis is outside the current scope |
| Seeded private random generator | Repeats a case without mutating application-wide random state | Global randomness creates accidental coupling; recording every random draw adds complexity | Repeated generation, global-state isolation, and separate-process fingerprints were checked on Python 3.14 |
| Fault category cycles with seed modulo eight | Ensures a consecutive eight-case range covers each fault category | Random fault selection can leave small comparisons imbalanced | This sampling rule is predictable; future agents must not receive construction seeds or scenario IDs that expose the rule |
| 120 one-minute telemetry samples | Supplies a baseline and incident window while keeping bundles small | Longer or irregularly sampled streams increase realism and storage needs | Each metric is checked for length and finite, non-negative samples; the time horizon is an authored benchmark choice |
| Checksummed frozen JSONL sets | Fixes evaluation inputs independently of generator or Python RNG changes, with inspectable records | Regenerating from seeds saves storage but can change inputs across environments; binary storage reduces size but adds dependencies | Nine sets are published with a manifest and SHA-256 catalog; loader tests reject changed files and run with generation disabled |
| Dataclasses and standard-library generator | Keeps the first runnable component small and dependency-light | A schema library can provide richer validation at the cost of a runtime dependency | Loading checks core fields and telemetry records; it is not a complete versioned schema or hostile-input resource-limit mechanism |
| Telemetry field projection | Keeps construction labels and gold metadata out of tool observations | Passing full bundles exposes labeled answers; projection alone does not isolate hostile Python code | All tools are tested across 120 frozen cases; changing labels and extra metadata leaves observations unchanged |
| Uniform tool-call budget | Provides a simple common investigation resource constraint | Real tools differ in cost and latency; uniform steps do not capture those differences | Valid and invalid requests consume steps, and exhaustion prevents dispatch; there is no free-call option |
| Fixed recent trace window | Makes trace selection independent of labeled onset | Filtering by true onset quietly consults ground truth; a fixed window can miss earlier relevant traces | Traces cycle through matching stored records from minutes 80–119, with replay tests |
| Literal log search | Keeps filtering predictable and avoids executing user-supplied regex patterns | Regex is more expressive but needs a bounded execution mechanism | Case-insensitive substring filters and severity/record limits are tested |
| Detached telemetry and observations | Prevents edits to returned records from changing future observations or saved transcripts | Shared mutable dictionaries are simpler but couple agent code to evaluator state | Snapshot and mutation tests cover the public observation contract |

## Browser workbench and deployment

The Flask workbench exposes the existing incident generator and verified frozen cases through a small API and static browser interface. A root-level `app.py` supplies the deployment entry point; `.python-version` selects the locally verified Python 3.14 runtime. An API plus static assets keeps the demo inspectable without a database or model credentials. A separate frontend framework would add a build pipeline and more dependencies without being required for the current interaction.

The core modules use the standard library, but the installed distribution requires Flask because it includes this web application. Keeping Flask in runtime dependencies also supplies the automatic Flask deployment with its framework. Splitting the demo into an optional package is possible later, with explicit deployment dependency checks; the current package is not dependency-free.

Visitors choose a case, browse telemetry, and submit a service, fault, and recovery action to reveal the construction label. This educational flow permits unrestricted browsing and answer reveal. Automated benchmark agents use the separate budgeted Python tool interface; future scored experiments must not consume the browser API's selection metadata or answer endpoint.

Verification: the web branch passed 137 tests before integration; the combined web and tool implementation passed 180 tests on Python 3.14. Page/assets/config/health routes and the live frozen-case diagnosis flow were checked. The browser demo does not establish agent performance, evidence support, adversarial isolation, or production-scale capacity.

## Report grading

The prototype accuracy checks, Brier calculation, and gold tool/service mapping are retained in an evaluator-side grader. The labeled scenario is supplied explicitly alongside its paired environment; attaching labels back to the environment would undo the observation boundary. The trusted evaluator is responsible for pairing the same episode. Current in-process grading does not authenticate transcripts against hostile code.

Strict field validation records invalid reports and reference errors. Invalid confidence remains unavailable rather than being coerced, clipped, or replaced with 0.5. This avoids silently manufacturing a probability; summaries must disclose missing confidence values. Component accuracy and `diagnosis_ok` remain visible for malformed submissions, while `success` requires a valid report and all predictions to match. Brier loss uses this accepted-success definition. Keeping diagnostic accuracy as the only success criterion would obscure interface failures; both outcomes are exposed so later analyses can distinguish them.

Evidence scoring counts unique string references, retains unknown/failed/malformed references in the denominator, and grants coarse credit from returned services and authored gold tool classes. Repeated strings are deduplicated; each non-string malformed entry counts as invalid. Empty result records earn no relevance credit. Reference validity and relevance have separate outputs. Claim-level entailment or line-level support would be stronger and remains a later milestone; current relevance can credit benign text about a gold service.

Verification: 243 tests on Python 3.14 include malformed nested values, non-finite confidence, missing evidence, citation failures and duplication, both fix fields, partial diagnoses, result JSON safety, and all 120 frozen cases with evaluator-authored fixtures. The grading example uses handcrafted predictions and assigned confidence, with suite/set/checksum/revision metadata; it establishes API behavior rather than agent performance.

## Planned investigation architecture

| Planned choice | Why explore it | What must be established |
|---|---|---|
| Perception separated from reasoning | Allows errors in interpreting telemetry to be studied separately from investigation policy | Scripted adapter tests and actual model comparisons on identical cases |
| Naive Bayes over service/fault hypotheses | Provides a simple, inspectable belief update with development-data likelihood fitting | Normalized probabilities, dev-only fitting, and held-out calibration; correlated evidence can cause overconfidence |
| Expected information gain for probe choice | Chooses observations expected to reduce uncertainty | Small fixtures with known answers and fair comparisons against random and operational heuristics |
| Saved experiment transcripts | Makes reasoning and outcomes inspectable after a run | Report grading is implemented; complete run artifacts and agent-exception preservation remain planned |

### Belief updates and information gain: proposed, not implemented here

For a service/fault hypothesis `h`, evidence `e`, and a query `q`, Bayes' rule updates the prior with a likelihood. A Naive Bayes model would factor evidence-tag likelihoods under conditional independence. That makes a small model inspectable, but repeated or correlated telemetry can count the same signal more than once and inflate confidence. Alternatives include a simple signature classifier, a discriminative model, and a model of joint tag outcomes. Comparisons must include the simple classifier rather than assume investigation is necessary.

Let `b(h)` be the current belief and `z` a possible tag outcome of a query. A fitted model must define `P(z | h, q)`. It implies the predictive distribution `P(z | q) = sum_h b(h) P(z | h, q)` and the posterior `b_z(h) = b(h) P(z | h, q) / P(z | q)` for nonzero-probability outcomes. Expected information gain is the reduction in entropy averaged over these possible outcomes:

```math
\mathrm{EIG}(q) = \mathcal{H}(b) - \sum_z P(z \mid q)\mathcal{H}(b_z).
```

The expectation is over modeled outcomes, not an observation already received. A probe independent of `h` has zero gain; a perfectly discriminating probe can remove all current uncertainty. Enumerating binary tags assumes a defined finite outcome space and can grow exponentially. EIG measures uncertainty under the fitted model, not guaranteed causal usefulness, correctness, or cost savings. Equal-cost tools are the initial setting; unequal costs would require a separately justified decision rule.

No fitted likelihood artifact has been published in this repository. Integration must record development-only counts, priors, smoothing, tag definitions, training checksums, and an artifact checksum. Zero-probability cases, normalization, and probe rankings need small known-answer tests. The 120 smoke fixtures are not the training corpus. Test and independently authored cases must not contribute fitting counts, threshold selection, or calibration parameters.

### Independent validation before more convenience features

The earlier sequence put authored cases and real-model runs after much of the tooling. The revised [roadmap](ROADMAP.md) prioritizes authored incidents and a minimal recorded local-model pilot using the existing tools and grader. This exposes generator coupling and actual model failures sooner. A full Bayesian/LLM comparison still needs validated likelihoods and aligned knowledge and budgets.

Authored cases must avoid generator templates, document causality and distractors, and freeze before tuning. Field-projection tests check direct label leakage; they do not rule out predictable signal signatures or memorization. An audit should inspect prompts, tool schemas, all observation fields, saved model inputs, training-suite membership, and checksums. The browser answer endpoint and evaluator-held labels must never enter a scored agent context. Real operational telemetry remains a separate external-validity requirement.

## Current verification boundary

Installation, all four examples, and 243 tests were verified locally on Python 3.14. The package declares Python 3.10+ as a compatibility target. The [CI matrix](../.github/workflows/tests.yml) also passed installation, all 243 tests, ten frozen checksums, and all four examples outside the checkout on Linux with each Python version from 3.10 to 3.14 at revision `92e6888a94be931e2a69d2d739e797e9ffa5ef23` ([run evidence](https://github.com/Pranjal677504/Inquest/actions/runs/37794556651)). Windows and macOS version matrices are not covered. CI has read-only repository permissions, uses pinned action revisions, and needs no provider credentials. CLI, model-resource packaging, and wheel verification remain pending.

The manual investigation example makes predetermined queries; no autonomous agent evaluation, actual LLM comparison, or production validation has been published in this repository. The [related-work comparison](RELATED_WORK.md) sets expectations against existing operational and causal benchmarks. Information gain, calibration, and budget efficiency are research questions, not established differentiators.

Byte-for-byte generation across Python versions is not guaranteed. The [published frozen suite](../datasets/README.md) is the common input for initial comparisons: readers load the recorded bytes and verify checksums without generating cases. It contains 120 synthetic incidents and is intended for small initial comparisons rather than statistical performance claims or likelihood training. Suite changes require a new version. The manifest has format version 1; individual scenario records still have no schema migration support.

## Questions a technical walkthrough should answer

- How does a dependency failure propagate to callers, and which tests demonstrate it?
- How are seeds, category balance, and frozen bundles related to reproducibility?
- Which labels and metadata could reveal answers, and where will access be restricted?
- What does a round-trip test establish, and what does it leave untested?
- Why could the proposed belief model become overconfident?
- How will informed probe selection be compared fairly with simpler policies?
- Which claims are already verified, and which require future experiments?

The answers should refer to source, tests, or recorded runs. Planned capabilities should be described as plans until their evidence exists.
