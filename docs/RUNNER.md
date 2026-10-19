# Reproducible investigation runner

The runner executes one JSON action at a time against the existing budgeted environment. It supports a transparent offline heuristic, a local Ollama model, and a hosted/local compatible chat-completions endpoint. Model backends receive public chat messages and observations only. The evaluator retains cases, labels, grading, IDs, and provenance.

**Status:** the runner and provider contracts are tested. The included experiments contain an offline heuristic baseline and a historical Gemini v1 summary/aggregate audit; raw Gemini transcripts remain private. See `experiments/gemini-authored-budget5-v1/README.md`. Maintainer-executed authored-v2 V2/V3 runs have been reviewed offline; the review workflow, implementation status and limitations appear in [Project progress](PROGRESS.md). Detailed outcomes remain in maintainer-controlled run archives. V2 remains the working evaluation baseline. Mock HTTP responses and scripted test replies are software tests, not model experiments.

Policy v3 is available as an opt-in development candidate. Its guidance, limitations, and exact V2/V3 comparison workflow are documented in [Policy V3](POLICY_V3.md). Neither authored suite is independent assessment data for V3.

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

### Gemini compatibility

Google rejected `gemini-2.5-flash-lite` for a new user with HTTP 404 and recommended `gemini-3.5-flash-lite`. The Gemini 3.5 migration guide requires omitting deprecated sampling parameters. Select the compatible endpoint, omit temperature, and explicitly select its output-limit field:

```bash
python -m inquest run \
  --suite datasets/authored-v1 --set holdout \
  --backend compatible \
  --base-url https://generativelanguage.googleapis.com/v1beta/openai \
  --api-key-env GEMINI_API_KEY --model gemini-3.5-flash-lite \
  --omit-temperature --token-limit-param max_tokens --json-mode \
  --max-output-tokens 2048 --max-model-turns 8 \
  --budgets 5 --case-limit 1 --output runs/gemini-3-5-first-test
```

Set `GEMINI_API_KEY` in the same shell first. The runner does not load `.env` automatically. Model availability, free-tier eligibility, and quotas are account-specific. The supplied single-case pilot used this configuration on clean source revision `d2c3c6e6c7acac934451ab2eaed3a75aa832c1f4`, completed in 8.46 seconds, and reported 6,754 input / 149 output tokens. This is an initial integration check, not a full-suite result or evidence of calibrated confidence. See Google's [compatibility guide](https://ai.google.dev/gemini-api/docs/openai) and [migration guide](https://ai.google.dev/gemini-api/docs/generate-content/whats-new-gemini-3.6).

`--omit-temperature` records a null temperature and sends no temperature field. `--token-limit-param` defaults to `max_completion_tokens`; choose `max_tokens` only for compatible endpoints that require it. These settings are included in the run fingerprint. Existing Groq and Ollama request defaults are preserved. Use a new output directory after changing code, model, or request settings; `--resume` preserves completed failures rather than retrying them.

### Full 16-case evaluation with a private key prompt

After installing the package in editable mode and pulling the latest committed branch, run:

```bash
python scripts/run_gemini_eval.py
```

Paste the key only when the hidden prompt appears. The launcher keeps it in the current process environment, never in command arguments or a file. It runs all 16 authored cases at budget 5 with the same protocol and generation limits as the pilot, adds a 15-second minimum interval between HTTP attempt starts, and prints each completed episode to stderr. Allow approximately 20–35 minutes; interrupted or failed episodes remain recorded. A larger workload can still exceed account-specific token or daily limits. Pacing is not a quota guarantee.

Results go to `runs/gemini-3-5-authored-budget5-v1`. To resume after interruption, without changing code or settings:

```bash
python scripts/run_gemini_eval.py --resume
```

Completed failures are skipped on resume, not retried. To share results:

```bash
tar -czf runs/gemini-3-5-authored-budget5-v1.tar.gz -C runs gemini-3-5-authored-budget5-v1
```

The general CLI options `--request-interval 15 --progress` work with other HTTP models too. Pacing covers retries and successive episodes within the same backend instance; separate processes do not share a limiter. It is recorded in the fingerprint and as `transport_wait` journal events. Episode latency includes pacing waits, so it cannot be directly compared with the unpaced pilot as inference latency. The default interval remains zero.

### Free-tier-only policy comparison

Use a Gemini project whose Free tier status you have verified. The launcher does not enable billing, provision infrastructure, change providers, or fall back to a paid model. An API key alone does not establish account billing status; these controls cannot make usage on a paid project free.

Pull and install the committed source, then run only the v2 candidate:

```bash
python scripts/run_gemini_eval.py --policy v2
```

The private key prompt, model, budget 5, maximum 8 model turns, output limit, JSON mode, and 15-second pacing match the reference setup. The new output is `runs/gemini-3-5-authored-budget5-policy-v2`; the existing v1 directory is not overwritten. Both policies remain selectable with `--policy v1` or `--policy v2` on the general CLI. The v1 system prompt remains byte-identical. V2 is an experiment in guidance, not a hard guarantee that a model checks counterevidence or produces valid actions. The same strict parser and grader apply to both. Provider JSON mode is unchanged to keep the experiment focused on policy instructions; no unverified provider JSON-schema feature is silently enabled.

The launcher now enables `--pause-on-rate-limit`. The first HTTP 429 pauses the entire run, writes a partial summary, and leaves the current episode unfinished instead of manufacturing a completed failure. Exit code 3 means paused. Once account quota recovers, resume without changing code or settings:

```bash
python scripts/run_gemini_eval.py --policy v2 --resume
```

An unfinished episode starts a new attempt with its original tool budget. The old attempt and all recorded usage remain included. Completed failures stay completed and are skipped. The general backend default retains bounded 429 retries unless this pause option is explicitly selected. No request runs outside the finite turn/retry limits; these are execution bounds, not a monetary spending limit or a guarantee of free quota.

When both runs are complete, compare locally without an API key:

```bash
python -m inquest compare \
  --baseline runs/gemini-3-5-authored-budget5-v1 \
  --candidate runs/gemini-3-5-authored-budget5-policy-v2
```

Comparison requires identical cases, dataset hashes, protocol, budgets, episode limits, scoring-source hashes, model, and generation settings, with clean recorded source. It reports gains and regressions per case and difficulty, Brier values/missingness, and provider-reported usage. Operational differences such as the new quota-pause option are disclosed. It refuses incomplete runs rather than dropping unfinished cases. Historical v1 manifests without a named policy remain readable as v1; strict resume still rejects changed source/configuration. Historical model aliases/default sampling can vary over time, so a paired comparison does not prove a causal or statistically significant improvement.

V2 was developed after reviewing the v1 failures. Treat authored-v1 as development data. Preserve both full runs, including failures. The next suite is described below; no success improvement is claimed from scripted tests.

### Fresh cases with the frozen V2 policy

The separate [authored-v2 suite](../datasets/authored-v2/README.md) contains sixteen newly authored mechanisms and distractor combinations. The prompt is the exact V2 prompt published before these cases were prepared. Preparation used no live model calls. The new cases share the ontology, topology, renderer, and baseline telemetry with authored-v1 and were prepared by the same author after earlier development review; they are not an independent or secret benchmark.

After pulling committed source, run:

```bash
python scripts/run_gemini_eval.py --suite authored-v2 --policy v2
```

This uses the same provider settings, budget, pacing, and quota pause as the existing launcher. It checks the frozen prompt before asking for a key. Results go to `runs/gemini-3-5-authored-v2-budget5-policy-v2`; previous runs remain intact. Resume without changing settings or source:

```bash
python scripts/run_gemini_eval.py --suite authored-v2 --policy v2 --resume
```

To inspect results offline:

```bash
python -m inquest summarize --run-dir runs/gemini-3-5-authored-v2-budget5-policy-v2
```

Report this suite separately from authored-v1. The comparison command rejects pairing different suites; a higher percentage on different cases is not a paired policy gain. The [evidence coverage review](EVIDENCE_COVERAGE.md) documents why a health observation may be useful despite receiving zero credit under old case metadata. Historical grader code, cases, and scores remain unchanged; useful health probes are explicitly allowed in the new suite's evidence metadata.

### V3 development candidate on the same cases

To compare against the existing completed V2 run, run only the new candidate:

```bash
python scripts/run_gemini_eval.py --suite authored-v2 --policy v3
```

The new output directory is `runs/gemini-3-5-authored-v2-budget5-policy-v3`. Model/generation settings, budget, pacing and quota pause remain the same. Append `--resume` after quota recovery or interruption without changing code/settings. V3 guidance emphasizes demand, caller evidence, mechanism and contradiction checks; it adds no hidden tool calls or semantic enforcement. See [the policy contract](POLICY_V3.md).

After completion, compare offline:

```bash
python -m inquest compare \
  --baseline runs/gemini-3-5-authored-v2-budget5-policy-v2 \
  --candidate runs/gemini-3-5-authored-v2-budget5-policy-v3
```

Both authored suites informed V3 development. The launcher and comparison output disclose that context. Preserve V2 and report all paired outcomes, including regressions. See [Project progress](PROGRESS.md) for current decisions and review status; scripted checks are not evidence of accuracy gains. Existing defaults and V2 output paths remain unchanged. The authored-v2 launcher still checks the original frozen prompt when running the V2 reference; V3 is a separately fingerprinted experiment. An existing completed output must be preserved; do not rerun merely to replace unfavorable results.

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
