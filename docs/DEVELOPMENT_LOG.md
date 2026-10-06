# Development log

This repository starts from an existing local Inquest prototype. This log records integration, improvements, verification, and remaining limitations. The initial repository setup and first code milestone were completed on 6 October 2026; there is no multi-day development history yet.

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

Next milestone: budgeted investigation tools with observation validation and checks for answer leakage.

## How to read this log

Entries use the date on which work occurred. Multiple changes on one day appear together. Each entry identifies the affected milestone, origin of integrated components, verification evidence, limitations, and next planned capability.
