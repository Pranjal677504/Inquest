# Report grading

The grader validates a final diagnosis and scores it against evaluator-held labels. It uses the saved tool transcript for reference checks and investigation cost. No model or API key is needed.

## Quickstart

```bash
python examples/grade_report.py
```

This demonstration scores two **handcrafted** reports over one checksum-verified frozen case. The first has a correct diagnosis and existing references; the second cites an observation that does not exist. The confidence values are chosen constants. Neither report is an agent prediction or evidence of benchmark performance.

The output identifies the suite, set, file checksum, code revision, and whether the checkout has uncommitted changes. Revision and dirty state are `null` when Git metadata is unavailable. Published experiments require a clean recorded revision and full run provenance.

## Evaluator API

```python
from inquest.env import InvestigationEnv
from inquest.frozen import load_frozen_set
from inquest.grader import grade, validate_report

case = load_frozen_set("datasets/smoke-v1", "test-easy")[7]
env = InvestigationEnv(case, max_steps=3)
observation = env.call("query_metric", service="postgres", metric="lock_wait_ms")
report = {
    "service": "postgres",
    "fault_type": "bad_migration",
    "fix": {"action": "rollback_migration", "target": "postgres"},
    "evidence": [observation.id],
    "confidence": 0.8,
}
assert validate_report(report) == ()
score = grade(case, env, report)
```

The evaluator must pair the scenario and environment from the **same episode**. The environment does not retain its construction bundle or labels. The grader receives the labeled scenario separately. Grade results contain scenario IDs and ground-truth metadata and belong on the evaluator side; agents receive tool observations only.

`grade(scenario, env, report)` accepts a decoded report object or `None`. It returns explicit failure scores for malformed reports. Passing a raw JSON string does not parse it and yields an object-validation error. Future adapters will handle decoding and parse failures. Incorrect evaluator argument types raise `TypeError`.

`validate_report(report)` returns a tuple of structural field errors. It does not consult labels or check whether observation IDs exist. `grade` additionally resolves references against the environment's saved transcript.

## Report contract

| Field | Requirement |
|---|---|
| `service` | Exact known service name |
| `fault_type` | Exact known fault category |
| `fix` | Object with a known `action` and known service `target` |
| `evidence` | Nonempty list of observation ID strings: `o1`, `o2`, and so on |
| `confidence` | Finite JSON number from 0 to 1 inclusive |
| `summary` | Optional string; not semantically graded |

Names are case-sensitive. Unknown fields and extra fix parameters are ignored and receive no credit. A known but incorrect service, fault, action, or target is a valid prediction that can fail its accuracy check.

Booleans, numeric strings, out-of-range values, NaN, infinity, and missing confidence are invalid. There is no conversion, clipping, or default confidence. Invalid confidence produces `null` for both `confidence` and `brier`; the validation failure remains recorded.

An absent or empty evidence list is invalid. Unknown, malformed, and failed-call references are invalid. A successful observation with zero results is an existing reference, but supplies no relevance credit for an empty log/event/trace result. Repeated string references count once for scoring and are counted separately as duplicates.

## Score definitions

| Output | Definition |
|---|---|
| `submitted` | A value other than `None` was supplied, including an empty object or malformed value |
| `report_valid` | All structural fields and observation references pass validation |
| `validation_errors` | Field-specific errors; raw malformed values are not echoed |
| `service_ok`, `type_ok` | Exact match to the labeled initiating service and fault |
| `fix_ok` | Both action and target match the labeled fix |
| `diagnosis_ok` | All three accuracy checks pass, independently of report validity |
| `success` | `report_valid` and `diagnosis_ok` are both true |
| `confidence` | Original valid number, otherwise `null` |
| `brier` | `(confidence - success)^2`, otherwise `null` for invalid confidence |
| `evidence` | Fraction of counted citations with coarse gold tool/service relevance |
| `citation_count` | Unique string citations plus each non-string citation item |
| `valid_citations` | Counted references to existing successful observations |
| `relevant_citations` | Valid references satisfying the relevance heuristic |
| `invalid_citations` | `citation_count - valid_citations` |
| `duplicate_citations` | Repeated string citation entries removed from the scoring denominator |
| `steps` | Number of recorded attempted tool calls, including invalid calls |
| `obs_tokens` | Sum of observation-text token estimates from the same transcript snapshot |

The result also records the evaluator's scenario ID, true fault, split, and difficulty. It contains JSON-safe values, including explicit `null` for unavailable confidence metrics.

For example, one relevant reference plus one unknown reference scores `evidence = 0.5`. The unknown ID also makes the report invalid, so `success = false` even if all predictions match. Component checks and `diagnosis_ok` preserve that distinction. With valid confidence 0.8, this invalid submission has Brier loss 0.64 under the accepted-success definition.

Confidence is assessed against accepted joint success, including the report contract. Future evaluations must report invalid-report and invalid-confidence counts, retain failed episodes in success denominators, and state the number of valid confidence values used for Brier summaries. Averaging only available Brier values without reporting missingness can give a misleading result. A single Brier loss cannot establish calibration.

## Coarse evidence relevance

This initial heuristic adapts the prototype's gold tool/service labels:

| Observation | Services considered |
|---|---|
| Metric, health, or nonempty log response | Returned `service` |
| Event list | Services in the returned event summaries |
| Event detail | Service in the returned event |
| Nonempty trace | Services in the returned spans |

Credit requires a successful observation, its tool class in `scenario.gold_tools`, and at least one returned service in `scenario.gold_services`. Service inventory and general alerts are not mapped to gold tool classes. Current frozen cases do not mark traces as a gold class, so trace references receive no relevance credit in this suite.

Empty records, failed observations, and invalid IDs receive zero credit. Invalid IDs remain in the denominator rather than being silently discarded. Unscoped event queries use the records actually returned, which can include a gold service. A benign record about the right service can still receive credit: this heuristic does not inspect whether text supports a specific claim.

**Reference validity and relevance are separate.** A correct diagnosis citing existing but irrelevant observations can still have `success = true` and `evidence = 0`. The later evidence-support milestone will assess claims or cited lines. Fix grading checks action and target only; it does not verify rollback versions, configuration keys, recovery effectiveness, or safety of an operational intervention.

## Provenance and verification

The accuracy checks, Brier calculation, tool-class mapping, and score metadata originate from the local prototype's `src/inquest/grader.py`. Integration replaces its access to `env.sc` with an explicit evaluator-held scenario, adds strict report validation, preserves invalid citations, excludes failed/empty records from relevance credit, and recognizes returned event/trace services.

Tests cover exact and partial diagnosis matches, both fix fields, missing and malformed reports, confidence boundaries and non-finite values, citation duplication and invalid IDs, failed calls, empty results, event/trace relevance, input immutability, and JSON-safe scores. All 120 published frozen cases are exercised with evaluator-authored correct-report fixtures. Those fixture assertions verify the grading implementation and do not measure agent accuracy. Python compatibility remains locally verified on 3.14 only.
