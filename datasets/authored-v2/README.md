# Fresh authored incidents: inquest-authored-v2

Sixteen new synthetic incidents, frozen on 2026-10-19 for the already-existing policy **v2**. There are two cases per supported fault category: one medium and one hard. Four hard cases omit root-service logs. The services, topology, fault ontology, tools, shared baseline metric values, renderer, and grader are retained from the existing benchmark; the initiating mechanisms, timelines, logs, and distractor combinations are newly authored.

The suite version and policy version are separate concepts. `authored-v2` identifies these data bytes. `--policy v2` identifies the unchanged investigation instructions. Neither refers to new model weights.

## Frozen experiment

- Policy source revision: `91e1a0354b1cb562f121d44d91ffa7a2a75e5574`, published before these cases were authored.
- V2 system-prompt SHA-256: `6c94ffeaf6dbde3eeea84e5d5f1e1f34c24a0b9fd8284bfd13a28a8d9d8a411a`.
- Budget: five tool calls, eight model turns, two protocol-error allowance.
- Planned provider settings: `gemini-3.5-flash-lite`, omitted temperature, JSON mode, `max_tokens=2048`, 15-second attempt pacing, pause on the first HTTP 429.
- No model calls, candidate rejection based on model scores, prompt changes, or live performance claims were used to prepare this suite.

The [manifest](manifest.json) records the evaluation contract, construction-source hashes, ordered identities, and data hash. [SHA256SUMS](SHA256SUMS) binds the source definitions, expanded data, machine-readable casebook, and manifest. Freeze/pin the published Git revision and retain these hashes before running. Provider aliases and default sampling cannot pin remote model weights.

## Case coverage

| Cases | Fault | New initiating mechanisms |
|---|---|---|
| 001–002 | Bad deployment | Retired signing-key slot; overflowing order cents conversion |
| 003–004 | Configuration regression | Two-slot local connection pool; deadline shorter than healthy commit time |
| 005–006 | Resource leak | Retained auth audit buffers; unclosed search result handles |
| 007–008 | Certificate expiry | Payments and auth TLS failures before HTTP dispatch |
| 009–010 | Traffic surge | Checkout replay; partner search request fan-out |
| 011–012 | Bad migration | Removed ledger column name; narrowed stock quantity type |
| 013–014 | Dependency outage | Stopped cache listener; closed public database socket |
| 015–016 | Feature flag | Synchronous search explanations; blocking orders audit mirror |

The [casebook](CASEBOOK.md) documents every cause, distractor, and five-call path. Every path begins with alerts, reaches at least two support probes and one counterevidence probe, and fits the unchanged tool budget. These paths are evaluator-authored and use known labels when choosing probes: they verify availability of clues and grading compatibility, **not autonomous discovery, unique causality, or model performance**.

Health checks are included in this new suite's gold evidence where useful, including the cache outage. The grader implementation and all old cases remain unchanged. Evidence is still coarse tool/service relevance, not proof that a cited observation entails every part of the proposed cause or repair. See [the evidence coverage review](../../docs/EVIDENCE_COVERAGE.md).

## Offline review and model run

```bash
python scripts/build_authored_v2.py --output-dir /tmp/inquest-authored-v2-review
python -m pytest -q tests/test_authored_v2.py tests/test_gemini_launcher.py
```

The renderer refuses a nonempty destination. It imports only the explicit-keyframe renderer, never the procedural incident generator. Tests verify all sixteen probe paths, counterevidence, wrong-diagnosis rejection, source reproducibility, checksum failures, suite identity, and the frozen prompt.

After pulling committed source and activating the project's virtual environment:

```bash
python scripts/run_gemini_eval.py --suite authored-v2 --policy v2
```

The launcher validates the prompt before asking privately for the key. Results go to `runs/gemini-3-5-authored-v2-budget5-policy-v2`, preserving existing outputs. To resume the exact same configuration after quota recovery or interruption, append `--resume`. Verify your Gemini project is on the free tier; the launcher does not enable billing or use paid fallbacks. Preparation and offline validation use no API requests.

## Interpretation and limitations

These are **public, AI-authored, single-author-reviewed synthetic cases**. The same author designed policy v2, inspected earlier development results, and prepared this suite; that knowledge informed the coverage. The suite is fresh relative to the frozen policy but is not independent, blinded, secret, or representative production data. The on-disk `holdout` name is a format convention, not a claim of statistical independence. No independent human/domain-expert review has occurred.

Report the new suite separately. The comparison command deliberately refuses to pair it against authored-v1 because the incidents differ. A future policy comparison must run both policies on the same frozen suite and compatible configuration. Once these cases influence another prompt, they become development data for that prompt. Do not select or edit cases in response to V2's results while continuing to call them untouched assessment data.
