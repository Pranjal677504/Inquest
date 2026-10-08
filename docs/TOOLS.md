# Investigation tools

`InvestigationEnv` provides eight read-only tools over a frozen incident. The evaluator loads and selects the full bundle; investigators receive tool specifications and observations. No network access, model, or API credentials are needed.

## Quickstart

After installing from the checkout:

```bash
python examples/inspect_incident.py
```

This is a scripted manual walkthrough of a database incident, not an autonomous agent or a scored benchmark run. It makes five predetermined queries and prints their observations. Evaluator-side report grading is available in the [grading guide](GRADING.md). Autonomous investigation policies remain planned.

Python usage on the evaluator side:

```python
from inquest.env import InvestigationEnv
from inquest.frozen import load_frozen_set

case = load_frozen_set("datasets/smoke-v1", "test-easy")[7]
env = InvestigationEnv(case, max_steps=20, max_lines=20)
observation = env.call("get_alerts")
print(observation.id, observation.text)
```

## Call and observation contract

`env.call(tool_name, **arguments)` consumes one step and returns an `Observation` with:

| Field | Meaning |
|---|---|
| `id` | Sequential observation ID, starting at `o1` |
| `tool` | Requested tool name |
| `args` | A detached copy of the supplied arguments |
| `text` | Readable telemetry or an argument error |
| `data` | Structured telemetry; empty for invalid requests |
| `error` | `None`, `unknown_tool`, or `invalid_arguments` |

Every attempted call is charged, including unknown tools, missing arguments, unsupported fields, and invalid filters. There is no free-call option. Once the budget is exhausted, `BudgetExceeded` is raised before dispatch; no extra observation or step is added. A zero-step budget is permitted. Budgets must be non-negative integers; `max_lines` must be a positive integer. Boolean values are not accepted as numeric settings.

`env.steps`, `env.steps_left`, and `env.max_steps` expose accounting. `env.obs` returns detached transcript records in call order, so editing a returned observation does not change telemetry or the saved transcript. `tokens_used()` estimates **observation text** tokens as roughly one token per four characters; it does not measure model usage, prompts, or tool-call arguments.

## Available tools

| Tool | Arguments | Observation |
|---|---|---|
| `list_services` | None | Service names and caller-to-dependency edges |
| `get_alerts` | None | Currently firing error/latency alerts and first sustained threshold crossings derived from metrics |
| `query_metric` | `service`, `metric` | Fifteen-minute means, baseline and recent means, ratio, and derived sustained deviation time |
| `search_logs` | `service`; optional `query`, `level`, `limit` | Recent matching log lines and total matches |
| `get_events` | Optional `service` | Most recent change-event summaries, newest first |
| `get_event` | `event_id` | Summary and full detail of one selected event |
| `health_check` | `service` | Status, version, recent restarts, and certificate lifetime |
| `get_trace` | Optional `status` | Next matching trace in stored order within the last 40 minutes |

All services have `rps`, `error_rate`, `latency_p99`, `cpu`, and `memory` metrics. PostgreSQL additionally has `lock_wait_ms` and `conn_used`; cache has `hit_rate`.

### Derived alerts and metric summaries

The baseline is minutes 0–39. Error alerts use a 2% threshold; latency alerts use twice the median baseline. A first sustained crossing requires three complete consecutive samples starting at minute 40 or later, and an alert is shown only if its threshold still holds at the latest sample. Alert crossing time is calculated from telemetry, not taken from the incident's labeled onset.

Metric summaries compare the baseline with the last ten samples. A change point is the first three-sample sustained deviation greater than the maximum of four baseline standard deviations, 15% of the baseline mean, and a small positive floor. These are authored heuristics; they do not establish causal onset or statistical significance.

### Log filters and record limits

`query` is a case-insensitive **literal substring**, with an empty string matching all messages. Regular expressions are not executed. `level` is the minimum severity (`INFO`, `WARN`, or `ERROR`, case-insensitive). Unknown levels and non-positive/non-integer limits return charged argument errors.

Log output contains the latest matching records, in chronological order, capped by both `limit` (default 12) and `max_lines`. Event lists are capped by `max_lines` and omit details; a separate `get_event` call retrieves those details. The setting limits returned records for these tools, not every text line or total tokens. Other tools have outputs bounded by the fixed graph and telemetry representation.

### Trace replay

Traces are selected from minutes 80–119, a fixed window shared by all cases. `error` and `timeout` match traces containing at least one span with that status; `ok` requires all spans to be healthy. Repeated successful queries cycle deterministically through matching traces in their stored order. No matching trace returns `{"trace": null}`. Invalid requests do not advance a trace cursor.

This differs from the prototype's use of the true incident onset. The fixed window avoids selecting observations using hidden labels while preserving replay from the frozen file.

## Observation boundary and limits

The environment copies only permitted telemetry fields. It does not retain the input `Scenario` or consult its root service, fault, fix, seed, ID, split, difficulty, labeled onset, or gold metadata. Event IDs remain visible so event details can be queried. Observation IDs refer to tool calls; neither is the construction scenario ID.

Logs and event details can provide strong diagnostic clues, such as a migration or expired certificate. Those clues are intentional telemetry. Filtering metadata does not guarantee that arbitrary externally supplied telemetry contains no answer-like text. The published suite was checked for the prototype's explicit root-cause trace label.

This is an observation-level boundary, **not a sandbox against Python reflection, private-attribute changes, source inspection, or reading public dataset files**. A future harness must keep construction bundles on the evaluator side and give agents only tool calls and observations. Public frozen fixtures cannot establish resistance to malicious agents or dataset memorization.

## Verification

Tests exercise all eight tools across all 120 published incidents. Additional checks cover charged invalid calls, exhausted/zero budgets, record limits, literal filters, full three-sample alert windows, deterministic trace cycling after JSON reload, detached observations, and independence from construction labels and extra metadata fields. The full suite currently passes 243 tests on Python 3.14. Other Python versions remain unverified.
