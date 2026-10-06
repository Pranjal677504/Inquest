# Development log

This repository starts from an existing local Inquest prototype. The history records its gradual integration, verification, and subsequent improvements. Development may use Codex assistance; individual entries record the work and evidence rather than making claims of unaided authorship.

## 2026-10-06 — Repository foundation

Established the repository scope, milestone acceptance criteria, license, and development log. The initial repository contains documentation and repository hygiene files. Prototype code and previously generated result tables will be integrated in later verified milestones.

Verification: checked all local Markdown links and reviewed the initial file list to exclude credentials, generated caches, and prior run artifacts. No software tests apply to this documentation-only milestone.

Next milestone: integrate deterministic incident bundles and their tests.

## 2026-10-06 — README technical expansion

Expanded the foundation README at the maintainer's request. It now explains the investigation problem, architecture, Bayesian reasoning, initial service graph, incident categories, tools, agent comparisons, evaluation contract, reproduction requirements, and validity limits. Details are grounded in the existing local prototype and marked as intended integration where they are not yet present in this branch. The roadmap remains at the foundation milestone.

Verification: checked documentation links, Mermaid source, the illustrative JSON report, and the documented topology and tool names against the prototype. Runnable setup and measured results remain pending their implementation milestones.

GitHub preview exposed a Markdown conflict in the display equations and an unsupported math macro. Changed them to fenced-math format with supported notation and checked the published presentation.

## 2026-10-06 — Deterministic incident bundles

Integrated milestone 02 at the maintainer's request for working source code. The topology and generator originate from the existing local Inquest prototype (`src/inquest/topology.py` and `src/inquest/scenario.py`); this is verified integration with improvements, not a claim of a newly authored simulator.

Added generation and seed-range validation, explicit unknown-service errors, JSON bundle checks, a public Python API, basic package configuration, and a runnable construction/replay example. Replaced the prototype's trace note `root span failing` with ordinary request-failure wording so telemetry no longer explicitly labels the answer. Construction bundles still deliberately contain labels and must not be passed directly to agents.

Verification on Python 3.14: installed `python -m pip install -e ".[dev]"` into a fresh isolated environment; `python -m pytest -q` passed 117 tests. Tests cover all eight faults across every difficulty/split combination, serialization round trips, deterministic generation, global random-state isolation, malformed inputs, shortest-path queries, database lock propagation, and traffic propagation to dependencies. Ran `python examples/generate_incident.py`; the example produced eight services, 120 telemetry minutes, two events, 60 traces, and an identical JSON round trip. Compared the same hard OOD bundle in separate processes with two Python hash seeds from outside the checkout; fingerprints matched. Checked local documentation links and `git diff --check`.

Limitations: installation and tests are locally verified on Python 3.14 only; the declared Python 3.10+ range will receive a CI matrix in milestone 09. Cross-version seed fingerprints are not guaranteed. Tools, agents, grading, end-to-end investigations, and benchmark results remain pending. Basic packaging is present to make this milestone runnable; the full CLI, wheel checks, and CI acceptance gate remain open.

Next milestone: integrate budgeted investigation tools and review their observations for answer leakage. Resume the existing daily cadence from the next development session.

## Entry format

For each completed development session, record the actual local date, milestone, origin of reused code, behavior added or fixed, verification command and outcome, limitations, and next step. A skipped or blocked run does not become a completed milestone.
