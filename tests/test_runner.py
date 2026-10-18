"""Episode and persistence contracts; scripted replies are not model experiments."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from inquest.agent_protocol import ProtocolError, parse_action
from inquest.backends import BackendError, ModelReply
from inquest.cli import main
from inquest.frozen import load_frozen_set
from inquest.runner import (EpisodeConfig, RunError, atomic_json, run_episode,
                            run_experiment, run_lock, summarize, wilson)

SUITE = Path(__file__).resolve().parents[1] / "datasets/authored-v1"


class Scripted:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.messages = []

    def identity(self):
        return {"kind": "scripted_test_fixture", "is_model": True}

    def complete(self, messages, emit):
        self.messages.append(deepcopy(messages))
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        return response if isinstance(response, ModelReply) else ModelReply(response, "test-model", 10, 20)


def tool(name="search_logs", **args):
    return json.dumps({"kind": "tool", "tool": name, "args": args or {"service": "auth"}})


def report(scenario, **changes):
    body = {"service": scenario.root_service, "fault_type": scenario.fault_type,
            "fix": deepcopy(scenario.fix), "evidence": ["o1"], "confidence": 0.6}
    body.update(changes)
    return json.dumps({"kind": "report", "report": body})


@pytest.fixture
def scenario():
    return load_frozen_set(SUITE, "holdout")[0]


def episode(scenario, responses, **options):
    events = []
    backend = Scripted(responses)
    result = run_episode(scenario, backend, EpisodeConfig(**options), lambda k, b: events.append({"kind": k, **b}))
    return result, events, backend


@pytest.mark.parametrize("text", [
    "not JSON", '```json\n{}\n```', '[]', '{}', '{"kind":"shell"}',
    '{"kind":"tool","tool":"get_alerts","args":[],"extra":1}',
    '{"kind":"tool","tool":5,"args":{}}',
    '{"kind":"report","report":{},"extra":1}',
    '{"kind":"report","kind":"tool","report":{}}',
    '{"kind":"report","report":{"confidence":NaN}}',
    '{"kind":"report","report":{"confidence":1e999}}',
    '{} {}', 'x' * 32001,
])
def test_strict_action_protocol_rejects_malformed_or_ambiguous_values(text):
    with pytest.raises(ProtocolError):
        parse_action(text)


def test_valid_report_is_graded_and_usage_is_preserved(scenario):
    result, events, _ = episode(scenario, [tool(), report(scenario)], max_steps=1)
    assert result["status"] == "reported"
    assert result["score"]["success"] and result["score"]["evidence_relevant_success"]
    assert result["score"]["steps"] == 1
    assert result["score"]["brier"] == pytest.approx(0.16)
    assert result["usage"]["input_tokens_known"] == 20
    assert result["usage"]["output_tokens_known"] == 40
    assert result["usage"]["input_usage_missing_calls"] == 0
    assert [e["kind"] for e in events] == ["model_request", "model_reply", "observation",
                                            "model_request", "model_reply", "report", "episode_finished"]


def test_protocol_feedback_is_bounded_and_not_a_free_tool_call(scenario):
    result, events, _ = episode(scenario, ['{"kind":"tool","args":[]}', tool(), report(scenario)], max_steps=1)
    assert result["score"]["success"]
    assert result["protocol_errors"] == 1 and result["score"]["steps"] == 1
    assert any(e["kind"] == "protocol_error" for e in events)
    failed, _, _ = episode(scenario, ['no', 'still no', report(scenario)])
    assert failed["status"] == "protocol_error" and failed["model_turns"] == 2
    assert failed["score"]["steps"] == 0 and not failed["score"]["success"]


@pytest.mark.parametrize("action", [tool("erase_database"), tool("query_metric", service="auth", metric="nonexistent")])
def test_invalid_environment_calls_are_charged(scenario, action):
    result, events, _ = episode(scenario, [action, report(scenario)], max_steps=1)
    assert result["score"]["steps"] == 1
    assert not result["score"]["report_valid"]
    assert next(e for e in events if e["kind"] == "observation")["observation"]["error"] is not None


def test_no_tool_runs_beyond_budget(scenario):
    result, events, _ = episode(scenario, [tool(), tool(), tool()], max_steps=2)
    assert result["status"] == "tool_budget_exhausted"
    assert result["score"]["steps"] == 2 and result["model_turns"] == 3
    assert sum(e["kind"] == "observation" for e in events) == 2


@pytest.mark.parametrize("changes", [{"confidence": True}, {"evidence": ["o999"]}, {"fix": {}}])
def test_final_report_contract_failures_are_not_silently_repaired(scenario, changes):
    result, _, _ = episode(scenario, [tool(), report(scenario, **changes)])
    assert result["status"] == "reported"
    assert not result["score"]["report_valid"]
    assert result["model_turns"] == 2


def test_provider_error_and_missing_usage_are_explicit(scenario):
    result, _, _ = episode(scenario, [BackendError("provider_http_401")])
    assert result["status"] == "backend_error" and not result["score"]["success"]
    assert result["usage"]["model_requests"] == result["usage"]["input_usage_missing_calls"] == 1
    result, _, _ = episode(scenario, [ModelReply(tool(), "test-model"), ModelReply(report(scenario), "test-model")])
    assert result["usage"]["input_tokens_known"] == 0
    assert result["usage"]["input_usage_missing_calls"] == 2


def test_case_metadata_and_gold_are_not_in_backend_messages(scenario):
    scenario.meta["secret"] = "PRIVATE-EVALUATOR-METADATA"
    _, _, backend = episode(scenario, [tool(), report(scenario)])
    text = json.dumps(backend.messages)
    assert scenario.id not in text
    assert "PRIVATE-EVALUATOR-METADATA" not in text
    assert 'root_service' not in text and 'gold_services' not in text


def test_backend_cannot_mutate_retained_chat_history(scenario):
    class Mutating(Scripted):
        def complete(self, messages, emit):
            reply = super().complete(messages, emit)
            messages[0]["content"] = "MUTATED"
            return reply
    backend = Mutating([tool(), report(scenario)])
    run_episode(scenario, backend, EpisodeConfig(max_steps=1), lambda *args: None)
    assert backend.messages[1][0]["content"] != "MUTATED"


def test_context_and_turn_limits_stop_without_hallucinated_results(scenario):
    result, _, _ = episode(scenario, [], max_prompt_chars=1)
    assert result["status"] == "context_limit" and result["model_turns"] == 0
    result, _, _ = episode(scenario, [tool()], max_model_turns=1)
    assert result["status"] == "model_turn_limit" and not result["score"]["success"]


def experiment(tmp_path, backend, **changes):
    settings = {"suite": SUITE, "set_name": "holdout", "backend": backend,
                "budgets": (1,), "output": tmp_path / "run", "case_limit": 1, "allow_dirty": True}
    settings.update(changes)
    return run_experiment(**settings)


def test_completed_resume_skips_every_model_request(tmp_path, scenario):
    first = experiment(tmp_path, Scripted([tool(), report(scenario)]))
    second = experiment(tmp_path, Scripted([]), resume=True)
    assert first == second
    assert second["groups"]["budget_1/all"]["success_rate"] == 1
    assert second["usage_all_attempts"]["model_requests"] == 2


def test_failed_completed_episode_stays_in_denominator_and_is_not_retried(tmp_path):
    result = experiment(tmp_path, Scripted([BackendError("provider_http_401")]))
    assert result["groups"]["budget_1/all"]["success_rate"] == 0
    assert result["groups"]["budget_1/all"]["brier_missing"] == 1
    assert experiment(tmp_path, Scripted([]), resume=True) == result


def test_interrupted_episode_restarts_with_a_preserved_prior_attempt(tmp_path, scenario):
    with pytest.raises(KeyboardInterrupt):
        experiment(tmp_path, Scripted([tool(), KeyboardInterrupt()]))
    directory = tmp_path / "run/episodes/case-0001-budget-001"
    first_journal = (directory / "attempt-001.jsonl").read_bytes()
    before = summarize(tmp_path / "run")
    assert before["completed_episodes"] == 0
    assert before["groups"]["budget_1/all"]["success_rate"] is None
    result = experiment(tmp_path, Scripted([tool(), report(scenario)]), resume=True)
    assert (directory / "attempt-001.jsonl").read_bytes() == first_journal
    assert (directory / "attempt-002.jsonl").exists()
    assert result["prior_attempts_preserved"] == 1
    assert result["usage_all_attempts"]["model_requests"] == 4
    assert result["usage_all_attempts"]["input_tokens_known"] == 30
    assert result["usage_all_attempts"]["input_usage_missing_calls"] == 1


def test_truncated_abandoned_journal_is_preserved_and_disclosed(tmp_path, scenario):
    with pytest.raises(KeyboardInterrupt):
        experiment(tmp_path, Scripted([KeyboardInterrupt()]))
    path = tmp_path / "run/episodes/case-0001-budget-001/attempt-001.jsonl"
    with path.open("ab") as stream:
        stream.write(b'{"kind":')
    result = experiment(tmp_path, Scripted([tool(), report(scenario)]), resume=True)
    assert result["unreadable_journal_lines"] == 1
    assert path.read_bytes().endswith(b'{"kind":')


@pytest.mark.parametrize("changes", [{"budgets": (2,)}, {"episode_options": {"max_model_turns": 8}}])
def test_resume_rejects_configuration_changes(tmp_path, scenario, changes):
    experiment(tmp_path, Scripted([tool(), report(scenario)]))
    with pytest.raises(RunError, match="Resume configuration"):
        experiment(tmp_path, Scripted([]), resume=True, **changes)


def test_saved_manifest_and_result_corruption_are_rejected(tmp_path, scenario):
    experiment(tmp_path, Scripted([tool(), report(scenario)]))
    manifest_path = tmp_path / "run/run.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["config"]["budgets"] = [20]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(RunError, match="Invalid saved run manifest"):
        summarize(tmp_path / "run")


def test_run_lock_prevents_two_writers_and_releases_after_exception(tmp_path):
    with pytest.raises(RuntimeError):
        with run_lock(tmp_path):
            with pytest.raises(RunError, match="Another process"):
                with run_lock(tmp_path):
                    pytest.fail("second writer acquired lock")
            raise RuntimeError("test interruption")
    with run_lock(tmp_path):
        pass


def test_atomic_write_failure_preserves_previous_result(tmp_path, monkeypatch):
    path = tmp_path / "result.json"
    atomic_json(path, {"previous": True})
    def failed_replace(*args):
        raise OSError("test disk failure")
    monkeypatch.setattr("inquest.runner.os.replace", failed_replace)
    with pytest.raises(OSError):
        atomic_json(path, {"previous": False})
    assert json.loads(path.read_text()) == {"previous": True}
    assert not list(tmp_path.glob(".pending-*"))


def test_wilson_interval_includes_uncertainty_at_extremes():
    assert wilson(0, 0) is None
    low, high = wilson(0, 16)
    assert low == 0 and 0 < high < 0.3
    low, high = wilson(16, 16)
    assert 0.7 < low < 1 and high == pytest.approx(1)


def test_cli_offline_run_summary_replay_and_resume(tmp_path, capsys):
    output = tmp_path / "cli-run"
    args = ["run", "--suite", str(SUITE), "--set", "holdout", "--backend", "heuristic",
            "--budgets", "5", "--case-limit", "1", "--output", str(output), "--allow-dirty", "--progress"]
    assert main(args) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["kind"] == "offline_heuristic_evaluation"
    assert "case-0001-budget-005:" in captured.err
    assert main(args + ["--resume"]) == 0
    assert capsys.readouterr().err == ""
    assert main(["replay", "--run-dir", str(output), "--job-id", "case-0001-budget-005"]) == 0
    replay = json.loads(capsys.readouterr().out)
    assert any(event["kind"] == "observation" for event in replay["events"])
    assert main(["replay", "--run-dir", str(output), "--job-id", "../escape"]) == 2
    assert "Unknown job" in capsys.readouterr().err


@pytest.mark.parametrize("change", ["missing_brier", "wrong_case", "bad_status", "missing_journal"])
def test_corrupt_completed_results_are_not_silently_skipped(tmp_path, scenario, change):
    experiment(tmp_path, Scripted([tool(), report(scenario)]))
    directory = tmp_path / "run/episodes/case-0001-budget-001"
    path = directory / "result.json"
    result = json.loads(path.read_text())
    if change == "missing_brier":
        del result["score"]["brier"]
    elif change == "wrong_case":
        result["score"]["scenario"] = "another-case"
    elif change == "bad_status":
        result["status"] = []
    else:
        (directory / "attempt-001.jsonl").unlink()
    path.write_text(json.dumps(result))
    with pytest.raises(RunError, match="Invalid saved result"):
        experiment(tmp_path, Scripted([]), resume=True)


def test_changed_model_identity_is_rejected_on_resume(tmp_path, scenario):
    experiment(tmp_path, Scripted([tool(), report(scenario)]))
    class Changed(Scripted):
        def identity(self):
            return {"kind": "scripted_test_fixture", "is_model": True, "revision": "different"}
    with pytest.raises(RunError, match="Resume configuration"):
        experiment(tmp_path, Changed([]), resume=True)
