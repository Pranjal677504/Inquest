"""Fresh-case reachability, causal review contracts, and frozen-policy isolation."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from inquest.agent_protocol import system_prompt
from inquest.env import InvestigationEnv
from inquest.frozen import load_frozen_set
from inquest.grader import grade
from inquest.scenario import FAULTS, FIX_ACTION, Scenario
from scripts.build_authored_v2 import FROZEN_V2_PROMPT, build, construct, review

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "datasets/authored-v2"
SOURCE = json.loads((SUITE / "authoring.json").read_text())


def forbidden(*args, **kwargs):
    raise AssertionError("Fresh cases must not call a generator or provider")


def test_fresh_set_is_balanced_and_prompt_predates_cases(monkeypatch):
    monkeypatch.setattr("inquest.scenario.generate", forbidden)
    monkeypatch.setattr("random.Random", forbidden)
    scenarios = load_frozen_set(SUITE, "holdout")
    assert len(scenarios) == 16
    assert Counter(s.fault_type for s in scenarios) == Counter({f: 2 for f in FAULTS})
    for fault in FAULTS:
        assert sorted(s.difficulty for s in scenarios if s.fault_type == fault) == ["hard", "medium"]
    assert hashlib.sha256(system_prompt("v2").encode()).hexdigest() == FROZEN_V2_PROMPT
    original = load_frozen_set(ROOT / "datasets/authored-v1", "holdout")
    def telemetry(s):
        return json.dumps({k: getattr(s, k) for k in ("metrics", "logs", "events", "traces", "health")}, sort_keys=True)
    assert not {s.id for s in original} & {s.id for s in scenarios}
    assert not {telemetry(s) for s in original} & {telemetry(s) for s in scenarios}
    assert sum(bool(c["missing_logs"]) for c in SOURCE["cases"]) == 4


@pytest.mark.parametrize("index", range(16))
def test_five_call_path_reaches_support_and_counterevidence_without_leaking_labels(index):
    scenario = load_frozen_set(SUITE, "holdout")[index]
    case = SOURCE["cases"][index]
    env = InvestigationEnv(scenario, max_steps=5)
    citations = []
    assert len(case["probes"]) == 5
    assert case["probes"][0]["tool"] == "get_alerts"
    for probe in case["probes"]:
        ob = env.call(probe["tool"], **probe["args"])
        assert ob.error is None
        assert probe["contains"] in ob.text
        if probe["role"] == "support":
            citations.append(ob.id)
    assert len(citations) >= 2 and env.steps_left == 0
    report = {"service": scenario.root_service, "fault_type": scenario.fault_type,
              "fix": deepcopy(scenario.fix), "confidence": 0.5, "evidence": citations}
    score = grade(scenario, env, report)
    assert score["success"] and score["evidence_relevant_success"]
    # A wrong but structurally valid diagnosis is not rescued by valid citations.
    wrong_fault = FAULTS[(FAULTS.index(scenario.fault_type) + 1) % len(FAULTS)]
    wrong = {**report, "fault_type": wrong_fault,
             "fix": {"action": FIX_ACTION[wrong_fault], "target": scenario.root_service}}
    incorrect = grade(scenario, env, wrong)
    assert incorrect["report_valid"] and not incorrect["success"]
    for service in case["missing_logs"]:
        assert scenario.logs[service] == []
    public = json.dumps([asdict(ob) for ob in env.obs])
    for hidden in (scenario.id, '"root_service"', '"fault_type"', '"gold_services"', '"gold_tools"'):
        assert hidden not in public


def test_fresh_cause_specific_signals_have_expected_direction():
    cases = load_frozen_set(SUITE, "holdout")
    # Distinguishing telemetry rather than the label alone supports these cases.
    for index in (8, 9):
        scenario = cases[index]
        series = scenario.metrics[scenario.root_service]["rps"]
        assert series[-1] == 12 * series[0]
    leak = cases[4].metrics["auth"]["memory"]
    assert leak[104] > 2 * leak[0] and leak[80] < leak[104]
    for index in (6, 7):
        assert cases[index].health[cases[index].root_service]["cert_days_left"] < 0
    for index in (12, 13):
        assert cases[index].health[cases[index].root_service]["status"] == "down"


def test_new_health_evidence_is_counted_without_changing_legacy_metadata():
    scenario = load_frozen_set(SUITE, "holdout")[12]
    env = InvestigationEnv(scenario, max_steps=1)
    ob = env.call("health_check", service="cache")
    score = grade(scenario, env, {"service": "cache", "fault_type": "dependency_outage",
                  "fix": {"action": "failover", "target": "cache"}, "confidence": 0.5, "evidence": [ob.id]})
    assert score["success"] and score["evidence_relevant_success"]
    old = load_frozen_set(ROOT / "datasets/authored-v1", "holdout")[14]
    assert old.gold_tools == ["logs"]


def test_fresh_renderer_reproduces_all_frozen_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr("inquest.scenario.generate", forbidden)
    monkeypatch.setattr("inquest.scenario._signal", forbidden)
    monkeypatch.setattr("random.Random", forbidden)
    out = tmp_path / "fresh"
    build(SUITE / "authoring.json", out)
    for path in out.iterdir():
        assert path.read_bytes() == (SUITE / path.name).read_bytes()
    assert len(load_frozen_set(out, "holdout")) == 16
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        build(SUITE / "authoring.json", out)


@pytest.mark.parametrize("mutation", ["unreachable", "budget", "counterevidence", "policy", "balance"])
def test_review_rejects_broken_experiment_contract(mutation):
    source = deepcopy(SOURCE)
    if mutation == "unreachable":
        source["cases"][0]["probes"][2]["contains"] = "UNREACHABLE_CLUE"
    elif mutation == "budget":
        source["cases"][0]["probes"].append(deepcopy(source["cases"][0]["probes"][0]))
    elif mutation == "counterevidence":
        source["cases"][0]["probes"][-1]["role"] = "support"
    elif mutation == "policy":
        source["evaluation_contract"]["prompt_sha256"] = "0" * 64
    else:
        source["cases"][0]["difficulty"] = "hard"
    with pytest.raises(ValueError):
        review(source, construct(source))


@pytest.mark.parametrize("name", ["manifest.json", "holdout.jsonl", "casebook.json", "authoring.json"])
def test_fresh_suite_rejects_modified_bytes(tmp_path, name):
    out = tmp_path / "suite"
    shutil.copytree(SUITE, out)
    path = out / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        load_frozen_set(out, "holdout")


def test_suite_identity_cannot_be_relabeled_while_retaining_other_version_cases(tmp_path):
    out = tmp_path / "suite"
    shutil.copytree(ROOT / "datasets/authored-v1", out)
    manifest = json.loads((out / "manifest.json").read_text())
    manifest["suite_id"] = "inquest-authored-v2"
    (out / "manifest.json").write_text(json.dumps(manifest))
    names = [line.split("  ")[1] for line in (out / "SHA256SUMS").read_text().splitlines()]
    (out / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256((out / name).read_bytes()).hexdigest()}  {name}\n" for name in names))
    with pytest.raises(ValueError, match="incompatible scenario"):
        load_frozen_set(out, "holdout")


@pytest.mark.parametrize("bad_id", ["authored-v3-001", "authored-v2-1", "../authored-v2-001"])
def test_new_scenario_identity_remains_bounded(bad_id):
    payload = json.loads((SUITE / "holdout.jsonl").read_text().splitlines()[0])
    payload["id"] = bad_id
    with pytest.raises(ValueError, match="authored scenario ID"):
        Scenario.from_json(json.dumps(payload))
