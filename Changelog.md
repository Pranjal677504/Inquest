# Changelog

This changelog records notable changes to InquestBench.
Unreleased entries describe work merged into main.
Dated verification records identify the specific revision tested.

## [Unreleased]

### Added

- Browser workbench for investigating synthetic microservice incidents.
- Frozen smoke-v1, authored-v1, and authored-v2 incident suites with
  manifests, provenance records, and checksum verification.
- Budgeted investigation tools and structured diagnosis grading.
- Recorded single-agent runner with offline heuristic, Ollama, and
  compatible chat-completions backends.
- Versioned investigation policies, durable run artifacts, resume,
  replay, summaries, and paired comparisons.
- Saved-run viewer for observations, citations, reports, errors,
  and exported comparison artifacts.
- Public sample investigations that run without model credentials.
- Opt-in local browser execution using the offline heuristic,
  durable job storage, cancellation, and restart recovery.
- Benchmark card documenting intended use, datasets, metrics,
  evaluation boundaries, reproducibility, and limitations.
- Release checklist and a dated fresh-checkout verification record.

### Changed

- Updated project documentation to reflect merged local execution
  and current release priorities.
- Clarified V2 as the working evaluation baseline while retaining
  V1 as the CLI default for compatibility. Baseline model runs
  must explicitly select `--policy v2`.
- Updated the CI checkout action.

### Evaluation notes

- V3 remains experimental. Both authored suites informed its
  development and are development data for that policy.
- Authored cases are public, AI-authored, and single-author reviewed.
  Independent domain-expert validation remains pending.
- Evidence relevance measures coarse tool/service relevance,
  not claim-level causal support.
- Offline heuristic results and software tests do not establish
  autonomous model accuracy or production readiness.

### Verification

- The 2026-10-25 walkthrough verified candidate `6eaa023` with
  473 Python tests, 18 Chromium tests, frozen-data checksums,
  and documented local and hosted product checks.
- These results apply to the recorded candidate and environment.

See [the verification record](docs/releases/2026-10-25/README.md)
and [benchmark card](docs/BENCHMARK_CARD.md) for scope and limitations.