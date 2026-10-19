# Development roadmap

This roadmap describes the intended capabilities and the evidence needed to consider them complete. Milestone numbers are stable identifiers, not the order in which all work must occur. Completion dates and verification appear in the development log; unchecked items are planned work with no promised completion date.

## Current priorities

The runner, hosted Gemini experiments, frozen suites, replay and paired comparison are available. See [Project progress](PROGRESS.md) for reviewed results and current limitations. V2 remains the working evaluation baseline and V3 remains experimental; the launcher default remains V1. Both authored suites are development data for V3.

1. **Product investigation view (10, 18).** Display a saved run's tool timeline, cited observations, report, validation outcomes and provider errors in the browser without a model request. Then connect local execution with visible job state and finite budgets.
2. **Progress and comparisons (08, 13, 17).** Keep dated implementation status and complete experiment outcomes, including regressions and provider failures. Add a comparison view. Maintainer review controls publication; private raw archives are not automatically published.
3. **Independent assessment and evidence (14–16).** Obtain independent domain-expert review and evaluate claim-level support and topology variation. The two authored suites contain 32 single-author synthetic cases; they are not an independent benchmark.
4. **Reasoner research (06, 07, full 12–13).** Fit on separate development data and compare probe policies at equal budgets. A fitted Bayesian reasoner, additional agent styles and calibrated held-out results remain future work, rather than prerequisites for the initial replay-based product.

No additional live model run is needed to begin the offline product work. The existing workflow assumes no paid backend; the user verifies account free-tier status. GitHub operations are handled by the maintainer from VS Code.

## Foundation

- [x] **01 — Repository foundation.** Establish the project scope, license, roadmap, and an honest record of the existing prototype. Check local documentation links and exclude generated files.
- [x] **02 — Deterministic incident bundles.** Integrate the prototype topology and scenario generator. Validate inputs, deterministic output, serialization round trips, and fault coverage. Supply a small runnable example.
  - Published extension: nine versioned frozen JSONL sets, a checksummed provenance manifest, and a verified loader. These files provide the canonical initial evaluation inputs; cross-version RNG equivalence is not assumed.
- [x] **03 — Investigation tools.** Integrate telemetry tools, budgets, and observation IDs. Test invalid calls, limits, and deterministic trace selection. Inspect all tool output for unintended ground-truth disclosure.
- [x] **04 — Report grading.** Integrate service, fault, fix, and confidence grading. Validate malformed reports, non-finite confidence, missing evidence, and invalid citations. Document exactly what each metric measures.
- [ ] **05 — Bundle CLI.** Add safe generation and replay commands, seed ranges, useful errors, and overwrite protection. Verify a frozen bundle produces the same observations after reload.

## Investigation and evaluation

- [ ] **06 — Bayesian reasoning.** Integrate evidence tags, dev-only likelihood fitting, belief updates, and expected information gain. Publish training-suite/checksum provenance, tag definitions, count estimation, smoothing, priors, and the fitted artifact checksum. Do not fit on test or authored holdout cases. Validate probabilities, normalization, and probe choice on small fixtures with known answers, including uninformative probes and correlated evidence.
- [ ] **07 — Offline agents and fair comparisons.** Integrate random, downstream-alert, and information-gain agents. Align available system knowledge and budgets. Run a small smoke comparison and include failures.
- [ ] **08 — Reproducible evaluation.** Durable manifests, journals, strict resume, replay, failure-inclusive summaries and offline paired comparison are implemented. Maintainer-executed hosted model runs have been replayed offline. Independent assessment, immutable remote model identity and broader evaluation evidence remain incomplete. Preserve all outcomes, settings, suite/source/prompt hashes, usage and missingness; publish only reviewed artifacts.
- [ ] **09 — Packaging and CI.** Installed CLI, an isolated wheel/console check, examples, checksums and the Python 3.10–3.14 plus Chromium workflow are implemented. Published checkpoints have passed the six-job matrix. The V3 implementation passed 453 Python tests locally; verify the current remote result in PR checks. Bundled model-resource acceptance criteria remain open.
- [ ] **10 — Investigation replay.** CLI replay of complete saved requests, responses, observations and reports is implemented. Browser replay and proposed belief transitions remain pending. Save full tool observations and belief transitions. Add a self-contained way to inspect a successful and a failed investigation without credentials.

## LLM and research evidence

- [ ] **11 — LLM adapters.** Ollama and compatible adapters pass HTTP fixtures; maintainer-executed Gemini runs establish actual hosted execution. Strict actions, bounded retries, pacing, quota pause, usage and report validation are implemented. Live Ollama and additional structured-perception/ReAct styles remain unverified or incomplete.
- [ ] **12 — Real local-model pilot.** Hosted single-agent Gemini pilots and policy comparisons are available. A real local-model run and the full comparison of the proposed agent styles remain pending; hosted results do not complete those acceptance criteria. Retain model identity, transcripts, settings, failures and limitations.
- [ ] **13 — Failure analysis and calibration.** Representative hosted-run failures, gains, regressions, provider errors and confidence missingness have been reviewed. Tag evaluation and fitted calibration assessed on separate held-out data remain incomplete.
- [ ] **14 — Authored holdout incidents.** Two sixteen-case suites provide explicit definitions, casebooks, loader support and source/data checksums. Authored-v2 was prepared after V2 prompt freeze; both suites subsequently informed V3. All cases are AI-authored and reviewed by the same author; independent domain-expert review remains pending. Preserve the observation boundary, versioned bytes and explicit disclosure of tuning. Public single-author cases do not establish secret test isolation or production validity.
- [ ] **15 — Evidence support.** An additive `evidence_relevant_success` gate now reports accepted diagnoses with at least one coarse tool/service-relevant citation. Claim-level support remains incomplete. Extend grading to check actual supporting observations or lines, with examples of valid and invalid citations. Keep legacy metrics clearly identified.
- [ ] **16 — Topology variation.** Introduce configurable call graphs and a held-out topology evaluation. Test causal propagation and agent knowledge under the new graphs.

## Showcase and release

- [ ] **17 — Reproducible result figures.** Generate plots from committed run data with uncertainty, clear labels, and a documented reproduction command. Share successes and failures.
- [ ] **18 — Release and walkthrough.** A benchmark card, setup guide, architecture explanations, walkthrough, changelog, and versioned release, supported by setup verification from a fresh checkout.

## Completion criteria

Completed milestones have an implementation or artifact, relevant verification, and a dated development-log entry. Published experiments include the runs and settings behind their results. Existing prototype components retain their integration history. A pending item indicates that its acceptance evidence is incomplete.

Scope may change as tests and experiments reveal better approaches. Material changes to the plan are accompanied by a rationale in the development log.
