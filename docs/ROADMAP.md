# Development roadmap

Milestones are ordered by dependency. Each development session completes one focused milestone or a coherent part of it. Complex milestones may take several sessions. A completion mark requires the stated evidence; a calendar date alone does not imply completion.

## Foundation

- [x] **01 — Repository foundation.** Establish the project scope, license, roadmap, and an honest record of the existing prototype. Check local documentation links and exclude generated files.
- [ ] **02 — Deterministic incident bundles.** Integrate the prototype topology and scenario generator. Validate inputs, deterministic output, serialization round trips, and fault coverage. Supply a small runnable example.
- [ ] **03 — Investigation tools.** Integrate telemetry tools, budgets, and observation IDs. Test invalid calls, limits, and deterministic trace selection. Inspect all tool output for unintended ground-truth disclosure.
- [ ] **04 — Report grading.** Integrate service, fault, fix, and confidence grading. Validate malformed reports, non-finite confidence, missing evidence, and invalid citations. Document exactly what each metric measures.
- [ ] **05 — Bundle CLI.** Add safe generation and replay commands, seed ranges, useful errors, and overwrite protection. Verify a frozen bundle produces the same observations after reload.

## Investigation and evaluation

- [ ] **06 — Bayesian reasoning.** Integrate evidence tags, dev-only likelihood fitting, belief updates, and expected information gain. Validate probabilities, normalization, and probe choice on small fixtures with known answers.
- [ ] **07 — Offline agents and fair comparisons.** Integrate random, downstream-alert, and information-gain agents. Align available system knowledge and budgets. Run a small smoke comparison and include failures.
- [ ] **08 — Reproducible evaluation.** Record scenario IDs, run configuration, code revision, model checksum, timings, and errors. Produce raw JSONL and summaries with confidence intervals. Verify interrupted runs preserve usable artifacts.
- [ ] **09 — Packaging and CI.** Add an installable command, bundled model resources, tests across supported Python versions, and a wheel smoke test outside the checkout. Publish passing workflow evidence.
- [ ] **10 — Investigation replay.** Save full tool observations and belief transitions. Add a self-contained way to inspect a successful and a failed investigation without credentials.

## LLM and research evidence

- [ ] **11 — LLM adapters.** Integrate local and hosted backends, structured perception, and ReAct. Test parse failures, retries, cache behavior, per-episode token accounting, and report validation using scripted responses. Document how to run locally without an API key.
- [ ] **12 — Real local-model pilot.** Run both LLM agent styles on the same frozen cases using an available local model. Save the model identity, prompts, transcript, usage, outcomes, and limitations. If a model or sufficient compute is unavailable, leave this milestone pending and request the specific missing input.
- [ ] **13 — Failure analysis and calibration.** Inspect representative failures. Measure tag accuracy and confidence calibration; fit any calibration only on dev data and assess it on held-out data.
- [ ] **14 — Authored holdout incidents.** Add a small documented set of hand-authored incidents outside the random generator. Record construction, ground truth, and how they differ from generated cases.
- [ ] **15 — Evidence support.** Extend grading to check actual supporting observations or lines, with examples of valid and invalid citations. Keep legacy metrics clearly identified.
- [ ] **16 — Topology variation.** Introduce configurable call graphs and a held-out topology evaluation. Test causal propagation and agent knowledge under the new graphs.

## Showcase and release

- [ ] **17 — Reproducible result figures.** Generate plots from committed run data with uncertainty, clear labels, and a documented reproduction command. Share successes and failures.
- [ ] **18 — Release and walkthrough.** Finish the benchmark card, setup guide, architecture explanations, one walkthrough, changelog, and a versioned release. Verify setup from a fresh checkout and stop the daily build schedule when all accepted milestones are complete.

## Working rules

Commit completed changes with their current dates and messages that explain the behavior added or fixed. Integrating a module from the existing prototype is recorded as integration. Experiments are recorded only after they run. Unfinished or blocked milestones stay open.

The roadmap is a plan, not a guarantee that every feature will be suitable. Revise it when tests or experiments reveal a better direction, and record why.
