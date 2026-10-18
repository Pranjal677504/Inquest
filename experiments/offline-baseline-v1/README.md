# Offline baseline v1 — recorded engineering checkpoint

**This experiment uses a deterministic non-LLM heuristic. It is not an LLM result or evidence of autonomous model reasoning.** No model API key or local model/server was configured for this session.

## Protocol and provenance

- Policy: `earliest-alert-v1`, implemented after the public cases were authored and inspected. No accuracy-driven modifications were made after these recorded runs.
- Data: all 16 `authored-v1/holdout` cases and all 16 `smoke-v1/test-hard` cases.
- Tool budgets: 5, 10 and 20; completion-turn limit 32; fixed policy confidence 0.5; same public ontology and recovery mapping as the model prompt.
- Total: 96 episodes across 32 distinct public synthetic cases. Repeated budgets do not create 96 independent incidents.
- Every episode completed on its first attempt; all reports passed structural/reference validation. Resuming the two complete runs produced identical summaries without new attempts.
- Runtime: Linux/Python 3.12.14. Source revision: `e79c21ffdff0a1369b8baeda0cf855de32cdc574`, with a clean working tree when each run started. Per-run manifests retain source hashes, data/catalog/manifest checksums, prompt hash, exact settings, and case order.
- Zero model requests, zero paid API calls, and no model token measurements. Local latency includes policy, environment and durable-recording overhead and is not an inference-speed benchmark.

## Results

Accepted success requires a valid report plus correct service, fault and fix. Evidence-relevant success additionally requires at least one coarse tool/service-relevant citation.

| Suite | Tool budget | Accepted success | Evidence-relevant success | Invalid reports | Mean tool calls | Descriptive Wilson 95% interval for success |
|---|---:|---:|---:|---:|---:|---|
| authored | 5 | 11/16 | 10/16 | 0 | 5.00 | 0.444–0.858 |
| authored | 10 | 11/16 | 10/16 | 0 | 9.50 | 0.444–0.858 |
| authored | 20 | 11/16 | 10/16 | 0 | 14.50 | 0.444–0.858 |
| smoke-hard | 5 | 10/16 | 10/16 | 0 | 5.00 | 0.386–0.815 |
| smoke-hard | 10 | 10/16 | 10/16 | 0 | 9.50 | 0.386–0.815 |
| smoke-hard | 20 | 10/16 | 10/16 | 0 | 13.25 | 0.386–0.815 |

Intervals describe these small case proportions and do not establish production generalization. All 96 confidence values are the policy's constant 0.5, giving Brier loss 0.25; this does not demonstrate calibration. No outcome is omitted from a completed-run denominator.

## Failures at budget 20

The same accepted-success counts occurred at every budget. This fixed policy keeps the earliest-alert service as its diagnosis target and uses only a limited set of fault indicators; spending additional calls on other services did not correct those assumptions.

| Suite | Case | Submitted service / fault | Labeled fault |
|---|---|---|---|
| authored | `authored-v1-003` | `orders` / `bad_deploy` | `cert_expiry` |
| authored | `authored-v1-004` | `payments` / `bad_deploy` | `feature_flag` |
| authored | `authored-v1-008` | `postgres` / `bad_deploy` | `dependency_outage` |
| authored | `authored-v1-011` | `gateway` / `bad_deploy` | `cert_expiry` |
| authored | `authored-v1-012` | `gateway` / `bad_deploy` | `config_regression` |
| smoke-hard | `test-hard-2` | `auth` / `bad_deploy` | `resource_leak` |
| smoke-hard | `test-hard-4` | `gateway` / `bad_deploy` | `cert_expiry` |
| smoke-hard | `test-hard-7` | `postgres` / `bad_deploy` | `bad_migration` |
| smoke-hard | `test-hard-10` | `gateway` / `feature_flag` | `resource_leak` |
| smoke-hard | `test-hard-12` | `gateway` / `bad_deploy` | `cert_expiry` |
| smoke-hard | `test-hard-15` | `postgres` / `bad_deploy` | `bad_migration` |

Representative causes of failure:

- `authored-v1-003` and `authored-v1-011`: the expired listener prevents target requests, so a caller fires the visible alert. The policy selects the caller and never identifies the target certificate.
- `authored-v1-004`: a remotely controlled flag is absent from the change-event list. The policy's change-event-based flag check misses the wait described in logs/traces.
- `authored-v1-008`: the database process is degraded rather than down; the policy fails to interpret the fenced writer endpoint as dependency unavailability.
- `authored-v1-012`: the configuration sync is absent from the recorded change list. Ingress logs explain it, but the policy lacks semantic log interpretation for this fault.
- One authored accepted diagnosis lacks a coarse relevant citation. Correct labels alone do not establish a well-supported investigation.

The policy is intentionally transparent and has known access/interpretation limits. These failures motivate a real model comparison; they do not show that a model would perform better. The authored suite also awaits independent domain-expert review. Later tuning on these public cases must be disclosed.

## Reproduce or inspect

Reproduce a new policy run from the recorded source content and frozen bytes:

```bash
python -m inquest run --suite datasets/authored-v1 --set holdout \
  --backend heuristic --budgets 5,10,20 --output runs/reproduce-authored
python -m inquest run --suite datasets/smoke-v1 --set test-hard \
  --backend heuristic --budgets 5,10,20 --output runs/reproduce-smoke-hard
```

To inspect the exact recorded histories without a provider or credentials, verify `SHA256SUMS` in this directory, extract an archive into a new review directory, then summarize/replay it:

```bash
mkdir /tmp/inquest-baseline-review
tar -xzf experiments/offline-baseline-v1/authored-run.tar.gz -C /tmp/inquest-baseline-review
python -m inquest summarize --run-dir /tmp/inquest-baseline-review/authored
python -m inquest replay --run-dir /tmp/inquest-baseline-review/authored \
  --job-id case-0001-budget-005
```

Each archive includes exact request messages, policy responses, tool observations, complete reports, results and the run manifest. The adjacent summary JSON files match the copies in the archives. No fixture responses were substituted for recorded policy decisions. The experiment archives are preserved inputs; use a new directory when rerunning.

A real model pilot remains the next experiment. Choose a configured Ollama or compatible provider using [the runner guide](../../docs/RUNNER.md), start with one case, and retain its actual errors and usage. No model identity or performance has been invented for this checkpoint.
