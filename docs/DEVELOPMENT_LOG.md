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

## Entry format

For each completed development session, record the actual local date, milestone, origin of reused code, behavior added or fixed, verification command and outcome, limitations, and next step. A skipped or blocked run does not become a completed milestone.
