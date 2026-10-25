# InquestBench benchmark card

Updated: 2026-10-25. Status: early synthetic evaluation toolkit; independent benchmark validation remains pending.

## Intended use

InquestBench supports development and controlled comparison of agents investigating synthetic microservice incidents. Use it to inspect tool selection, diagnosis and repair-label accuracy, citations, confidence, and investigation cost under explicit budgets. Saved transcripts support replay and failure analysis; the browser workbench supports demonstrations and manual investigation.

The suite does not establish production incident-response readiness, safe automated remediation, or superiority over other benchmarks. See [design](DESIGN.md), [related work](RELATED_WORK.md), and [project progress](PROGRESS.md) for research direction and current evidence.

## Task and evaluation boundary

Each incident uses a fixed eight-service topology, 120 minutes of telemetry, and one labeled initiating fault. The categories are `bad_deploy`, `config_regression`, `resource_leak`, `cert_expiry`, `traffic_surge`, `bad_migration`, `dependency_outage`, and `feature_flag`.

The evaluator loads a frozen labeled bundle. Investigators receive eight read-only [tools](TOOLS.md): service inventory, alerts, metrics, logs, health, events, event detail, and traces. Every attempted tool call consumes budget, including invalid calls; dispatch stops at exhaustion. Model turns, protocol errors, retries, and generation limits are separately bounded by the [runner](RUNNER.md).

A final report names a service, fault type, fix action and target, nonempty observation citations, and confidence in [0, 1]. The evaluator grades construction labels and saved references. Full bundles, IDs, seeds, casebooks, expected reports, and gold metadata must stay outside agent context. The Python environment is not a sandbox against source access or reflection; custom harnesses must enforce this boundary.

## Datasets and provenance

| Frozen suite | Cases and organization | Interpretation |
|---|---|---|
| [smoke-v1](../datasets/README.md) | 120 procedural cases: 24 development, 48 test, 48 alternate-wording (`ood`). Each easy/medium/hard set has 8 development or 16 test/ood cases. | Debugging and small initial comparisons. `ood` changes signal-log wording within the same generator, not topology or operational domain. |
| [authored-v1](../datasets/authored-v1/README.md) | 16 AI-authored cases: one medium and one hard per category; four omit root-service logs; set `holdout`. | Explicit causal stress-test fixtures constructed separately from the procedural generator, public and single-author reviewed. |
| [authored-v2](../datasets/authored-v2/README.md) | 16 newly authored mechanisms: one medium and one hard per category; four omit root-service logs; evaluator-authored five-call support/counterevidence paths; set `holdout`. | Prepared after the V2 policy prompt froze; retains shared topology, tools, renderer and grader. |

Codex prepared the authored cases for Pranjal Prajapati. The same author reviewed cases, designed V2, and inspected earlier development failures. Independent domain-expert review remains pending. Difficulty labels express design intent, not measured difficulty. Probe paths use known labels to verify clue reachability, not autonomous discovery or unique causality.

All cases and labels are public. `test`, `ood`, and `holdout` identify datasets; they do not guarantee independence, secrecy, or contamination resistance. Both authored suites subsequently informed V3 and are development data for V3. Disclose further tuning or case selection. Report suites separately: incidents and relevance metadata differ.

Load published bytes through the frozen loader, retain manifests and `SHA256SUMS`, and pin the source revision. Regeneration from seeds is not equivalent to loading frozen inputs. Changes to contents or selection require a new suite version. Data lives in the checkout, outside the Python distribution. See the [data guide](../datasets/README.md) and suite provenance records.

## V2 baseline and V1 CLI default

**V2 is the working evaluation policy baseline:** it followed V1 failure review, and its prompt froze before authored-v2 construction. This is a recorded reference, not independent validation or proof of superiority. The [authored-v2 contract](../datasets/authored-v2/README.md) records policy revision `91e1a0354b1cb562f121d44d91ffa7a2a75e5574` and prompt SHA-256 `6c94ffeaf6dbde3eeea84e5d5f1e1f34c24a0b9fd8284bfd13a28a8d9d8a411a`.

**The CLI defaults to V1** to preserve existing invocations and configurations. Explicitly pass `--policy v2` for baseline model runs. Policy versions identify instructions, not model weights; `authored-v2` identifies data, not policy. [V3](POLICY_V3.md) remains an opt-in development candidate because both authored suites informed it.

The recorded authored-v2 V2 protocol uses five tool calls, eight model turns, a two-error protocol limit, JSON mode, omitted temperature, a 2,048-token output limit using `max_tokens`, 15-second attempt pacing, and pause on the first HTTP 429 with the configured Gemini compatible backend. These are experiment settings, not universal defaults or guarantees of provider availability, determinism, or free usage. See the [runner guide](RUNNER.md) for backend setup and exact resume rules.

For an offline interface check with explicit policy selection, from a clean committed checkout and using a fresh output directory:

```bash
python -m pip install -e ".[dev]"
python -m inquest run --suite datasets/authored-v2 --set holdout --policy v2 --backend heuristic --budgets 5 --output runs/authored-v2-heuristic-card-check
```

The heuristic is a separate non-LLM baseline with fixed `earliest-alert-v1` behavior and constant, uncalibrated confidence. It does not interpret the V2 prompt: selecting V2 records configuration without creating a V2 model result. Public samples and local browser execution also use the offline heuristic.

## Metrics and denominators

The [grading contract](GRADING.md) and [grader](../src/inquest/grader.py) define episode scores. The [runner summary](../src/inquest/runner.py) groups results by tool budget and difficulty, including `all`.

| Metric | Definition and reporting requirement |
|---|---|
| `service_ok`, `type_ok`, `fix_ok` | Exact service and fault matches; fix requires both labeled action and target. `diagnosis_ok` requires all three independently of report validity. |
| `submitted`, `report_valid` | Submission presence is distinct from valid structure and observation references. Missing, malformed, and valid-but-incorrect reports differ. |
| `success` / `success_rate` | Valid report plus correct joint diagnosis. For complete groups, successes / all planned episodes, retaining completed provider/protocol failures. Incomplete groups have null final rates and intervals: report planned, completed and unfinished counts. |
| `evidence_relevant_success` | Accepted success with at least one coarse gold tool/service-relevant citation. Report beside success; it is not claim-level support. |
| `evidence` and citation counts | Fraction of counted citations with coarse relevance. String references count once; duplicates are recorded separately. Invalid references remain in the denominator and invalidate the report. |
| `brier` | `(confidence - success)^2`, targeting accepted joint success. Invalid/missing confidence yields null. Report `mean_brier_available`, `brier_available`, `brier_missing`, and completion counts. Valid confidence on an invalid report is still scored against failure. |
| `invalid_reports`, `status_counts` | Invalid reports include absent reports after backend failures. Inspect status/transcripts before calling these malformed model submissions. |
| `steps`, `obs_tokens`, latency and usage | Attempted tool calls, observation-text token estimates, elapsed time and recorded provider usage. Report missing usage, errors, retries and abandoned attempts. Unavailable usage is not zero; latency includes pacing waits. |

The runner emits Wilson 95% success intervals for complete groups. They do not establish independent sampling or population validity. Report counts and paired case outcomes alongside percentages. A single Brier score does not establish calibration; averaging only available values can conceal failures.

## Reproducible comparisons and current evidence

1. Record clean source revision, frozen suite/set and hashes, policy prompt/hash, backend/model identity or revision, generation settings, budgets, record limits, and retry/transport configuration. Keep labels out of agent inputs.
2. Compare policies on identical frozen cases and compatible settings at each budget, with distinct output directories. Preserve failures and unfinished episodes; disclose case limits and selection. Do not pair different suites as identical incidents.
3. Retain manifests, journals, results, summaries, known/missing usage, and interruption history. Resume only unchanged configurations; completed failures remain completed. Use runner replay and comparison checks. Disclose provider alias drift and repeated-run variability.
4. Report per-suite/per-budget completion, validity, success, evidence relevance, Brier availability, cost and failure analysis. Publish reviewed artifacts with provenance; private archives limit external auditability.

The [offline baseline](../experiments/offline-baseline-v1/README.md) is a heuristic experiment. [Project progress](PROGRESS.md) identifies maintainer-executed Gemini runs and public/private artifact boundaries. This card introduces no new model scores or policy promotion. The [2026-10-25 walkthrough](releases/2026-10-25/README.md) records software/product verification for candidate `6eaa023`; tests, scripted probes, and handcrafted reports do not measure autonomous model accuracy.

## Limitations

- **Coverage:** fixed topology and ontology, one initiating fault, simplified synthetic metrics and sparse logs. No independent production incidents, multifault coverage, or held-out topology evaluation.
- **Causality and repairs:** label matching does not execute repairs, verify recovery, or validate operational parameters such as rollback versions. Clue reachability does not prove unique causality.
- **Evidence:** a benign record about a gold service can earn relevance. Success can accept valid but irrelevant citations. Claim-level entailment remains future work.
- **Independence:** public AI-authored cases and same-author review create tuning/memorization risks. Authored-v2's post-freeze construction does not make it blinded or externally independent.
- **Models and confidence:** small remote-model experiments cannot isolate prompt effects from sampling/provider drift. No fitted likelihood artifacts, validated Bayesian reasoner, or demonstrated calibration are published.
- **Operations:** replay verifies saved behavior, not remote-model determinism. Product verification is scoped to its recorded environment, not comprehensive infrastructure/platform validation.

## Maintenance and reuse

[Inquest](https://github.com/Pranjal677504/Inquest) is maintained by Pranjal Prajapati and contributors. The repository carries the [MIT license](../LICENSE); preserve its notice when reusing covered material. Include this card with the exact source/data revision when reporting experiments. The [roadmap](ROADMAP.md) tracks independent review, claim-level evidence, topology variation, and reasoner research.
