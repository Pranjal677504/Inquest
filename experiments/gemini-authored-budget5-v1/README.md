# Gemini 3.5 Flash-Lite: first full authored-set evaluation

This is the fixed reference for policy v2 development. The user ran Gemini on their own Mac and supplied the complete saved run. The reviewer made no live model calls: all request histories, observations, reports, and grades were reproduced offline from the recorded replies.

## Provenance and verification

- Source revision: `79ca81b8ec8d6398559aa5a14096fa592e743bab`, recorded clean.
- Run fingerprint: `33b45f62b11ccdb74b4727bc673cc00089e67f86a89881b77ab933cb7105bbcd`.
- Model returned: `gemini-3.5-flash-lite`; provider default temperature, JSON mode, `max_tokens=2048`.
- Policy: original v1, prompt SHA-256 `ed68047e265416ec7d41bdebf7fbeec362f019c60aae3611403d766ddcd081b6`.
- Sixteen authored cases, budget 5, maximum 8 model turns, two protocol-error allowance, 15-second request interval.
- Recorded package hashes matched the original source tree. Dataset, catalog, manifest, and prompt hashes matched; the saved summary recomputed exactly.
- All 92 request histories, 67 observations, 16 reports, and 16 grades reproduced. The 16 corresponding offline-baseline grades also reproduced.
- The original archive remains private with the user. Public artifacts contain only the summary and aggregate audit: `audit.json` records the original uploaded archive checksum, verification counts, and the paired outcome counts/case IDs. Raw prompts, responses, observations, and provider response IDs are not published. The offline replay verified internal consistency, not cryptographic attestation by the model provider.

## Results at budget 5

| Metric | Gemini v1 | Offline earliest-alert policy |
|---|---:|---:|
| Accepted reports | 10/16 (62.5%) | 11/16 (68.75%) |
| Success with relevant evidence | 10/16 | 10/16 |
| Medium | 7/8 | 7/8 |
| Hard | 3/8 | 4/8 |
| Mean Brier score | 0.25156875 | 0.25 |

Both policies succeeded on 9 cases and failed on 4. Gemini uniquely succeeded on case 003; the offline policy uniquely succeeded on cases 014 and 015. The offline policy's accepted case 015 lacked evidence that passed the coarse relevance check.

All Gemini final reports were structurally valid. Nine of 92 replies had malformed tool envelopes and were corrected after protocol feedback; no malformed request was silently repaired or executed. There were no transport failures. Provider-reported usage was 104,939 input and 2,477 output tokens, with no missing usage fields. Reported zeros, including malformed-response usage, remain as supplied by the provider; they are not independently measured token counts.

Mean episode elapsed time was 85.38 seconds, including pacing. The recorded waits sum to 1,259.13 seconds across the run; this is not an inference-speed benchmark.

## Six diagnosis failures

| Case | Expected mechanism and repair | Observed decision problem |
|---|---|---|
| 004 | Payments feature flag; disable flag | Report blamed deployment despite successful dark-path canary and `risk-inline=true` logs. Submitted at 4/5 steps with 0.95 confidence. |
| 008 | Postgres endpoint outage; failover | Read fenced-writer and working-alternate-endpoint logs, then blamed a payments deployment. Submitted at 4/5 steps with 0.95 confidence. |
| 011 | Search certificate expiry; renew certificate | Normal search error metrics weakened the deployment hypothesis; no TLS health or gateway-log check followed. Submitted at 4/5 steps with 0.5 confidence. |
| 012 | Gateway configuration; revert gateway configuration | Chose an inventory configuration already restored before gateway errors began. Used 5/5 steps, confidence 0.5. |
| 014 | Search demand surge; scale up | Queried an empty log source twice and never inspected request volume. Used 5/5 steps, confidence 0.95. |
| 015 | Cache dependency outage; failover | Correctly located a down cache but inferred resource leakage without evidence. Used 5/5 steps, confidence 0.9. |

Four wrong reports had confidence 0.9–0.95. Mean confidence was 0.984 on successes and 0.7917 on failures. This single, small sample does not establish calibration. The overall Brier score did not improve on a constant 0.5-confidence reference.

## Policy v2 experiment

V2 adds generic competing-explanation checks, contradiction checks, source switching when logs are absent, and explicit nested-argument examples. The original v1 prompt, cases, tool behavior, and grader remain unchanged. There is no case-specific lookup, answer injection, automatic repair of malformed replies, or enforced success threshold.

Run all 16 cases with the same model settings and budget using `python scripts/run_gemini_eval.py --policy v2`. This creates a separate directory. Use `python -m inquest compare` to report paired improvements and regressions after completion; comparison needs no key or API call. See `docs/RUNNER.md` for exact commands.

No v2 model results are included yet. V2 was designed after examining these cases and failures: this is a development-set experiment, not an untouched holdout comparison. Freeze v2 before authoring fresh evaluation cases. The offline baseline was also designed after inspecting the public data. Provider aliases and default sampling can change results. The original 16-case Wilson interval is descriptive (approximately 38.6–81.5%); it does not support a production-accuracy or model-ranking claim.
