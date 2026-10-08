"""Validate and score reports using evaluator-held labels and a tool transcript.

Adapted from the local Inquest prototype. Evidence is coarse tool/service
relevance, not proof that the cited text entails the diagnosis.
"""
from __future__ import annotations

import math
import re

from .env import InvestigationEnv, Observation
from .scenario import FAULTS, FIX_ACTIONS, Scenario
from .topology import SERVICES

TOOL_TO_GOLD = {
    "get_events": "events", "get_event": "events", "search_logs": "logs",
    "query_metric": "metric", "health_check": "health", "get_trace": "trace",
}
_OBSERVATION_ID = re.compile(r"o[1-9][0-9]*\Z")


def _choice(value: object, choices) -> bool:
    return isinstance(value, str) and value in choices


def _confidence(value: object) -> bool:
    # JSON numbers only: no booleans, numeric strings, coercion, or clipping.
    return type(value) in (int, float) and 0 <= value <= 1 and math.isfinite(value)


def validate_report(report: object) -> tuple[str, ...]:
    """Return stable field errors; unknown keys are ignored, not scored.

    This checks structure only. ``grade`` also resolves references against the
    evaluator's actual transcript. Empty evidence is explicitly invalid.
    """
    if not isinstance(report, dict):
        return ("report: expected object",)
    errors = []
    if not _choice(report.get("service"), SERVICES):
        errors.append("service: expected known service")
    if not _choice(report.get("fault_type"), FAULTS):
        errors.append("fault_type: expected known fault")
    fix = report.get("fix")
    if not isinstance(fix, dict):
        errors.append("fix: expected object")
    else:
        if not _choice(fix.get("action"), FIX_ACTIONS):
            errors.append("fix.action: expected known action")
        if not _choice(fix.get("target"), SERVICES):
            errors.append("fix.target: expected known service")
    if not _confidence(report.get("confidence")):
        errors.append("confidence: expected finite number in [0, 1]")
    cited = report.get("evidence")
    if not isinstance(cited, list):
        errors.append("evidence: expected list")
    elif not cited:
        errors.append("evidence: expected at least one observation ID")
    else:
        for index, value in enumerate(cited):
            if not isinstance(value, str) or not _OBSERVATION_ID.fullmatch(value):
                errors.append(f"evidence[{index}]: expected observation ID (o1, o2, ...)")
    if "summary" in report and not isinstance(report["summary"], str):
        errors.append("summary: expected string")
    return tuple(errors)


def _relevant(scenario: Scenario, observation: Observation) -> bool:
    if observation.error is not None or TOOL_TO_GOLD.get(observation.tool) not in scenario.gold_tools:
        return False
    data = observation.data
    if observation.tool == "search_logs":
        services = [data.get("service")] if data.get("lines") else []
    elif observation.tool == "get_events":
        services = [event.get("service") for event in data.get("events", [])]
    elif observation.tool == "get_event":
        services = [data.get("event", {}).get("service")]
    elif observation.tool == "get_trace":
        trace = data.get("trace") or {}
        services = [span.get("service") for span in trace.get("spans", [])]
    else:
        services = [data.get("service")]
    return any(service in scenario.gold_services for service in services)


def _evidence(scenario: Scenario, transcript: tuple[Observation, ...], cited: object) -> dict:
    by_id = {observation.id: observation for observation in transcript}
    if not isinstance(cited, list):
        cited = []
    seen: set[str] = set()
    total = valid = relevant = duplicates = 0
    errors = []
    for index, value in enumerate(cited):
        if isinstance(value, str):
            if value in seen:
                duplicates += 1
                continue
            seen.add(value)
        total += 1
        if not isinstance(value, str) or not _OBSERVATION_ID.fullmatch(value):
            # Structural validation supplies the field error; retain this item
            # in the denominator without hashing arbitrary malformed values.
            continue
        observation = by_id.get(value)
        if observation is None:
            errors.append(f"evidence[{index}]: unknown observation")
        elif observation.error is not None:
            errors.append(f"evidence[{index}]: failed observation")
        else:
            valid += 1
            relevant += int(_relevant(scenario, observation))
    return {
        "evidence": relevant / total if total else 0.0,
        "citation_count": total, "valid_citations": valid,
        "relevant_citations": relevant, "invalid_citations": total - valid,
        "duplicate_citations": duplicates, "errors": errors,
    }


def evidence_score(scenario: Scenario, env: InvestigationEnv, cited: object) -> float:
    """Coarse relevance fraction including unknown/failed/malformed citations.

    Repeated strings count once; each non-string item counts as invalid.
    Missing or non-list evidence scores zero. No claim-level support is checked.
    """
    return _evidence(scenario, env.obs, cited)["evidence"]


def grade(scenario: Scenario, env: InvestigationEnv, report: object) -> dict:
    """Score one episode without attaching labels to the agent environment.

    The trusted evaluator must pair the scenario and environment from the same
    episode. The result contains evaluator metadata and must not go to agents.
    """
    if not isinstance(scenario, Scenario) or not isinstance(env, InvestigationEnv):
        raise TypeError("grade expects a Scenario and InvestigationEnv from the same episode")
    transcript = env.obs
    body = report if isinstance(report, dict) else {}
    fix = body.get("fix") if isinstance(body.get("fix"), dict) else {}
    service_ok = _choice(body.get("service"), SERVICES) and body["service"] == scenario.root_service
    type_ok = _choice(body.get("fault_type"), FAULTS) and body["fault_type"] == scenario.fault_type
    fix_ok = (fix.get("action") == scenario.fix["action"] and fix.get("target") == scenario.fix["target"])
    evidence = _evidence(scenario, transcript, body.get("evidence"))
    errors = list(validate_report(report)) + evidence.pop("errors")
    report_valid = not errors
    diagnosis_ok = bool(service_ok and type_ok and fix_ok)
    success = report_valid and diagnosis_ok
    confidence = body.get("confidence") if _confidence(body.get("confidence")) else None
    return {
        "scenario": scenario.id, "fault_type": scenario.fault_type,
        "difficulty": scenario.difficulty, "split": scenario.split,
        "submitted": report is not None, "report_valid": report_valid,
        "validation_errors": errors, "service_ok": service_ok,
        "type_ok": type_ok, "fix_ok": fix_ok, "diagnosis_ok": diagnosis_ok,
        "success": success, **evidence,
        "steps": len(transcript), "obs_tokens": sum(observation.tokens for observation in transcript),
        "confidence": confidence,
        "brier": (confidence - float(success)) ** 2 if confidence is not None else None,
    }
