# Project progress

Updated 2026-10-25. This page consolidates implementation status and the workflow for privately reviewed maintainer-supplied runs. The saved-run viewer (PR #6), local execution (PR #7), hosted `/runs` routing (PR #9), and public sample walkthrough (PR #10) are merged on `main`. GitHub publication remains maintainer-controlled.

## Product goal

Deliver an evidence-backed investigation workbench for replayed synthetic microservice incidents. Users should be able to start an investigation, follow its tool timeline, inspect cited observations, review the diagnosis and proposed repair, and compare saved runs. Read-only tools and transparent uncertainty are part of that contract. Production telemetry integration and repair execution are outside the initial release.

## Implemented and verified

| Area | Status |
|---|---|
| Browser workbench | Telemetry browsing, diagnosis submission, stale-response protection, keyboard tabs, and browser regression coverage |
| Saved-run viewer | Local folder/file import, exact-attempt tool timeline, citation links, reports, errors, unfinished jobs and saved comparison artifacts; no upload or model calls |
| Local execution | Opt-in loopback service; one offline worker, durable SQLite jobs, selected cases/budgets, idempotent start, cancellation, restart recovery and direct saved-result review |
| Frozen inputs | 120 smoke cases plus two separate 16-case authored suites; 18 canonical checksums |
| Investigation tools | Eight read-only tools, charged attempts, sequential observation IDs, detached telemetry |
| Report grading | Structural/reference validation, diagnosis and repair checks, coarse evidence relevance, Brier loss and missingness |
| Runner | Versioned prompts, strict JSON actions, durable journals, atomic results, locking, strict resume, replay and summaries |
| Providers | Compatible hosted and Ollama adapters; Gemini has maintainer-executed run evidence; live Ollama remains unverified |
| Free-tier workflow | Private key prompt, pacing, finite limits, first-429 pause and separate outputs; billing status remains the user's responsibility |
| Comparison | Offline paired results with compatible cases, scoring sources, limits, model settings, gains, regressions and usage |
| Policies | V1 and V2 prompt bytes preserved; V3 remains an experimental guidance candidate |

The V3 implementation passed **453 Python tests locally**. The subsequent merged saved-run viewer passed the six-job Python 3.10–3.14 and Chromium PR matrix. Scripted tests verify software behavior and reachability, not autonomous model accuracy.

The saved-run viewer update passed **454 Python tests and 12 Chromium workflows locally** on Linux/Python 3.12 with Playwright 1.55. Desktop and mobile layouts were inspected. Four maintainer-supplied saved-run folders opened successfully and all 64 episodes were inspected without network requests; no private run content is bundled with the viewer. The maintainer merged it through VS Code as PR #6. [Viewer usage](SAVED_RUNS.md) covers local startup and import limits.

The local-execution update passed **473 Python tests and 17 Chromium workflows locally** on Linux/Python 3.12 with Playwright 1.55. The launch script completed a browser-created offline job, retained it after restart and opened its saved result. Cancellation/recovery, completed-result reuse, lost-response deduplication, shutdown, identity restrictions and hosted-route isolation are tested. It merged in [PR #7](https://github.com/Pranjal677504/Inquest/pull/7), with successful pull-request and `main` CI. Local browser execution is not a live model result. See [Local execution](LOCAL_EXECUTION.md).

## Evaluation records and review status

The maintainer has executed compatible hosted Gemini experiments using the CLI and supplied saved runs for offline review. V1/V2/V3 are separately fingerprinted configurations. Saved requests, observations, reports, grades, provider/protocol errors and summaries support replay and comparison. Source and data integrity checks accompany the review.

Detailed run outcomes and transcripts remain in maintainer-controlled archives and local `runs/` directories. This implementation-progress page does not publish private-run aggregates or response identifiers. The previously published initial reference is documented separately in [the historical V1 experiment](../experiments/gemini-authored-budget5-v1/README.md).

| Configuration | Local output directory |
|---|---|
| authored-v1 / V1 | `runs/gemini-3-5-authored-budget5-v1` |
| authored-v1 / V2 | `runs/gemini-3-5-authored-budget5-policy-v2` |
| authored-v2 / V2 | `runs/gemini-3-5-authored-v2-budget5-policy-v2` |
| authored-v2 / V3 | `runs/gemini-3-5-authored-v2-budget5-policy-v3` |

Retain all completed outcomes, including backend failures, rather than replacing failed cases to improve a summary. V2 is the working evaluation baseline because it followed review of V1 failures and its prompt was frozen before authored-v2 was prepared. The CLI keeps V1 as its default to preserve existing invocation behavior and run configurations; select `--policy v2` explicitly for baseline runs. Both authored suites informed V3, so it remains experimental.

Review summaries carefully: the `invalid_reports` counter includes absent reports after backend failures. It must not automatically be described as a count of malformed submitted reports. Distinguish provider-response errors, retried transport failures, malformed intermediate actions, incorrect diagnoses, and invalid submitted reports. Available Brier/usage values and missingness must be reported together. A response rejected as `provider_response_missing_content` lacked the expected text field; without its raw body the exact response shape cannot be inferred.

## Policy and product decisions

Demand checks, caller evidence, mechanism classification and handling contradictory observations remain targets for improvement. A correct label or a positive coarse relevance score does not establish complete causal support. Changed instructions are an experiment; they do not guarantee model compliance. No hidden answer repair, probe injection, confidence clipping or automatic promotion is used.

Use reviewed paired outcomes to decide whether a candidate should replace a baseline. A single remote-model run does not isolate prompt wording from sampling or changes behind a model alias. Preserve failed candidates as engineering evidence. The [release walkthrough](releases/2026-10-25/README.md) passed for candidate `6eaa023`. The next product work is the benchmark card, changelog and versioned release, followed by claim-level evidence support and independent assessment.

## Interpretation boundaries

Both authored suites informed V3 development. They are development data for V3. Authored-v2 was prepared after the V2 prompt was frozen, but the same author had inspected earlier failures; it is not independent, blinded, secret or representative production data. Relevance metadata differs between suites, including useful health checks added to new cases. Report suites separately. Coarse relevance does not establish claim-level causal support.

## Next product milestone

1. Keep V2 as the working evaluation baseline and V3 as a recorded experiment. The CLI default remains V1 for existing commands; use `--policy v2` explicitly when running the baseline.
2. The saved-run viewer (PR #6), opt-in offline local execution (PR #7), and public sample walkthrough (PR #10) are merged. Completed runs can be reviewed without a model request.
3. The [2026-10-25 fresh-checkout walkthrough](releases/2026-10-25/README.md) passed for candidate `6eaa023`: 473 Python tests, 18 Chromium tests, all frozen checksums, the public sample, an actual local offline job and restart, saved-result review, and hosted route checks. Prepare the benchmark card, changelog and versioned release to complete milestone 18. Browser-started model execution remains a separate future capability.
4. The viewer displays saved CLI comparison artifacts with counts, per-case outcomes, usage and limitations. Direct selection and verified pairing of two folders in the browser remain future work; compatibility validation stays in the CLI.
5. Prioritize claim-level evidence support and independently reviewed assessment cases, then topology variation. A fitted reasoner and calibration remain separate research work.

No further live model run is required for this offline product work. Future experiments should preserve all outcomes, distinguish provider failures from diagnosis failures, and state whether their cases informed development.

## Where details live

- [Development log](DEVELOPMENT_LOG.md): dated work and verification history.
- [Roadmap](ROADMAP.md): remaining acceptance criteria; unchecked research milestones remain incomplete.
- [Runner](RUNNER.md): install, run, pause, resume, replay, summarize and compare.
- [V3 policy](POLICY_V3.md): experiment contract and limitations.
- [Evidence coverage](EVIDENCE_COVERAGE.md): coarse relevance and historical metadata limitations.
- [Testing](TESTING.md): behavior and browser checks.

GitHub commits, pushes, PR changes and merges are handled by the maintainer from VS Code. Private raw run archives are not published by these status documents.
