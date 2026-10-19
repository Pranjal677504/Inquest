# Policy V3: mechanism before event

V3 is a selectable investigation-guidance candidate. It prioritizes demand checks for unexplained latency or saturation, caller evidence after missing root logs, and evidence that distinguishes the fault mechanism from a preceding change event. It was developed after examining results on authored-v1 and authored-v2. Both suites are development data for this candidate; neither is an independent assessment of V3.

## Policy and execution contract

- V1 and V2 system prompts retain their exact historical bytes. The V3 prompt SHA-256 is `01cef3e5d0501350a5ec045e55626e701c70473eea65230fe25741729f1a3b88`.
- The common action protocol, eight tools, ontology, strict parser, episode loop, tool budget, grader, and all frozen dataset files are unchanged.
- V3 is a separate instruction block on the common public contract. It does not stack another instruction block onto V2, add reflection API calls, expose labels, or insert case-specific answers.
- Demand checks use the existing `rps` metric. Missing logs prompt source switching toward callers or traces. Degraded health and temporal proximity to a release are not treated as proof of a code fault.
- A release can trigger a more specific mechanism such as a resource leak. Normal memory does not establish that handles, connections, or threads are not leaking.
- Reports should account for the strongest contradiction and remaining uncertainty. There is no invented numeric confidence cap.

These are instructions, **not enforced semantic gates**. The model can still skip a probe, submit early, or express unsupported confidence. Such behavior is recorded and graded as submitted; the runner never repairs a diagnosis, manufactures a probe, or silently changes confidence. Scripts and tests cannot establish that Gemini follows the guidance. No live V3 accuracy improvement is claimed.

## One development comparison

Keep the already-completed V2 run. After pulling committed source, use the private-key launcher once on the same suite:

```bash
python scripts/run_gemini_eval.py --suite authored-v2 --policy v3
```

Results go to `runs/gemini-3-5-authored-v2-budget5-policy-v3`. The launcher preserves the reference model and generation settings, five-call budget, eight-turn limit, 15-second pacing, and first-429 pause. Resume with the same command plus `--resume`; avoid changing source or configuration during the run. Completed failures remain completed. Verify that the Gemini project remains on the free tier; the application enables no billing and has no paid fallback.

Compare saved results without an API key or request:

```bash
python -m inquest compare \
  --baseline runs/gemini-3-5-authored-v2-budget5-policy-v2 \
  --candidate runs/gemini-3-5-authored-v2-budget5-policy-v3
```

The comparison requires the same cases, budget, scoring-source hashes, model and generation settings. Agent-policy source hashes may differ, as expected for a policy update. It reports gains **and regressions**, evidence-relevant success, confidence scores and missingness, invalid reports, protocol errors, steps, elapsed time, and usage. Compare all sixteen cases, retaining failures. Do not describe this as fresh-case validation of V3. Provider aliases/default sampling and execution time may vary.

V3's prompt is slightly longer than V2's. Request and token counts depend on the actual run; the unchanged finite limits do not guarantee identical usage, free quota, or improved accuracy. No extra pilot or baseline rerun is required for this workflow.

## Offline verification

`tests/test_policy_v3.py` checks immutable prompt identities, scripted demand and caller-log paths, bounded malformed-envelope recovery, unchanged failure grading, historical-policy comparison compatibility, and strict resume rejection. The scripted paths are chosen by the evaluator; they verify plumbing and limits, not a model's autonomous probe selection. Launcher tests verify separate output directories, reference generation settings, private-key handoff, and resume.

Frozen case reproduction still requires byte-identical definitions, expanded telemetry, and casebook. Re-rendering after a policy-module edit records that module's current hash in the newly produced provenance manifest; the published dataset and its original provenance remain untouched.
