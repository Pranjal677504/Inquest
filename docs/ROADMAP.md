# Development roadmap

This roadmap describes the intended capabilities and the evidence needed to consider them complete. Milestone numbers are stable identifiers, not the order in which all work must occur. Completion dates and verification appear in the development log; unchecked items are planned work with no promised completion date.

## Current priorities

The generator, tools, browser, and grader are available. The next work should test the investigation problem before adding more convenience features:

1. **Review authored cases (14).** `authored-v1` now supplies 16 AI-authored causal cases, complete definitions, checksums, and reachable support/counterevidence probes. It uses no random generator or signal templates. Single-author checks are recorded; obtain independent domain-expert review before treating the suite as independently validated, and disclose any tuning against these public cases.
2. **An early real-model pilot (parts of 11, 08, and 12).** The minimal JSON tool loop, Ollama/compatible adapters, durable recording, resume and replay are now implemented and tested. Run an actual available model on smoke fixtures and authored cases. Publish actual prompts, observations, reports, errors, model identity, usage, and case checksums. This pilot need not wait for the Bayesian agent or a CLI; it will not complete the two-agent comparison in 12.
3. **Reasoner and comparative evidence (06, 07, then full 12–13).** Fit on separate development data, compare probe policies at equal budgets, and assess failures and calibration on untouched cases. A simple signature classifier should be included to show whether the task requires more than recognizing authored patterns.

CI is brought forward from 09. Packaging, CLI, and richer replay remain useful but do not substitute for independent validation. Real-model runs require an available model and compute; no paid backend is assumed.

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
- [ ] **08 — Reproducible evaluation.** Implementation checkpoint: run manifests record data/code/prompt/model identity, settings, observations, errors and usage; durable journals preserve interrupted attempts, and summaries retain failures with per-budget Wilson intervals. Actual model evidence and independently reviewed evaluation remain pending. Record frozen suite versions and data-file checksums alongside scenario IDs, run configuration, code revision, model checksum, timings, and errors. Larger versioned sets will support likelihood fitting and performance assessment. Produce raw JSONL and summaries with confidence intervals. Verify interrupted runs preserve usable artifacts.
- [ ] **09 — Packaging and CI.** Implementation checkpoint: installed `inquest` CLI and a wheel/console smoke run outside the checkout are implemented and locally verified; CI configuration includes this check. Hosted verification and the broader model-resource acceptance criteria remain pending. An installable command, bundled model resources, and a wheel smoke test outside the checkout. The Python 3.10–3.14 Linux matrix is implemented early in [the workflow](../.github/workflows/tests.yml) and [passed](https://github.com/Pranjal677504/Inquest/actions/runs/37794556651): 243 tests, four examples, installation, and ten frozen checksum entries on every version. The authored-suite update passed 303 Python tests and six browser tests locally on Linux/Python 3.12.14; hosted verification for that update is pending publication. The remaining packaging acceptance criteria are incomplete.
- [ ] **10 — Investigation replay.** CLI replay of complete saved requests, responses, observations and reports is implemented. Browser replay and proposed belief transitions remain pending. Save full tool observations and belief transitions. Add a self-contained way to inspect a successful and a failed investigation without credentials.

## LLM and research evidence

- [ ] **11 — LLM adapters.** Ollama and compatible non-streaming chat adapters, strict JSON actions, bounded transport/protocol errors, and usage accounting now pass loopback HTTP and scripted-agent tests. Actual provider/model execution and additional agent styles remain pending. Integrate local and hosted backends, structured perception, and ReAct. Test parse failures, retries, cache behavior, per-episode token accounting, and report validation using scripted responses. Document how to run locally without an API key.
- [ ] **12 — Real local-model pilot.** First publish an actual single-agent pilot using the existing tools and grader; then compare both LLM agent styles on the same frozen and independently authored cases. Record model identity and revision, prompts, transcripts, usage, outcomes, failures, and limitations. Requires a suitable local model and sufficient compute. Scripted adapters and handcrafted reports do not count as model runs; a single-agent pilot does not complete the full comparison.
- [ ] **13 — Failure analysis and calibration.** Inspect representative failures. Measure tag accuracy and confidence calibration; fit any calibration only on dev data and assess it on held-out data.
- [ ] **14 — Authored holdout incidents.** Implementation checkpoint: 16 AI-authored cases, explicit keyframes, checked casebook, versioned loader support, and structural/causal self-checks are available in `datasets/authored-v1`. Independent domain-expert review remains pending, so this milestone is not marked complete. Original acceptance criteria: add a small independently authored, checksummed versioned suite outside the random generator. Document each causal narrative, telemetry construction, distractors, ground truth, and differences from generator templates. Cases must work through the existing observation and grading interfaces without exposing labels. Record review and freeze before fitting or prompt tuning. Public authored cases reduce generator coupling but do not establish secret test isolation or production validity; later tuning against them must be disclosed.
- [ ] **15 — Evidence support.** An additive `evidence_relevant_success` gate now reports accepted diagnoses with at least one coarse tool/service-relevant citation. Claim-level support remains incomplete. Extend grading to check actual supporting observations or lines, with examples of valid and invalid citations. Keep legacy metrics clearly identified.
- [ ] **16 — Topology variation.** Introduce configurable call graphs and a held-out topology evaluation. Test causal propagation and agent knowledge under the new graphs.

## Showcase and release

- [ ] **17 — Reproducible result figures.** Generate plots from committed run data with uncertainty, clear labels, and a documented reproduction command. Share successes and failures.
- [ ] **18 — Release and walkthrough.** A benchmark card, setup guide, architecture explanations, walkthrough, changelog, and versioned release, supported by setup verification from a fresh checkout.

## Completion criteria

Completed milestones have an implementation or artifact, relevant verification, and a dated development-log entry. Published experiments include the runs and settings behind their results. Existing prototype components retain their integration history. A pending item indicates that its acceptance evidence is incomplete.

Scope may change as tests and experiments reveal better approaches. Material changes to the plan are accompanied by a rationale in the development log.
