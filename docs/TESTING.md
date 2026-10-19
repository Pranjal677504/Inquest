# Testing

## Python behavior and frozen data

From a checkout with Python 3.10 or newer:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

The read-only CI matrix runs the Python suite, all five examples, and frozen checksum verification on Python 3.10–3.14. Keep published dataset bytes unchanged. From `datasets/smoke-v1`, run `sha256sum -c SHA256SUMS` on Linux or `shasum -a 256 -c SHA256SUMS` on macOS.

Scenario loading validates health status, a nonempty version string, a nonnegative integer restart count, and integer certificate days. Negative certificate days are valid expired-certificate telemetry. Additional health metadata is allowed and remains excluded from investigation observations.

## Browser workflows

Browser tests are separate from the default Python suite so ordinary toolkit development does not require a browser installation:

```bash
python -m pip install -e ".[dev,browser]"
python -m playwright install --with-deps --only-shell chromium
python -m pytest browser_tests -q
```

The test fixture starts Flask through Werkzeug on an ephemeral loopback port and closes the server and browser afterward. No model, credentials, deployed site, or database is needed. A dedicated CI job runs the same commands on Linux with Python 3.12.

Checks exercise real frozen/generated incident requests, diagnosis submission, case resets, keyboard service selection and tab navigation, duplicate submissions, and recovery from non-JSON HTTP errors. Delayed-response checks hold completed diagnosis HTTP responses at the browser transport boundary and release them after another case loads. Both stale successes and stale errors must stay hidden. Delays use explicit release signals rather than fixed sleeps. JavaScript page errors fail the tests.

These are application correctness checks. Handcrafted diagnoses and assertions against evaluator-held labels are not autonomous-agent evaluation results. The additive `evidence_relevant_success` metric is documented in [Grading](GRADING.md); it does not establish claim-level evidence support.

## Authored causal fixtures

`tests/test_authored.py` exercises every case’s support and counterevidence probes through the tools, grading compatibility, metadata isolation, malformed identity rejection, checksums, casebook binding, generator independence, source-to-data reproduction, and overwrite protection. Legacy smoke serialization is checked against all 120 original records. Verify the four additional canonical hashes from `datasets/authored-v1` with `sha256sum -c SHA256SUMS`.

These checks validate interfaces and clue reachability. They are not an independent review of the causal narratives or agent accuracy measurements. See [the authored suite guide](../datasets/authored-v1/README.md) for limitations.

## Fresh authored-v2 suite

`tests/test_authored_v2.py` checks all sixteen five-call support/counterevidence paths, category balance, missing-log cases, rejection of incorrect diagnoses, selected mechanism-specific metric/health signals, metadata isolation, checksum corruption, source reproduction, and cross-suite identity rejection. Tests pin the existing V2 prompt hash; no provider is called. The launcher tests check separate output paths, unchanged old defaults, quota pause, resume, and rejection of an incompatible policy or changed prompt before requesting a key.

CI verifies the four new canonical checksums separately from the old suites. The documented paths are evaluator-authored fixtures and establish clue reachability and grading compatibility, not autonomous investigation or independent causal validation. See [the new suite guide](../datasets/authored-v2/README.md) and [evidence coverage review](EVIDENCE_COVERAGE.md).

## V3 policy candidate

`tests/test_policy_v3.py` pins all three prompt hashes and exercises scripted demand/caller-log paths, strict envelope limits, unchanged grading of unsupported reports, saved V2/V3 comparison and incompatible resume rejection. Launcher tests preserve reference generation settings, paths, key privacy and quota pause. These verify execution contracts; they do not show that a model chooses the scripted probes or becomes more accurate. See [Policy V3](POLICY_V3.md) before interpreting a development comparison.

## Agent runner and provider contracts

`tests/test_runner.py` covers strict JSON, bounded protocol errors, charged invalid calls, report validation, context/turn limits, label isolation, mutation isolation, crash-safe result replacement, process locking, interrupted resume, preserved failed attempts, configuration mismatch, summaries and replay. `tests/test_backends.py` uses real loopback HTTP to check Ollama/compatible request bodies, response identities, usage accounting, bounded retries, failed authentication, redirect rejection and error-body redaction. All provider responses in these tests are fixtures; they are not model results.

The CLI runs from a built wheel outside the checkout with an explicitly supplied suite directory. CI adds an isolated wheel/console-entrypoint smoke run. Actual provider and model execution must be verified separately; see [Runner](RUNNER.md).
