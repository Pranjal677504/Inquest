# Development log

This repository starts from an existing local Inquest prototype. This log records integration, improvements, verification, and remaining limitations. The initial repository setup and first code milestone were completed on 6 October 2026. Subsequent entries use the actual dates of completed work.

## 2026-10-06 — Initial setup and first code milestone

### Repository foundation

Established the repository scope, milestone acceptance criteria, license, and development log. The initial repository contains documentation and repository hygiene files. Prototype code and previously generated result tables will be integrated in later verified milestones.

Verification: checked all local Markdown links and reviewed the initial file list to exclude credentials, generated caches, and prior run artifacts. No software tests apply to this documentation-only milestone.

### README technical expansion

Expanded the foundation README to explain the investigation problem, architecture, Bayesian reasoning, initial service graph, incident categories, tools, agent comparisons, evaluation contract, reproduction requirements, and validity limits. Details were grounded in the existing local prototype and marked as planned where not yet implemented. At this point in the initial setup, only the foundation milestone was complete.

Verification: checked documentation links, Mermaid source, the illustrative JSON report, and the documented topology and tool names against the prototype. Runnable setup and measured results remain pending their implementation milestones.

GitHub preview exposed a Markdown conflict in the display equations and an unsupported math macro. Changed them to fenced-math format with supported notation and checked the published presentation.

### Deterministic incident bundles

Integrated milestone 02. The topology and generator originate from the existing local Inquest prototype (`src/inquest/topology.py` and `src/inquest/scenario.py`). This milestone integrates and improves those components.

Added generation and seed-range validation, explicit unknown-service errors, JSON bundle checks, a public Python API, basic package configuration, and a runnable construction/replay example. Replaced the prototype's trace note `root span failing` with ordinary request-failure wording so telemetry no longer explicitly labels the answer. Construction bundles still deliberately contain labels and must not be passed directly to agents.

Verification on Python 3.14: installed `python -m pip install -e ".[dev]"` into a fresh isolated environment; `python -m pytest -q` passed 117 tests. Tests cover all eight faults across every difficulty/split combination, serialization round trips, deterministic generation, global random-state isolation, malformed inputs, shortest-path queries, database lock propagation, and traffic propagation to dependencies. Ran `python examples/generate_incident.py`; the example produced eight services, 120 telemetry minutes, two events, 60 traces, and an identical JSON round trip. Compared the same hard OOD bundle in separate processes with two Python hash seeds from outside the checkout; fingerprints matched. Checked local documentation links and `git diff --check`.

Limitations: installation and tests are locally verified on Python 3.14 only; the declared Python 3.10+ range will receive a CI matrix in milestone 09. Cross-version seed fingerprints are not guaranteed. Tools, agents, grading, end-to-end investigations, and benchmark results remain pending. Basic packaging is present to make this milestone runnable; the full CLI, wheel checks, and CI acceptance gate remain open.

### Documentation corrections and design rationale

Clarified that Python 3.14 is the locally verified environment and that Python 3.10+ remains an unverified compatibility target. Replaced operational instructions in the roadmap with reader-facing deliverables and prerequisites. Consolidated the initial work under its actual date and removed wording suggesting that multiple development days had already elapsed. Added maintainer responsibilities and design notes covering implementation choices, alternatives, evidence, and limitations.

Verification: checked local documentation links and the documented API examples against the installed package; reviewed the design notes against the source and tests; checked formatting with `git diff --check`. These are documentation changes; no additional software test results are claimed.

### Repository metadata and frozen evaluation inputs

Added a repository description and the topics `python`, `incident-response`, `root-cause-analysis`, `microservices`, `synthetic-data`, `reproducible-research`, and `agent-evaluation`; read back the published settings to verify them.

Published `inquest-smoke-v1`: nine frozen JSONL sets containing 120 synthetic cases. Each development set contains eight cases, and each test/alternate-wording set contains sixteen, across easy, medium, and hard difficulties. The manifest records the actual generation runtime, generator revision, source hashes, ordered identities, selection settings, byte counts, and file hashes. A SHA-256 catalog covers the manifest and every data file. Versioned file bytes, rather than cross-version generation from seeds, are the canonical evaluation inputs.

Added a loader and example that verify checksums before loading saved cases, then check metadata and scenario validity. Tests read all nine sets with generation and random-number construction disabled and reject changed files, truncated files, missing checksums, and invalid set names. `python -m pytest -q` passed 135 tests on Python 3.14. Both runnable examples passed. `shasum -a 256 -c SHA256SUMS` verified all ten catalog entries. Documentation links, the published manifest fingerprint, and formatting were checked.

Limitations: these are small public fixtures with labels, not secret holdout data, complete service/fault coverage, statistical performance evidence, or sufficient likelihood training data. They contain no agent results. Agent access must exclude labels, seeds, IDs, and construction metadata. Data is distributed in the checkout. Published suites are immutable; changed cases require a new version. Python compatibility verification remains limited to 3.14.

Next milestone: budgeted investigation tools with observation validation and checks for answer leakage.

## 2026-10-07 — Budgeted investigation tools

Completed milestone 03 by integrating the eight tools from the local prototype's `src/inquest/env.py` and adapting their observation contract. Added validated step/record limits, sequential observation IDs, detached transcripts, explicit invalid-request outcomes, and a five-query manual example over a frozen case.

Changed the prototype's free-call option so every attempted request is charged. Trace selection now uses the fixed last 40 telemetry minutes rather than the labeled onset. The environment projects permitted fields into a detached telemetry snapshot and does not retain the full construction bundle. Extra metadata in health, metric, log, event, and trace records is excluded. Event lists return summaries, with full details available through a separate call. Log searches use case-insensitive literal substrings instead of regex. Alert threshold crossings require three complete consecutive samples, including at the end of the time horizon.

Verification on Python 3.14: installed `python -m pip install -e ".[dev]"` into a fresh isolated environment; `python -m pytest -q` passed 178 tests. The new tests exercise every tool across all 120 frozen cases, charged invalid requests, zero/exhausted budgets, record caps, literal filters, derived metric/alert behavior, trace cycling and JSON replay, mutation isolation, and independence from construction labels and extra metadata. All three examples ran successfully from outside the checkout. The manual example produced five observation IDs and exhausted its five-step budget without printing construction labels or a scenario ID. All ten frozen-suite checksum entries passed; dataset bytes remain unchanged. Checked local documentation links and `git diff --check`.

Limitations: the example's queries are predetermined, not selected by an autonomous agent. The environment is an observation boundary, not a sandbox for hostile Python code or protection against memorizing public fixtures. Arbitrary external telemetry could contain answer-like text despite field projection. Step budgets approximate investigation cost; text-token counts are estimates. Python versions other than 3.14 remain unverified. Grading and scored agent comparisons are still pending.

Next milestone: report grading with malformed-output, confidence, and citation validation.

### Web workbench integration and preview repair

The repository now requires pull requests for changes to `main`. The initial tool publication is [PR #2](https://github.com/Pranjal677504/Inquest/pull/2); its first preview failed with **No Flask entrypoint found**. The supplied Vercel build error established the cause: the tool branch did not yet contain the web application's `app.py`. Connector access to that Vercel team remained unavailable.

Reviewed [PR #1](https://github.com/Pranjal677504/Inquest/pull/1), which already contained the Flask workbench, static assets, API routes, dependency, and Python runtime selection. Its Vercel status was successful, with no outstanding review threads. Verified 137 tests in an isolated branch snapshot, page/assets/config/health routes, and the existing live browser's frozen-case diagnosis response. PR #1 was merged into `main` at `6f2b725a38379ef64ab3699820efc287e58d3c5f` after the maintainer explicitly authorized this repair.

Integrated that updated `main` into the tool branch without rewriting either branch's commits. Resolved overlapping README sections to retain both the browser setup and the implemented tool interface. Updated the design notes to distinguish the browser's unrestricted educational flow from budgeted benchmark observations.

Combined verification on Python 3.14: 180 tests passed; all three examples ran from outside the checkout; all ten frozen checksum entries passed. The published suite bytes remain unchanged. Integration supplies the missing deployment entry point; the new hosted preview and merge status are recorded in the linked PR.

## 2026-10-08 — Report grading

Completed milestone 04 by integrating the prototype's `src/inquest/grader.py` accuracy checks, gold tool/service relevance mapping, Brier calculation, and evaluator metadata. The labeled scenario now goes to the grader explicitly; the tool environment continues to hold telemetry only. Added structural report validation, reference checks against saved successful observations, citation accounting, and separate component correctness, diagnosis correctness, report validity, and accepted joint success.

Invalid confidence is reported as unavailable, with no numeric-string coercion, clipping, or default. Unknown, malformed, and failed-call citations remain in the evidence denominator; repeated strings count once. Empty log/event/trace results earn no relevance credit. Event and trace services are derived from returned records rather than query arguments. Added a grading guide and a runnable two-report demonstration that identifies the frozen suite, set, checksum, repository revision, and uncommitted state. Predictions and confidence in this demonstration are handcrafted fixtures.

Verification on Python 3.14: installed the package and development dependencies in a fresh isolated environment; `python -m pytest -q` passed 243 tests. The 63 additional test cases cover exact and partial predictions, action/target mismatches, empty and malformed reports, required fields, non-finite and out-of-range confidence, unknown/malformed/duplicate citations, failed calls, empty results, event/trace relevance, input immutability, evaluator misuse, and JSON-safe output. Evaluator-authored correct-report fixtures were scored over all 120 committed frozen cases. All four examples ran from outside the checkout; the new example produced accepted success for the valid report and an explicit invalid-reference failure for the second. All ten frozen checksum entries passed. The dataset files remain unchanged.

Limitations: evidence scores still check authored tool/service relevance rather than claim support; existing irrelevant citations can be valid references. Fixes check action and target, with operational parameters unscored. Brier loss concerns accepted joint success and does not establish calibration. Invalid-confidence missingness must be disclosed in future summaries. The evaluator must pair the scenario and transcript from the same episode. The example and test fixtures are not agent accuracy results. Only Python 3.14 has been verified locally.

Next milestone: safe bundle generation and replay commands.

## How to read this log

Entries use the date on which work occurred. Multiple changes on one day appear together. Each entry identifies the affected milestone, origin of integrated components, verification evidence, limitations, and next planned capability.
