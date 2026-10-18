# Reproducible investigation runner

The runner executes one JSON action at a time against the existing budgeted environment. It supports a transparent offline heuristic, a local Ollama model, and a hosted/local compatible chat-completions endpoint. Model backends receive public chat messages and observations only. The evaluator retains cases, labels, grading, IDs, and provenance.

**Status:** the runner and provider contracts are tested. The included recorded experiment is an offline heuristic baseline. No actual LLM pilot has been run in this environment because no model API key, installed model, or model server was available. Mock HTTP responses and scripted test replies are software tests, not model experiments.

## Install and run without credentials

```bash
python -m pip install -e ".[dev]"
python -m inquest run \
  --suite datasets/authored-v1 --set holdout \
  --backend heuristic --budgets 5,10,20 \
  --output runs/authored-heuristic-v1
```

An installed `inquest` command provides the same interface. The CLI code works from a wheel outside the source checkout; the frozen dataset directory is supplied separately. No new runtime dependency is required by the runner.

Commit implementation changes before an evaluation. `--allow-dirty` explicitly permits development checks and records the dirty state. It does not turn such a check into a published model result. If Git metadata is unavailable, the manifest records null revision/dirty values and retains package source hashes.

Use `--case-limit 1 --budgets 5` for an initial interface check. This selects the first case, not a random or balanced sample. Omit the limit for the full set. Use a new output directory for each configuration.

## Local Ollama

Start your own Ollama server and install a suitable instruction-following model. Use its exact installed tag from the model list; the runner never downloads a model.

```bash
python -m inquest run \
  --suite datasets/authored-v1 --set holdout \
  --backend ollama --model YOUR_INSTALLED_TAG \
  --base-url http://127.0.0.1:11434 --json-mode \
  --budgets 5 --case-limit 1 --output runs/ollama-first-case
```

Preflight reads `/api/tags` and records the selected model digest. Chat requests use `/api/chat` with `stream=false`, explicit temperature and output limit. Keep the tag pinned on the server during a run; a digest lookup does not lock a concurrently modified server. Provider/model availability and actual execution remain to be verified with a real installed model.

## Hosted compatible endpoint

Set the chosen API key as an environment variable in your shell or secret manager. The runner reads that variable; it does not accept a key on the command line or write it into artifacts. No `.env` file is loaded automatically.

For a Groq-compatible endpoint:

```bash
python -m inquest run \
  --suite datasets/authored-v1 --set holdout \
  --backend compatible --base-url https://api.groq.com/openai/v1 \
  --api-key-env GROQ_API_KEY --model YOUR_AVAILABLE_MODEL_ID \
  --budgets 5 --case-limit 1 --output runs/hosted-first-case
```

The adapter sends non-streaming `/chat/completions` requests with `max_completion_tokens`. Optional `--json-mode` requests `response_format={"type":"json_object"}`; enable it only for a model/server that supports it. Compatibility here means this explicit request/response contract, not every provider or optional API feature. Ollama and compatible adapters have real loopback HTTP contract tests; those tests do not validate a live commercial service.

Record an exact provider revision with `--model-revision` when one is available. Returned model names, response IDs and system fingerprints are stored per response. A provider alias may change behind an unchanged name; declared revisions are user-supplied metadata, not proof of immutable remote weights. Temperature zero is not a determinism guarantee.

## Action and budget contract

Each completion must contain exactly one JSON object, without fences or prose:

```json
{"kind":"tool","tool":"search_logs","args":{"service":"auth","limit":12}}
```

or:

```json
{"kind":"report","report":{"service":"auth","fault_type":"config_regression","fix":{"action":"revert_config","target":"auth"},"evidence":["o1"],"confidence":0.6}}
```

The second object is a schema example, not an agent result. The system prompt supplies the same service/fault ontology and recovery mapping to all policies. Telemetry is treated as evidence, not instructions. Only the existing eight read-only investigation tools are executable; there is no filesystem, network, shell, grading or answer-reveal tool.

- Every attempted environment call costs a step, including unknown names and invalid arguments.
- Malformed envelopes do not execute a tool. They consume a model turn and a bounded protocol-error allowance, both recorded.
- At zero tool steps the model can submit a final report. Another tool request ends the episode as a budget failure.
- Final report content goes directly to the grader. Missing/invalid confidence, unknown citations and malformed fields are not silently repaired.
- Defaults: 32 completion turns, two malformed-envelope errors, 100,000 prompt characters, 20 returned log/event records, and 768 maximum output tokens per completion.
- `--max-model-turns`, `--max-protocol-errors`, `--max-prompt-chars`, `--max-output-tokens`, `--temperature`, `--timeout` and `--retries` are explicit run configuration. These are finite per-call/per-episode controls, not a monetary spending limit.

The public Python observation boundary is not a sandbox against hostile code or direct access to public datasets. Keep the trusted evaluator and source files outside any untrusted agent process. Shared in-process custom Python backends are trusted implementation code.

## Saved artifacts and interruption behavior

Each run contains:

| Path | Contents |
|---|---|
| `run.json` | Protocol/settings, complete backend identity, code hashes/revision, prompt hash, suite/data/catalog hashes, ordered case selection, and planned jobs |
| `episodes/<job-id>/attempt-001.jsonl` | Exact request messages, returned assistant content/metadata/usage, transport attempts, protocol errors, observations, report, terminal score |
| `episodes/<job-id>/result.json` | Atomically replaced evaluator-side result for a completed episode |
| `summary.json` | Aggregates by tool budget and designed difficulty |

Journals flush and fsync each event. Results and summaries use write-then-replace. A POSIX file lock prevents concurrent writers and releases on process exit. Linux and macOS locking are supported; Windows runner execution is unsupported. This addresses process interruptions, not a guarantee against every filesystem or power-loss mode.

```bash
# Same run settings and output, with --resume added:
python -m inquest run \
  --suite datasets/authored-v1 --set holdout \
  --backend heuristic --budgets 5,10,20 \
  --output runs/authored-heuristic-v1 --resume
```

Resume requires matching code, prompt, data, model identity, case selection and settings. Completed failures are retained and skipped, not retried until they pass. An unfinished episode restarts with a fresh budget and chat in a new attempt file; previous attempts remain intact. All readable model usage from all attempts is included in summaries. Truncated abandoned journal lines are counted. A fresh attempt is a restart, not continuation of an in-flight model request.

HTTP retries are bounded and logged for 429, selected 5xx responses, and network errors. Authentication/validation failures and redirects are not retried. Network failures may have been processed by a provider, so actual billing can exceed known token totals. Error bodies and authorization headers are not recorded. The runner does not cache or silently replay previous completions.

## Summaries and replay

```bash
python -m inquest summarize --run-dir runs/authored-heuristic-v1
python -m inquest replay --run-dir runs/authored-heuristic-v1 \
  --job-id case-0001-budget-005
```

These commands require no model, credentials, source cases or network. Replay prints the latest attempt, including exact prompts and observations. `--attempt 1` selects an earlier attempt. It reads recorded results; it does not fabricate a fresh model response or regrade a changed dataset.

All completed failures remain in success denominators. A group with unfinished episodes has `success_rate=null` and no final interval, with planned/completed/unfinished counts. Different budgets are reported separately; the summary does not pool the same cases across budgets into an inflated sample size. Wilson 95% intervals describe proportions in these synthetic cases, not production generalization or independent samples from a real deployment population.

Summaries separate accepted success, evidence-relevant success, invalid reports, outcome status, tool steps, latency, and available Brier values. Missing Brier counts are explicit. Known input/output token totals, missing-usage calls and failed transport attempts are reported separately across all attempts. No unavailable usage is imputed as zero, and no dollar cost is inferred. Current Brier targets accepted success; evidence relevance is coarse and does not prove claim support.

## Offline policy and interpretation

`earliest-alert-v1` is a deterministic, non-LLM baseline. It chooses services by earliest firing alert, probes health/logs/changes/request volume/memory, and uses a fixed transparent precedence rule to name a fault. Confidence is always 0.5 and is not calibrated. It can mistake a caller symptom for the initiating service, particularly when a target rejects TLS or has no firing alert. The complete policy is in `src/inquest/backends.py`.

This policy was implemented after the public suites were authored and inspected. Its results are a transparent engineering baseline, not an untouched holdout assessment, evidence of model reasoning, or a tuning-free research comparison. Future agent comparisons must record policy/prompt changes, model identities, failed runs and any use of these public cases during development.

## API references

Adapter shapes were checked against the official [Ollama chat API](https://docs.ollama.com/api/chat), [Ollama model list](https://docs.ollama.com/api/tags), [Groq compatibility guide](https://console.groq.com/docs/openai), and [Groq chat API reference](https://console.groq.com/docs/api-reference#chat-create). Actual model availability must be checked in the configured service.
