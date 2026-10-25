# Development log

This repository starts from an existing local Inquest prototype. This log records integration, improvements, verification, and remaining limitations. The initial repository setup and first code milestone were completed on 6 October 2026. Subsequent entries use the actual dates of completed work.

For the consolidated current state, see [Project progress](PROGRESS.md). Earlier statements about pending provider runs or unavailable GitHub access describe their dated checkpoints and are superseded by later entries.

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

The original next milestone was safe bundle generation and replay commands; the review below changes that priority.

### Review corrections and compatibility CI

Reworked the README around the shipped browser, generator, frozen inputs, tools, and grader, with direct links to source and tests. Removed the long proposed-agent specification from the landing page. Added primary-source related work covering Cloud-OpsBench, OpenRCA, AIOpsLab, ITBench, ORCA-bench, and OpenRCA 2.0. Replayability and efficiency are established benchmark practices; information gain and calibration remain proposed experiments, not claimed advantages.

Clarified that standard-library core modules coexist with a Flask runtime dependency in the installed distribution. Added a read-only, pinned-action Linux CI matrix for Python 3.10–3.14 covering installation, behavior tests, frozen checksums, and examples outside the checkout. Workflow configuration does not itself establish compatibility; actual run results supply that evidence.

Changed research priorities: independently authored cases come next, followed by a minimal recorded real-model pilot, ahead of convenience CLI work. Existing milestone identifiers remain stable. Added acceptance requirements for separate fitting data, likelihood provenance, correlated evidence checks, leakage review, and public-holdout limitations. Design notes explain the proposed information-gain calculation and alternatives without suggesting a fitted model already exists.

Local verification on Python 3.14: 243 tests passed; the README's budgeted-tool example ran; all ten frozen checksum entries and local Markdown links passed; formatting checks passed. No source or published dataset bytes changed.

Hosted verification: [CI run 37794556651](https://github.com/Pranjal677504/Inquest/actions/runs/37794556651) at `92e6888a94be931e2a69d2d739e797e9ffa5ef23` passed on Python 3.10, 3.11, 3.12, 3.13, and 3.14 on Linux. Every job installed the package, passed 243 tests, verified all ten frozen checksum entries, and ran all four examples outside the checkout. The Vercel preview status also passed. These checks are linked in [PR #4](https://github.com/Pranjal677504/Inquest/pull/4); this follow-up records the actual results after they ran.

No independent cases, model runs, likelihood fits, or performance measurements are claimed by this correction. The next research milestone is the authored holdout suite.

## 2026-10-18 — Workbench reliability and explicit evidence relevance

Fixed two reproduced defects. Diagnosis responses and errors are now associated with the current case revision and request, so a late response cannot reveal an old answer under a newly loaded case. Diagnosis controls are disabled during case loading and submission, duplicate submissions are ignored, new cases reset the answer form, and non-JSON HTTP errors produce a useful status message. Case-load requests also use sequence checks to prevent older loads from replacing newer state.

Scenario loading now validates all health fields consumed by the investigation environment: status, a nonempty version string, nonnegative integer restart count, and integer certificate days. Expired certificates and additional metadata remain supported. Missing fields fail with `ValueError` at the loading boundary instead of a later tool-construction `KeyError`. Published dataset bytes are unchanged.

Added `evidence_relevant_success`, defined as existing accepted success plus at least one coarse tool/service-relevant citation. Existing success, report validation, and Brier definitions remain unchanged. This metric does not establish that cited text supports a claim; milestone 15 remains incomplete.

Added telemetry-tab Arrow Left/Right and Home/End navigation, roving focus, and tab/panel relationships. Six separate Chromium workflow tests exercise the real Flask API with frozen/generated cases, correct diagnosis and case reset, keyboard interaction, late diagnosis successes and errors, duplicate submission, and recovery from a failed non-JSON response. A dedicated CI job installs the optional browser dependencies and runs these workflows; the existing Python matrix remains in place. [Testing instructions](TESTING.md) document both suites.

Local verification on Linux with Python 3.12.14: all 264 Python tests and six browser tests passed; all four examples ran from outside the checkout; all ten frozen checksum entries passed; JavaScript syntax and Git whitespace checks passed. Local browser verification used Playwright 1.58.0 with Chromium 153.0.8010.0 from an alternate runtime because standard browser downloads returned invalid archives in this environment. Only the browser launch configuration was adapted locally; the committed application and browser tests ran unchanged. The new standard browser CI job requires its own hosted result before claiming that path is verified.

This pass adds correctness and test coverage. Independently authored incidents, claim-level evidence support, a guided budgeted browser investigation, and actual model evaluation remain planned research/product work. No agent accuracy or calibration results are claimed.

## 2026-10-18 — Authored causal incident suite

Added `inquest-authored-v1`: 16 AI-authored synthetic cases with one medium and one hard design per fault category. Every case has explicit metric keyframes, case-specific logs/events/traces/health, a causal explanation, distractors, two or more reachable supporting clue checks, and counterevidence. Four cases omit root-service logs. Cases were constructed separately from the procedural generator and its signal templates; shared healthy baselines, schema, topology, and fault/fix ontology are reused.

Committed canonical JSONL, complete authoring definitions, a machine-readable casebook, human-readable explanations, manifest provenance, and four SHA-256 entries. The generic renderer uses supplied keyframes and records rather than random sampling or fault-specific dispatch, and refuses nonempty output directories. Source hashes record the construction code even though the freeze was prepared from an uncommitted checkout based on `7054eed`. No prompts, model runs, likelihood fits, or tuning were used during construction.

Added explicit authored scenario identity (`origin=authored`, null seed, holdout split) and manifest-format-2 loading alongside legacy smoke compatibility. The loader verifies casebook/source integrity and binds casebook order and labels to data. All 120 legacy smoke records retain identical serialization. The new example makes two predetermined unscored queries. CI configuration adds authored checksum verification and the fifth example.

Verification on Linux/Python 3.12.14: 303 Python tests and all six Chromium workflow tests passed. Browser verification used the same alternate Chromium 153.0.8010.0 runtime and Playwright 1.58.0 recorded above. All five examples ran outside the checkout; all fourteen checksum entries across both suites passed; whitespace checks passed. New checks cover every authored clue, grading compatibility, tool metadata isolation, strict identities, changed files, casebook binding, generator/template independence, reproducible data bytes, and overwrite protection.

Review status: structural and causal self-review by the same AI author; independent human/domain-expert review is pending. Milestone 14 remains unchecked until its broader review acceptance evidence is complete. The suite is public, fixed-topology, sparse and synthetic; designed difficulty is not empirically calibrated. Tests use evaluator-authored reports and do not establish agent accuracy, claim-level support, or production validity. The next implementation is a minimal recorded agent runner and an actual model pilot, reporting these limitations.

GitHub write access remained unavailable in this session. Changes are delivered as local commits and apply-ready patches; no publication or hosted CI result is claimed.

## 2026-10-18 — Recorded single-agent runner and model adapters

Implemented a provider-neutral single-agent JSON action loop, an explicit non-LLM earliest-alert baseline, Ollama native chat, and compatible chat-completions adapters. The prompt exposes public tool/ontology knowledge only; the evaluator retains cases, IDs, labels and grading. Unknown environment calls remain charged, malformed envelopes consume bounded completion/error allowances, and final report validation failures are retained. No automatic final-report correction, source/filesystem access, paid provider default, or hidden completion cache is introduced.

Added durable per-attempt journals with exact prompts, assistant responses, observations, transport/protocol errors and usage; atomic completed results; POSIX locking; strict configuration/code/data/model checks on resume; and offline replay/summary CLI commands. Interrupted episodes restart in new attempt files while preserving prior attempts and their readable usage. Completed failures are not retried on resume. Summaries retain failure denominators, separate budgets/difficulty, report descriptive Wilson intervals, disclose missing Brier/usage and include prior-attempt accounting. Remote aliases are not claimed to identify immutable weights.

The model adapters were checked against official Ollama/Groq API documentation and real loopback HTTP fixtures. Keys are read from a named environment variable, excluded from artifacts, and not forwarded through redirects. Transport retries are bounded and explicit; raw error bodies and exception details are excluded. Provider availability, billing and actual model inference have not been validated by the fixture tests.

Verification on Linux/Python 3.12.14: all 371 Python tests passed, including 68 new protocol/runner/HTTP/persistence tests. Built a wheel, installed it into a clean isolated environment, and ran its console entrypoint, replay and summary outside the checkout against an explicitly supplied suite. All five examples ran outside the checkout; all fourteen frozen checksums and whitespace checks passed. CI configuration adds an isolated wheel/console check. No web UI files changed in this pass, and no new hosted CI result is claimed.

No conventional model API keys, installed local model, or Ollama server were configured in the execution environment. Actual LLM pilot work therefore remains blocked by the missing backend. The following experiment checkpoint records only the transparent offline heuristic; scripted responses and mock HTTP tests do not count as model runs. Windows runner execution is unsupported because the writer lock uses POSIX flock.

### Recorded offline baseline checkpoint

At clean source revision `e79c21f`, ran the fixed `earliest-alert-v1` heuristic on all 16 authored cases and all 16 smoke test-hard cases at tool budgets 5, 10 and 20: 96 episodes over 32 unique cases. Every episode completed on its first attempt with a structurally/reference-valid report. Authored accepted success was 11/16 at each budget, with evidence-relevant success 10/16. Smoke-hard accepted and evidence-relevant success were 10/16 at each budget. Constant confidence 0.5 produced Brier loss 0.25; this is not a calibration result.

Preserved exact prompts, policy responses, observations, reports, metadata and results in two checksummed run archives under `experiments/offline-baseline-v1`, with matching standalone summaries and an explicit failure analysis. Completed-run resume produced identical summaries with no new attempts. Archives were extracted and inspected using the installed CLI outside the checkout, without credentials or model access.

No model request or paid API call was made. The baseline was implemented after the public datasets were authored and inspected; this is not an untouched holdout assessment or a model comparison. Larger budgets did not fix this policy's selection/interpretation limitations. No policy classification logic was changed after observing these recorded results. Actual LLM evaluation remains pending a configured model backend. GitHub publication remains blocked by the existing write-access limitation; local commits and patches are the deliverable.

## 2026-10-19 — Recorded model runs, frozen policies and fresh cases

Added Gemini-compatible request settings and a private-key launcher with pacing, separate policy/suite output directories, finite episode limits, first-429 pause and strict resume. Added offline paired comparison with compatibility checks and explicit gains, regressions, missingness, errors and usage. V1 and V2 prompts retain their historical byte identities.

Prepared authored-v2 as a separate sixteen-case suite after freezing V2: balanced fault/difficulty coverage, four missing-root-log cases, checksummed source/data/casebook/manifest and five-call support/counterevidence paths. Preserved the old canonical data and grader. The evidence coverage review documents why useful health observations may receive no credit under older metadata. The new suite remains single-author synthetic work, not an independently validated holdout.

The maintainer executed hosted Gemini runs and supplied private archives for offline review. Recorded references include V1/V2 on authored-v1 and V2/V3 on authored-v2. Saved request histories, observations, reports and grades were checked through offline replay. Detailed outcomes remain in maintainer-controlled archives. The current [progress page](PROGRESS.md) records implementation status, the evaluation workflow and caveats without publishing private-run aggregates or transcripts.

V3 adds guidance for demand checks, caller evidence, specific mechanisms and contradictions while preserving parser, tool budget, runner loop, grader and frozen inputs. Local verification passed 453 Python tests; all eighteen canonical dataset checksums and whitespace checks passed. Historical V1/V2 replay remained consistent. Prior published CI checkpoints passed Python 3.10–3.14 and Chromium; the current V3 remote CI result was not rechecked during this review.

Keep V2 as the working evaluation baseline and V3 as an experimental candidate while preserving all paired outcomes. Provider failures, malformed actions and incorrect diagnoses must be distinguished. The summary invalid-report count can include an absent report after a backend failure, so it must not automatically be described as malformed submitted reports. Preserve the full case denominator and disclose unavailable usage/confidence. Public single-author development cases do not support production-generalization claims.

The next priority is a usable browser investigation viewer and connection to local execution, with evidence citations, errors, replay and comparison. Independent review, claim-level evidence and calibrated reasoning remain incomplete research milestones. Further prompt-only model runs are not required to start this product work.

The maintainer now handles GitHub commits, pushes, PR updates and merges from VS Code. This progress consolidation is prepared locally as reviewable files/patches; no GitHub mutation is performed during this review.

## 2026-10-19 — Private saved-run viewer

Prepared the `/runs` browser interface for maintainer application through VS Code. It opens existing run folders or incremental file selections entirely in the browser, displays manifest-wide completion counts, exact-attempt observations, clickable citations, diagnoses, validation/correctness checks, usage, provider/protocol/transport errors and unfinished episodes. It also displays saved paired-comparison JSON, retaining its limitations and keeping compatibility validation in the CLI.

The viewer uses local assets and system fonts, no browser storage and a network-blocking Content Security Policy. It renders imported values as text, bounds imports, rejects mismatched identities, labels journal gaps, and does not substitute previous attempts for missing current journals. It does not authenticate files or rerun grades. No new runtime dependency, model request, policy/grader/dataset change, or GitHub mutation was made.

Verification passed 454 Python tests and 12 Chromium workflows locally on Linux/Python 3.12 using Playwright 1.55. Invented test files cover failures, partial runs, escaped text, exact attempts, malformed imports, keyboard citations, mobile layout, comparison display and clear/import races. Desktop/mobile renders were inspected; all 64 episodes across four private maintainer folders opened without post-load network traffic. Their contents and performance aggregates remain outside this code patch. Local execution controls and interactive validated pairing of two folders remain later work. See [Saved runs](SAVED_RUNS.md).

## 2026-10-20 — Durable local browser execution

Prepared an opt-in loopback application that launches one selected authored case through the existing runner using only the offline heuristic. A single worker, SQLite transactions, a lifetime store lock, idempotent start keys and bounded jobs coordinate execution. Browser controls show tool calls and budgets, cancellation, explicit resume and direct saved-run review. Restart marks incomplete/queued work interrupted; completed artifacts are reused instead of executed again. Earlier journals remain intact. Empty unstarted header directories are preserved before recovery; inconsistent saved data is rejected.

Extended `run_experiment` with optional explicit case selection and a detached event hook after durable journal writes. Existing CLI defaults and the episode loop, prompts, tools, grader and frozen bytes are preserved. The worker source hash is recorded in backend identity for strict resume. No model request or new runtime dependency was introduced. The normal hosted app starts no worker and exposes no execution API. Local routes enforce loopback/Host/Origin/token checks, input bounds, cache isolation and escaped inert saved-file handoff.

Verification passed 473 Python tests and 17 Chromium workflows locally on Linux/Python 3.12 with Playwright 1.55. Coverage includes concurrent deduplication, queue ownership, cancellation, preserved attempts, recovery after artifact completion, source mismatch, shutdown boundaries, partial headers, HTTP restrictions, lost responses, browser reload/restart, error display, citation handoff and mobile layout. The actual startup command completed a browser-created job, retained it after restart, and opened the saved viewer without external requests. These are lifecycle/software checks, not LLM performance results. See [Local execution](LOCAL_EXECUTION.md).

The maintainer alone handles commits, pushes, PR creation and merging through VS Code. This change is delivered as an incremental patch against the merged saved-run viewer; no GitHub write is performed by the assistant. Browser model integration, claim-level support, independent review, topology variation and a reproducible release remain later work.

## 2026-10-25 — Benchmark card

Added [the benchmark card](BENCHMARK_CARD.md) covering intended use, frozen suites, evaluation boundaries, grading metrics and missingness, V2 baseline versus the V1 CLI default, reproducible comparisons, and limitations. Linked it from the README and updated progress/roadmap status; changelog and versioned release remain pending.

Verification: dataset counts and provenance checked against manifests and suite guides, metrics against grader/runner source, and policy/heuristic distinctions against source. Relative links and whitespace checked. No runtime code or model results changed; runtime tests were not rerun.

## Reading the dated entries

Entries use the date on which work occurred. Multiple changes on one day appear together. Each entry identifies the affected milestone, origin of integrated components, verification evidence, limitations, and next planned capability.
