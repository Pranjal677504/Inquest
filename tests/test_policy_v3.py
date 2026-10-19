"""V3 plumbing and bounded tool contracts; scripted paths are not LLM accuracy."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from inquest.agent_protocol import system_prompt
from inquest.backends import ModelReply
from inquest.cli import main
from inquest.comparison import compare_runs
from inquest.frozen import load_frozen_set
from inquest.runner import EpisodeConfig, RunError, code_identity, run_episode, run_experiment

SUITE = Path(__file__).resolve().parents[1] / "datasets/authored-v2"


class RecordedFixture:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.messages = []
    def identity(self):
        return {"kind": "scripted", "is_model": True, "requested_model": "fixture"}
    def complete(self, messages, emit):
        self.messages.append(deepcopy(messages))
        return ModelReply(next(self.replies), "fixture", 10, 10)


def tool(name, **args):
    return json.dumps({"kind": "tool", "tool": name, "args": args})


def report(case, evidence, **changes):
    body = {"service": case.root_service, "fault_type": case.fault_type,
            "fix": deepcopy(case.fix), "evidence": evidence, "confidence": 0.5}
    return json.dumps({"kind": "report", "report": {**body, **changes}})


def test_all_policy_hashes_are_stable_and_unknown_policy_rejected():
    expected = {
        "v1": "ed68047e265416ec7d41bdebf7fbeec362f019c60aae3611403d766ddcd081b6",
        "v2": "6c94ffeaf6dbde3eeea84e5d5f1e1f34c24a0b9fd8284bfd13a28a8d9d8a411a",
        "v3": "01cef3e5d0501350a5ec045e55626e701c70473eea65230fe25741729f1a3b88",
    }
    for policy, digest in expected.items():
        assert hashlib.sha256(system_prompt(policy).encode()).hexdigest() == digest
        assert EpisodeConfig(policy=policy).policy == policy
    with pytest.raises(ValueError):
        system_prompt("v4")


@pytest.mark.parametrize("index", [8, 9])
def test_scripted_demand_path_exposes_rps_and_mechanism_within_same_budget(index):
    case = load_frozen_set(SUITE, "holdout")[index]
    service = case.root_service
    log_service = service if index == 8 else "gateway"
    backend = RecordedFixture([
        tool("get_alerts"), tool("query_metric", service=service, metric="rps"),
        tool("search_logs", service=log_service), report(case, ["o2", "o3"]),
    ])
    events = []
    result = run_episode(case, backend, EpisodeConfig(max_steps=5, max_model_turns=8, policy="v3"),
                         lambda kind, body: events.append({"kind": kind, **body}))
    assert backend.messages[0][0]["content"] == system_prompt("v3")
    observations = [e["observation"] for e in events if e["kind"] == "observation"]
    assert observations[1]["data"]["ratio"] == 12
    assert result["score"]["success"] and result["score"]["evidence_relevant_success"]
    assert result["score"]["steps"] == 3 and result["model_turns"] == 4
    assert result["usage"]["model_requests"] == len(backend.messages) == 4
    assert all(m[0]["content"] == system_prompt("v3") for m in backend.messages)
    # Only public tool replies, never evaluator labels or case IDs, reach a model.
    assert case.id not in json.dumps(backend.messages)
    assert '"root_service"' not in json.dumps(backend.messages)


def test_missing_root_logs_can_switch_to_caller_with_bounded_protocol_recovery():
    case = load_frozen_set(SUITE, "holdout")[5]
    backend = RecordedFixture([
        tool("get_alerts"), tool("get_events", service="search"),
        tool("search_logs", service="search"),
        '{"kind":"tool","tool":"search_logs","service":"gateway"}',
        tool("search_logs", service="gateway"),
        tool("query_metric", service="search", metric="rps"),
        report(case, ["o4", "o5"]),
    ])
    events = []
    result = run_episode(case, backend, EpisodeConfig(max_steps=5, max_model_turns=8, policy="v3"),
                         lambda kind, body: events.append({"kind": kind, **body}))
    observations = [e["observation"] for e in events if e["kind"] == "observation"]
    assert observations[2]["data"]["lines"] == []
    assert "closed_since_boot=0" in observations[3]["text"]
    assert observations[4]["data"]["ratio"] == 1
    assert result["score"]["success"] and result["score"]["evidence_relevant_success"]
    assert result["protocol_errors"] == 1 and result["score"]["steps"] == 5
    assert result["model_turns"] == 7
    feedback = json.loads(backend.messages[4][-1]["content"])
    assert feedback["kind"] == "protocol_error" and feedback["steps_left"] == 2
    assert "inside args" in feedback["instruction"]


def test_v3_does_not_silently_replace_an_unsupported_report_or_inflate_score():
    case = load_frozen_set(SUITE, "holdout")[8]
    wrong = {"service": "payments", "fault_type": "bad_deploy",
             "fix": {"action": "rollback", "target": "payments"}, "confidence": 0.95}
    backend = RecordedFixture([tool("get_alerts"), report(case, ["o1"], **wrong)])
    result = run_episode(case, backend, EpisodeConfig(max_steps=5, policy="v3"), lambda *args: None)
    assert result["score"]["report_valid"] and not result["score"]["success"]
    assert result["report"]["confidence"] == 0.95
    assert result["score"]["steps"] == 1 and result["model_turns"] == 2
    # Guidance is advisory. No hidden probe, diagnosis repair or confidence cap.
    assert result["report"]["service"] == "payments"


def test_v3_still_stops_at_protocol_limit_without_executing_invalid_envelopes():
    case = load_frozen_set(SUITE, "holdout")[0]
    invalid = '{"kind":"tool","tool":"get_alerts","args":{},"hypothesis":"extra field"}'
    backend = RecordedFixture([invalid, invalid])
    result = run_episode(case, backend, EpisodeConfig(policy="v3"), lambda *args: None)
    assert result["status"] == "protocol_error" and result["protocol_errors"] == 2
    assert result["score"]["steps"] == 0 and not result["score"]["success"]


def test_v2_v3_runs_compare_with_historical_policy_source_and_strict_resume(tmp_path, monkeypatch, capsys):
    original_identity = {**code_identity(), "dirty": False}
    baseline_identity = deepcopy(original_identity)
    baseline_identity["revision"] = "historical-v2"
    baseline_identity["package_sha256"]["agent_protocol.py"] = "0" * 64
    paths = [tmp_path / "v2", tmp_path / "v3"]
    case = load_frozen_set(SUITE, "holdout")[0]
    for policy, path, identity in zip(("v2", "v3"), paths, (baseline_identity, original_identity)):
        monkeypatch.setattr("inquest.runner.code_identity", lambda identity=identity: identity)
        run_experiment(suite=SUITE, set_name="holdout", backend=RecordedFixture([
            tool("get_alerts"), report(case, ["o1"])]), budgets=(5,), output=path, case_limit=1,
            episode_options={"policy": policy, "max_model_turns": 8})
    comparison = compare_runs(*paths)
    assert comparison["baseline"]["policy"] == "v2" and comparison["candidate"]["policy"] == "v3"
    assert any("v3" in note and "development data" in note for note in comparison["limitations"])
    left, right = [json.loads((path / "run.json").read_text()) for path in paths]
    assert left["config"]["prompt_sha256"] != right["config"]["prompt_sha256"]
    assert left["config"]["suite"] == right["config"]["suite"]
    with pytest.raises(RunError, match="configuration"):
        run_experiment(suite=SUITE, set_name="holdout", backend=RecordedFixture([]), budgets=(5,),
                       output=paths[0], case_limit=1, resume=True,
                       episode_options={"policy": "v3", "max_model_turns": 8})
    assert main(["compare", "--baseline", str(paths[0]), "--candidate", str(paths[1])]) == 0
    assert json.loads(capsys.readouterr().out)["candidate"]["policy"] == "v3"


def test_cli_selects_v3_and_records_identity_without_external_requests(tmp_path, capsys):
    path = tmp_path / "cli-v3"
    assert main(["run", "--suite", str(SUITE), "--set", "holdout", "--backend", "heuristic",
                 "--policy", "v3", "--budgets", "5", "--case-limit", "1", "--max-model-turns", "8",
                 "--allow-dirty", "--output", str(path)]) == 0
    manifest = json.loads((path / "run.json").read_text())
    summary = json.loads(capsys.readouterr().out)
    assert manifest["config"]["episode_options"]["policy"] == "v3"
    assert manifest["config"]["prompt_sha256"] == hashlib.sha256(system_prompt("v3").encode()).hexdigest()
    assert summary["completed_episodes"] == 1 and summary["usage_all_attempts"]["model_requests"] == 0
