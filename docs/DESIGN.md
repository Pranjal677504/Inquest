# Design decisions

These notes describe the current incident-construction implementation and the rationale for the planned investigation architecture. Planned choices remain open to revision after implementation and evaluation.

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
| JSON bundles | Makes frozen cases inspectable and portable without a database | Binary or columnar storage reduces size for larger datasets but adds dependencies | Round trips are tested; stored bundles include labels and belong on the construction/evaluation side |
| Dataclasses and standard-library generator | Keeps the first runnable component small and dependency-light | A schema library can provide richer validation at the cost of a runtime dependency | Loading checks core fields and telemetry records; it is not a complete versioned schema or hostile-input resource-limit mechanism |
| Separate labels from future tool observations | Prevents the answer from being directly exposed to investigation agents | Passing full construction bundles would give agents the labeled answer | An explicit root-cause trace label was removed; the tool boundary and its tests remain milestone 03 |

## Planned investigation architecture

| Planned choice | Why explore it | What must be established |
|---|---|---|
| Perception separated from reasoning | Allows errors in interpreting telemetry to be studied separately from investigation policy | Scripted adapter tests and actual model comparisons on identical cases |
| Naive Bayes over service/fault hypotheses | Provides a simple, inspectable belief update with development-data likelihood fitting | Normalized probabilities, dev-only fitting, and held-out calibration; correlated evidence can cause overconfidence |
| Expected information gain for probe choice | Chooses observations expected to reduce uncertainty | Small fixtures with known answers and fair comparisons against random and operational heuristics |
| Uniform tool-call budget | Provides an initial common resource constraint for comparisons | Consistent accounting for valid and invalid calls; real tools differ in latency and cost |
| Independent grading and saved transcripts | Makes reports and outcomes inspectable after a run | Malformed-report checks, valid observation references, and preservation of errors and failed episodes |

## Current verification boundary

Installation, the example, and 117 tests were verified locally on Python 3.14. The package declares Python 3.10+ as a compatibility target, with a version matrix still pending. No end-to-end agent investigation, actual LLM comparison, or production validation has been published in this repository.

Byte-for-byte generation across Python versions is not guaranteed. Serialized bundles are the planned common input for comparisons across environments. The current JSON loader has no schema-version migration support; that must be addressed before treating future bundle revisions as interchangeable.

## Questions a technical walkthrough should answer

- How does a dependency failure propagate to callers, and which tests demonstrate it?
- How are seeds, category balance, and frozen bundles related to reproducibility?
- Which labels and metadata could reveal answers, and where will access be restricted?
- What does a round-trip test establish, and what does it leave untested?
- Why could the proposed belief model become overconfident?
- How will informed probe selection be compared fairly with simpler policies?
- Which claims are already verified, and which require future experiments?

The answers should refer to source, tests, or recorded runs. Planned capabilities should be described as plans until their evidence exists.
