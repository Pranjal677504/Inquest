# Project progress

Updated 2026-10-20. This page consolidates implementation status and the workflow for privately reviewed maintainer-supplied runs. The saved-run viewer baseline was merged by the maintainer at `5e4edda3e4415cbfad7e65c43d9a8509844ae639` (PR #6). The subsequent local-execution update is prepared as a patch for maintainer review and application through VS Code; the assistant performs no GitHub mutation.

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

The local-execution update passed **473 Python tests and 17 Chromium workflows locally** on Linux/Python 3.12 with Playwright 1.55. The actual launch script completed a browser-created offline job, retained it after restart and opened its saved result. Cancellation/recovery, completed-result reuse, lost-response deduplication, shutdown, identity restrictions and default hosted-route isolation are tested. Local browser execution is not a live model result. Its PR/CI verification remains for the maintainer's VS Code workflow. See [Local execution](LOCAL_EXECUTION.md).

## Evaluation records and review status

The maintainer has executed compatible hosted Gemini experiments using the CLI and supplied saved runs for offline review. V1/V2/V3 are separately fingerprinted configurations. Saved requests, observations, reports, grades, provider/protocol errors and summaries support replay and comparison. Source and data integrity checks accompany the review.

Detailed run outcomes and transcripts remain in maintainer-controlled archives and local `runs/` directories. This implementation-progress page does not publish private-run aggregates or response identifiers. The previously published initial reference is documented separately in [the historical V1 experiment](../experiments/gemini-authored-budget5-v1/README.md).

| Configuration | Local output directory |
|---|---|
| authored-v1 / V1 | `runs/gemini-3-5-authored-budget5-v1` |
| authored-v1 / V2 | `runs/gemini-3-5-authored-budget5-policy-v2` |
| authored-v2 / V2 | `runs/gemini-3-5-authored-v2-budget5-policy-v2` |
| authored-v2 / V3 | `runs/gemini-3-5-authored-v2-budget5-policy-v3` |

Retain all completed outcomes, including backend failures, rather than replacing failed cases to improve a summary. The working evaluation baseline remains V2; V3 stays experimental. The launcher default remains V1, so these are explicit selection decisions rather than a default-setting change.

Review summaries carefully: the `invalid_reports` counter includes absent reports after backend failures. It must not automatically be described as a count of malformed submitted reports. Distinguish provider-response errors, retried transport failures, malformed intermediate actions, incorrect diagnoses, and invalid submitted reports. Available Brier/usage values and missingness must be reported together. A response rejected as `provider_response_missing_content` lacked the expected text field; without its raw body the exact response shape cannot be inferred.

## Policy and product decisions

Demand checks, caller evidence, mechanism classification and handling contradictory observations remain targets for improvement. A correct label or a positive coarse relevance score does not establish complete causal support. Changed instructions are an experiment; they do not guarantee model compliance. No hidden answer repair, probe injection, confidence clipping or automatic promotion is used.

Use reviewed paired outcomes to decide whether a candidate should replace a baseline. A single remote-model run does not isolate prompt wording from sampling or changes behind a model alias. Preserve failed candidates as engineering evidence. The next work is the offline product interface rather than another immediate model run.

## Interpretation boundaries

Both authored suites informed V3 development. They are development data for V3. Authored-v2 was prepared after the V2 prompt was frozen, but the same author had inspected earlier failures; it is not independent, blinded, secret or representative production data. Relevance metadata differs between suites, including useful health checks added to new cases. Report suites separately. Coarse relevance does not establish claim-level causal support.

## Next product milestone

1. Keep V2 as the working evaluation baseline and retain V3 as a recorded experiment. Keep the current launcher default documented separately: it remains V1, not V2.
2. The browser saved-run viewer is merged: tool timeline, actual evidence citations, final report, validation errors and provider errors. Reading a completed run requires no model request.
3. Local execution is implemented in the prepared patch, using the offline heuristic and existing runner artifacts. Validate and publish it through VS Code. Hosted/model execution from the browser remains a separate future capability.
4. The viewer can display saved CLI comparison artifacts with counts, per-case outcomes, usage and limitations. Direct selection and verified pairing of two folders inside the browser remain future work; compatibility validation stays in the CLI.
5. Prepare a reproducible walkthrough and release checklist, then prioritize claim-level evidence support and independently reviewed assessment/topology variation. A fitted reasoner and calibration remain separate research work.

No further live model run is required for this offline product work. Future experiments should preserve all outcomes, distinguish provider failures from diagnosis failures, and state whether their cases informed development.

## Where details live

- [Development log](DEVELOPMENT_LOG.md): dated work and verification history.
- [Roadmap](ROADMAP.md): remaining acceptance criteria; unchecked research milestones remain incomplete.
- [Runner](RUNNER.md): install, run, pause, resume, replay, summarize and compare.
- [V3 policy](POLICY_V3.md): experiment contract and limitations.
- [Evidence coverage](EVIDENCE_COVERAGE.md): coarse relevance and historical metadata limitations.
- [Testing](TESTING.md): behavior and browser checks.

GitHub commits, pushes, PR changes and merges are handled by the maintainer from VS Code. Prepared local files/patches should be reviewed before publication. Raw run archives are not included in this documentation patch.
