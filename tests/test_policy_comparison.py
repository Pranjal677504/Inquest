"""Policy identity, historical compatibility, and paired saved-result checks."""
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
from inquest.runner import EpisodeConfig, RunError, canonical, code_identity, run_episode, run_experiment

SUITE = Path(__file__).resolve().parents[1] / "datasets/authored-v1"


class Scripted:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.messages = []
    def identity(self):
        return {"kind": "scripted", "is_model": True, "requested_model": "fixture"}
    def complete(self, messages, emit):
        self.messages.append(deepcopy(messages))
        return ModelReply(next(self.replies), "fixture", 10, 10)


def test_v1_prompt_is_byte_identical_to_the_recorded_live_reference():
    assert system_prompt() == system_prompt("v1")
    assert hashlib.sha256(system_prompt("v1").encode()).hexdigest() == "ed68047e265416ec7d41bdebf7fbeec362f019c60aae3611403d766ddcd081b6"
    with pytest.raises(ValueError):
        EpisodeConfig(policy="unknown")


def test_v2_reaches_backend_and_recovers_invalid_envelope_without_silent_repair():
    case = load_frozen_set(SUITE, "holdout")[0]
    report = {"service": case.root_service, "fault_type": case.fault_type,
              "fix": case.fix, "confidence": 0.6, "evidence": ["o1"]}
    backend = Scripted(['{"kind":"tool","tool":"get_alerts","service":"auth"}',
                        '{"kind":"tool","tool":"get_alerts","args":{}}',
                        json.dumps({"kind": "report", "report": report})])
    events = []
    result = run_episode(case, backend, EpisodeConfig(max_steps=1, policy="v2"),
                         lambda k, b: events.append({"kind": k, **b}))
    assert backend.messages[0][0]["content"] == system_prompt("v2")
    assert "inside args" in backend.messages[1][-1]["content"]
    assert result["protocol_errors"] == 1 and result["score"]["steps"] == 1
    assert result["score"]["success"]
    assert sum(e["kind"] == "observation" for e in events) == 1


@pytest.fixture
def runs(tmp_path, monkeypatch):
    identity = {**code_identity(), "dirty": False}
    monkeypatch.setattr("inquest.runner.code_identity", lambda: identity)
    cases = load_frozen_set(SUITE, "holdout")[:2]
    paths = [tmp_path / "v1", tmp_path / "v2"]
    for index, path in enumerate(paths):
        replies = []
        for number, case in enumerate(cases):
            correct = number == index
            replies += ['{"kind":"tool","tool":"get_alerts","args":{}}', json.dumps({
                "kind": "report", "report": {
                    "service": case.root_service if correct else "gateway",
                    "fault_type": case.fault_type, "fix": case.fix,
                    "confidence": 0.8, "evidence": ["o1"]}})]
        run_experiment(suite=SUITE, set_name="holdout", backend=Scripted(replies), budgets=(1,),
                       output=path, case_limit=2, episode_options={"policy": f"v{index + 1}"})
    return paths


def rewrite_config(path, change):
    manifest_path = path / "run.json"
    manifest = json.loads(manifest_path.read_text())
    change(manifest["config"])
    manifest["fingerprint"] = hashlib.sha256(canonical(manifest["config"]).encode()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    for file in (path / "episodes").glob("*/result.json"):
        result = json.loads(file.read_text())
        result["fingerprint"] = manifest["fingerprint"]
        file.write_text(json.dumps(result))


def test_comparison_reports_improvements_and_regressions_and_supports_historical_v1(runs, capsys):
    rewrite_config(runs[0], lambda c: c["episode_options"].pop("policy"))
    assert main(["compare", "--baseline", str(runs[0]), "--candidate", str(runs[1])]) == 0
    result = json.loads(capsys.readouterr().out)
    group = result["groups"]["budget_1/all"]
    assert result["baseline"]["policy"] == "v1" and result["candidate"]["policy"] == "v2"
    assert group["success_delta_percentage_points"] == 0
    assert group["regressions"] == ["authored-v1-001"]
    assert group["improvements"] == ["authored-v1-002"]


@pytest.mark.parametrize("change", [
    lambda c: c["suite"].update(data_sha256="0" * 64),
    lambda c: c["code"]["package_sha256"].update(**{"grader.py": "0" * 64}),
    lambda c: c["backend"].update(requested_model="different"),
    lambda c: c["episode_options"].update(max_model_turns=99),
    lambda c: c["code"].update(dirty=True),
    lambda c: c["code"].update(dirty=None),
])
def test_comparison_rejects_non_policy_changes(runs, change):
    rewrite_config(runs[1], change)
    with pytest.raises(RunError):
        compare_runs(*runs)


def test_comparison_does_not_drop_unfinished_cases(runs):
    (runs[1] / "episodes/case-0002-budget-001/result.json").unlink()
    with pytest.raises(RunError, match="Complete both"):
        compare_runs(*runs)
