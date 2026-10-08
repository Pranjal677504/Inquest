"""Report validation, explicit failures, and coarse citation accounting."""
from copy import deepcopy
import json

import pytest

from inquest.env import InvestigationEnv
from inquest.frozen import load_frozen_set
from inquest.grader import evidence_score, grade, validate_report

from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "datasets" / "smoke-v1"


@pytest.fixture
def episode():
    scenario = load_frozen_set(DATA, "test-easy")[7]
    env = InvestigationEnv(scenario, max_steps=6)
    env.call("query_metric", service="postgres", metric="lock_wait_ms")
    return scenario, env


def report_for(scenario, **changes):
    # Evaluator-side fixtures verify the scoring contract, not agent accuracy.
    report = {"service": scenario.root_service, "fault_type": scenario.fault_type,
              "fix": deepcopy(scenario.fix), "confidence": 0.8, "evidence": ["o1"],
              "summary": "A manually specified grading fixture."}
    report.update(changes)
    return report


def test_correct_report_and_costs(episode):
    scenario, env = episode
    result = grade(scenario, env, report_for(scenario))
    assert result["report_valid"] and result["submitted"] and result["success"]
    assert result["service_ok"] and result["type_ok"] and result["fix_ok"]
    assert result["diagnosis_ok"] and result["validation_errors"] == []
    assert result["evidence"] == 1 and result["valid_citations"] == 1
    assert result["steps"] == 1 and result["obs_tokens"] == env.tokens_used()
    assert result["brier"] == pytest.approx(0.04)
    assert not hasattr(env, "sc")


@pytest.mark.parametrize("field,value,failed", [
    ("service", "gateway", "service_ok"),
    ("fault_type", "bad_deploy", "type_ok"),
    ("fix", {"action": "rollback", "target": "postgres"}, "fix_ok"),
    ("fix", {"action": "rollback_migration", "target": "gateway"}, "fix_ok"),
])
def test_wrong_known_predictions(episode, field, value, failed):
    scenario, env = episode
    result = grade(scenario, env, report_for(scenario, **{field: value}))
    assert result["report_valid"] and not result[failed]
    assert not result["diagnosis_ok"] and not result["success"]
    assert result["brier"] == pytest.approx(0.64)


@pytest.mark.parametrize("confidence", [None, True, False, "0.8", [], {}, -0.01, 1.01,
                                        float("nan"), float("inf"), -float("inf"), 10 ** 500])
def test_invalid_confidence_is_not_coerced_or_replaced(episode, confidence):
    scenario, env = episode
    result = grade(scenario, env, report_for(scenario, confidence=confidence))
    assert not result["report_valid"] and not result["success"]
    assert result["diagnosis_ok"]
    assert result["confidence"] is None and result["brier"] is None
    assert "confidence: expected finite number in [0, 1]" in result["validation_errors"]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("confidence,expected", [(0, 1), (0.0, 1), (1, 0), (1.0, 0)])
def test_confidence_boundaries(episode, confidence, expected):
    scenario, env = episode
    result = grade(scenario, env, report_for(scenario, confidence=confidence))
    assert result["success"] and result["brier"] == expected


@pytest.mark.parametrize("report", [None, {}, [], ["o1"], "{", "{}", 1, False])
def test_nonreports_and_empty_reports_are_explicit(episode, report):
    scenario, env = episode
    result = grade(scenario, env, report)
    assert not result["report_valid"] and not result["success"]
    assert result["submitted"] is (report is not None)
    assert result["confidence"] is None and result["brier"] is None
    assert result["validation_errors"]
    assert result["steps"] == 1
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("field", ["service", "fault_type", "fix", "evidence", "confidence"])
def test_missing_required_fields(episode, field):
    scenario, env = episode
    report = report_for(scenario)
    del report[field]
    result = grade(scenario, env, report)
    assert not result["report_valid"] and not result["success"]
    assert any(error.startswith(field) for error in result["validation_errors"])


@pytest.mark.parametrize("changes", [
    {"service": []}, {"service": "POSTGRES"}, {"fault_type": {}}, {"fault_type": "other"},
    {"fix": []}, {"fix": "rollback"}, {"fix": {}},
    {"fix": {"action": [], "target": {}}}, {"fix": {"action": "other", "target": "other"}},
    {"summary": []}, {"evidence": None}, {"evidence": "o1"}, {"evidence": []},
    {"evidence": [{"id": "o1"}, ["o1"], 1, True, None]},
    {"evidence": ["o0", "o01", "o-1", "o1\n", "O1"]},
])
def test_malformed_nested_fields_never_crash(episode, changes):
    scenario, env = episode
    result = grade(scenario, env, report_for(scenario, **changes))
    assert not result["report_valid"] and not result["success"]
    json.dumps(result, allow_nan=False)


def test_unknown_citations_remain_in_denominator(episode):
    scenario, env = episode
    result = grade(scenario, env, report_for(scenario, evidence=["o1", "o1", "o999", "o999"]))
    assert result["evidence"] == 0.5
    assert result["citation_count"] == 2 and result["duplicate_citations"] == 2
    assert result["valid_citations"] == 1 and result["invalid_citations"] == 1
    assert result["diagnosis_ok"] and not result["success"]
    assert result["brier"] == pytest.approx(0.64)
    assert result["validation_errors"] == ["evidence[2]: unknown observation"]


def test_malformed_citations_remain_in_denominator(episode):
    scenario, env = episode
    cited = ["o1", {"id": "o1"}, ["o1"], "bad", "bad"]
    result = grade(scenario, env, report_for(scenario, evidence=cited))
    assert result["evidence"] == 0.25
    assert result["citation_count"] == 4 and result["invalid_citations"] == 3
    assert result["duplicate_citations"] == 1
    assert evidence_score(scenario, env, cited) == result["evidence"]


def test_failed_call_cannot_supply_evidence_and_still_costs_a_step(episode):
    scenario, env = episode
    returned = env.call("query_metric", service="postgres", metric="nonexistent")
    returned.error = None  # Detached returned object does not change the transcript.
    result = grade(scenario, env, report_for(scenario, evidence=["o1", "o2"]))
    assert result["steps"] == 2 and result["obs_tokens"] == env.tokens_used()
    assert result["evidence"] == 0.5 and result["invalid_citations"] == 1
    assert "evidence[1]: failed observation" in result["validation_errors"]
    assert not result["report_valid"]


def test_known_irrelevant_evidence_does_not_prove_support(episode):
    scenario, env = episode
    env.call("list_services")
    env.call("query_metric", service="cache", metric="rps")
    result = grade(scenario, env, report_for(scenario, evidence=["o2", "o3"]))
    assert result["evidence"] == 0
    assert result["valid_citations"] == 2 and result["invalid_citations"] == 0
    # This milestone checks reference validity and accuracy, not entailment.
    assert result["report_valid"] and result["success"]


def test_empty_log_results_are_not_relevant(episode):
    scenario, env = episode
    env.call("search_logs", service="postgres", query="no such log marker")
    result = grade(scenario, env, report_for(scenario, evidence=["o2"]))
    assert result["report_valid"] and result["evidence"] == 0


def test_event_lists_use_returned_services_not_query_arguments(episode):
    scenario, env = episode
    event_list = env.call("get_events")
    assert event_list.args == {}
    assert evidence_score(scenario, env, [event_list.id]) == 1
    causal_event = next(e for e in event_list.data["events"] if e["service"] == "postgres")
    detail = env.call("get_event", event_id=causal_event["id"])
    assert evidence_score(scenario, env, [detail.id]) == 1


def test_event_list_with_no_gold_service_is_irrelevant(episode):
    scenario, env = episode
    event = env.call("get_events", service="cache")
    assert evidence_score(scenario, env, [event.id]) == 0


def test_trace_service_relevance_when_labels_allow_trace(episode):
    scenario, _ = episode
    scenario.gold_tools = ["trace"]  # Evaluator-only fixture; no published bytes edited.
    scenario.gold_services = ["postgres"]
    env = InvestigationEnv(scenario)
    observation = env.call("get_trace", status="timeout")
    assert observation.data["trace"] is not None
    assert evidence_score(scenario, env, [observation.id]) == 1


def test_no_trace_is_not_relevant(episode):
    scenario, _ = episode
    scenario.gold_tools = ["trace"]
    scenario.gold_services = ["postgres"]
    scenario.traces = []
    env = InvestigationEnv(scenario)
    observation = env.call("get_trace")
    assert observation.data["trace"] is None
    assert evidence_score(scenario, env, [observation.id]) == 0


def test_validation_and_grading_do_not_mutate_inputs(episode):
    scenario, env = episode
    report = report_for(scenario, evidence=["o1", "o1"])
    before = deepcopy((scenario, report, env.obs))
    assert validate_report(report) == ()
    first = grade(scenario, env, report)
    first["validation_errors"].append("external edit")
    second = grade(scenario, env, report)
    assert second["validation_errors"] == []
    assert (scenario, report, env.obs) == before


def test_optional_summary_and_extra_keys(episode):
    scenario, env = episode
    report = report_for(scenario)
    del report["summary"]
    report["unscored_notes"] = {"anything": "extra"}
    report["fix"]["version"] = "unscored"
    assert grade(scenario, env, report)["report_valid"]


def test_zero_step_episode_and_no_report(episode):
    scenario, _ = episode
    result = grade(scenario, InvestigationEnv(scenario, max_steps=0), None)
    assert result["steps"] == result["obs_tokens"] == result["citation_count"] == 0
    assert not result["submitted"] and not result["success"]


def test_bad_evaluator_arguments_raise(episode):
    scenario, env = episode
    with pytest.raises(TypeError):
        grade(None, env, {})
    with pytest.raises(TypeError):
        grade(scenario, None, {})


def test_all_frozen_outcomes_and_json_safe_scores():
    checked = 0
    for file in sorted(DATA.glob("*.jsonl")):
        for scenario in load_frozen_set(DATA, file.stem):
            env = InvestigationEnv(scenario, max_steps=1)
            env.call("health_check", service=scenario.root_service)
            report = report_for(scenario)
            score = grade(scenario, env, report)
            assert score["success"] and score["diagnosis_ok"]
            assert score["scenario"] == scenario.id
            assert score["fault_type"] == scenario.fault_type
            assert score["difficulty"] == scenario.difficulty and score["split"] == scenario.split
            assert 0 <= score["evidence"] <= 1
            assert score["confidence"] == 0.8
            assert score["brier"] == pytest.approx(0.04)
            assert json.loads(json.dumps(score, allow_nan=False)) == score
            checked += 1
    assert checked == 120
