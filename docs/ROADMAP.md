# Development roadmap

This roadmap describes the intended capabilities and the evidence needed to consider them complete. Milestone numbers are stable identifiers, not the order in which all work must occur. Completion dates and verification appear in the development log; unchecked items are planned work with no promised completion date.

## Current priorities

The generator, tools, browser, and grader are available. The next work should test the investigation problem before adding more convenience features:

1. **Independent authored cases (14).** Construct a new versioned suite without calling the random generator or reusing its fault-signal templates. Include distractors, conflicting symptoms, and documented causal explanations. Review cases before tuning agents against them.
2. **An early real-model pilot (parts of 11, 08, and 12).** Implement a minimal local-model tool loop and run recording, then run it on both smoke fixtures and authored cases. Publish actual prompts, observations, reports, errors, model identity, usage, and case checksums. This pilot need not wait for the Bayesian agent or a CLI; it will not complete the two-agent comparison in 12.
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
- [ ] **08 — Reproducible evaluation.** Record frozen suite versions and data-file checksums alongside scenario IDs, run configuration, code revision, model checksum, timings, and errors. Larger versioned sets will support likelihood fitting and performance assessment. Produce raw JSONL and summaries with confidence intervals. Verify interrupted runs preserve usable artifacts.
- [ ] **09 — Packaging and CI.** An installable command, bundled model resources, and a wheel smoke test outside the checkout. The Python 3.10–3.14 Linux matrix is implemented early in [the workflow](../.github/workflows/tests.yml); passing runs establish compatibility for their tested revisions. Local verification remains Python 3.14. The remaining packaging acceptance criteria are incomplete.
- [ ] **10 — Investigation replay.** Save full tool observations and belief transitions. Add a self-contained way to inspect a successful and a failed investigation without credentials.

## LLM and research evidence

- [ ] **11 — LLM adapters.** Integrate local and hosted backends, structured perception, and ReAct. Test parse failures, retries, cache behavior, per-episode token accounting, and report validation using scripted responses. Document how to run locally without an API key.
- [ ] **12 — Real local-model pilot.** First publish an actual single-agent pilot using the existing tools and grader; then compare both LLM agent styles on the same frozen and independently authored cases. Record model identity and revision, prompts, transcripts, usage, outcomes, failures, and limitations. Requires a suitable local model and sufficient compute. Scripted adapters and handcrafted reports do not count as model runs; a single-agent pilot does not complete the full comparison.
- [ ] **13 — Failure analysis and calibration.** Inspect representative failures. Measure tag accuracy and confidence calibration; fit any calibration only on dev data and assess it on held-out data.
- [ ] **14 — Authored holdout incidents.** Next research milestone: add a small independently authored, checksummed versioned suite outside the random generator. Document each causal narrative, telemetry construction, distractors, ground truth, and differences from generator templates. Cases must work through the existing observation and grading interfaces without exposing labels. Record review and freeze before fitting or prompt tuning. Public authored cases reduce generator coupling but do not establish secret test isolation or production validity; later tuning against them must be disclosed.
- [ ] **15 — Evidence support.** Extend grading to check actual supporting observations or lines, with examples of valid and invalid citations. Keep legacy metrics clearly identified.
- [ ] **16 — Topology variation.** Introduce configurable call graphs and a held-out topology evaluation. Test causal propagation and agent knowledge under the new graphs.

## Showcase and release

- [ ] **17 — Reproducible result figures.** Generate plots from committed run data with uncertainty, clear labels, and a documented reproduction command. Share successes and failures.
- [ ] **18 — Release and walkthrough.** A benchmark card, setup guide, architecture explanations, walkthrough, changelog, and versioned release, supported by setup verification from a fresh checkout.

## Completion criteria

Completed milestones have an implementation or artifact, relevant verification, and a dated development-log entry. Published experiments include the runs and settings behind their results. Existing prototype components retain their integration history. A pending item indicates that its acceptance evidence is incomplete.

Scope may change as tests and experiments reveal better approaches. Material changes to the plan are accompanied by a rationale in the development log.
