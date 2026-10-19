"""Authored-data integrity, clue reachability, isolation, and legacy compatibility."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from inquest.env import InvestigationEnv
from inquest.frozen import load_frozen_set
from inquest.grader import grade
from inquest.scenario import FAULTS, Scenario
from scripts.build_authored_v1 import build, construct

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "datasets/authored-v1"
BOOK = json.loads((SUITE / "casebook.json").read_text())


def forbidden(*args, **kwargs):
    raise AssertionError("Authored inputs must not call procedural construction")


def test_balanced_authored_set_has_no_generator_seed(monkeypatch):
    monkeypatch.setattr("inquest.scenario.generate", forbidden)
    monkeypatch.setattr("inquest.generate", forbidden)
    monkeypatch.setattr("random.Random", forbidden)
    cases = load_frozen_set(SUITE, "holdout")
    assert len(cases) == 16
    assert Counter(s.fault_type for s in cases) == Counter({fault: 2 for fault in FAULTS})
    for fault in FAULTS:
        assert {s.difficulty for s in cases if s.fault_type == fault} == {"medium", "hard"}
    assert all(s.origin == "authored" and s.seed is None and s.split == "holdout" for s in cases)


@pytest.mark.parametrize("index", range(16))
def test_authored_clues_distractors_and_grader_work_through_tools(index):
    scenario = load_frozen_set(SUITE, "holdout")[index]
    case = BOOK["cases"][index]
    assert case["narrative"] and case["distractors"]
    assert any(p["role"] == "counterevidence" for p in case["probes"])
    env = InvestigationEnv(scenario, max_steps=len(case["probes"]))
    cited = []
    for probe in case["probes"]:
        observation = env.call(probe["tool"], **probe["args"])
        assert observation.error is None
        assert probe["contains"] in observation.text
        if probe["role"] == "support":
            cited.append(observation.id)
    assert len(cited) >= 2
    result = grade(scenario, env, {
        "service": scenario.root_service, "fault_type": scenario.fault_type,
        "fix": deepcopy(scenario.fix), "confidence": 0.5, "evidence": cited,
    })
    # Evaluator-authored reports check the contract, not agent performance.
    assert result["success"] and result["evidence_relevant_success"]
    assert result["steps"] == len(case["probes"])
    scenario.meta["private_note"] = "PRIVATE_AUTHORED_METADATA"
    env = InvestigationEnv(scenario)
    for tool, args in [
        ("list_services", {}), ("get_alerts", {}),
        ("query_metric", {"service": scenario.root_service, "metric": "error_rate"}),
        ("search_logs", {"service": scenario.root_service}), ("get_events", {}),
        ("get_event", {"event_id": scenario.events[0]["id"]}),
        ("health_check", {"service": scenario.root_service}), ("get_trace", {}),
    ]:
        assert env.call(tool, **args).error is None
    transcript = json.dumps([asdict(o) for o in env.obs])
    for hidden in (scenario.id, "PRIVATE_AUTHORED_METADATA", '"root_service"', '"fault_type"',
                   '"gold_tools"', '"gold_services"', '"origin"', '"seed"'):
        assert hidden not in transcript
    for service in case["missing_logs"]:
        assert not scenario.logs[service]


@pytest.mark.parametrize("field,value", [
    ("seed", 7), ("seed", False), ("split", "dev"), ("origin", "unknown"),
    ("origin", None), ("id", "../escape"), ("id", "authored-v1-1"),
    ("difficulty", "extreme"), ("difficulty", []),
])
def test_authored_identity_is_explicit_and_strict(field, value):
    payload = json.loads((SUITE / "holdout.jsonl").read_text().splitlines()[0])
    payload[field] = value
    with pytest.raises(ValueError):
        Scenario.from_json(json.dumps(payload))


def test_origin_cannot_be_omitted_to_bypass_generated_identity_rules():
    payload = json.loads((SUITE / "holdout.jsonl").read_text().splitlines()[0])
    del payload["origin"]
    with pytest.raises(ValueError):
        Scenario.from_json(json.dumps(payload))


@pytest.fixture
def copied_suite(tmp_path):
    target = tmp_path / "suite"
    shutil.copytree(SUITE, target)
    return target


@pytest.mark.parametrize("name", ["manifest.json", "holdout.jsonl", "casebook.json", "authoring.json"])
def test_changed_authored_bytes_are_rejected(copied_suite, name):
    path = copied_suite / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        load_frozen_set(copied_suite, "holdout")


def rewrite_catalog(directory):
    names = [line.split("  ")[1] for line in (directory / "SHA256SUMS").read_text().splitlines()]
    (directory / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256((directory / name).read_bytes()).hexdigest()}  {name}\n" for name in names))


@pytest.mark.parametrize("change", ["order", "labels", "record_type"])
def test_casebook_is_bound_to_loaded_cases(copied_suite, change):
    book = json.loads((copied_suite / "casebook.json").read_text())
    if change == "order":
        book["cases"].reverse()
    elif change == "labels":
        book["cases"][0]["root_service"] = "gateway"
    else:
        book["cases"][0] = None
    (copied_suite / "casebook.json").write_text(json.dumps(book))
    rewrite_catalog(copied_suite)
    with pytest.raises(ValueError, match="[Cc]asebook"):
        load_frozen_set(copied_suite, "holdout")


@pytest.mark.parametrize("directory,name", [("authored-v1", "test-hard"), ("smoke-v1", "holdout")])
def test_suite_types_cannot_be_mixed(directory, name):
    with pytest.raises(ValueError, match="does not belong"):
        load_frozen_set(ROOT / "datasets" / directory, name)


def test_authored_renderer_reproduces_data_without_generator_or_templates(tmp_path, monkeypatch):
    monkeypatch.setattr("inquest.scenario.generate", forbidden)
    monkeypatch.setattr("inquest.scenario._signal", forbidden)
    monkeypatch.setattr("inquest.scenario._fmt", forbidden)
    monkeypatch.setattr("inquest.scenario.T", {})
    monkeypatch.setattr("random.Random", forbidden)
    target = tmp_path / "render"
    build(SUITE / "authoring.json", target)
    for name in ("holdout.jsonl", "casebook.json", "authoring.json"):
        assert (target / name).read_bytes() == (SUITE / name).read_bytes()
    assert len(load_frozen_set(target, "holdout")) == 16
    previous = {p.name: p.read_bytes() for p in target.iterdir()}
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        build(SUITE / "authoring.json", target)
    assert previous == {p.name: p.read_bytes() for p in target.iterdir()}


def test_generated_serialization_remains_identical_to_frozen_smoke_bytes():
    for path in (ROOT / "datasets/smoke-v1").glob("*.jsonl"):
        for line in path.read_text().splitlines():
            scenario = Scenario.from_json(line)
            assert scenario.origin == "generated"
            assert scenario.to_json() == line


def test_authored_profiles_do_not_implicitly_depend_on_fault_dispatch():
    source = json.loads((SUITE / "authoring.json").read_text())
    original = construct(source)
    # Changing the label alone cannot synthesize different observations.
    source["cases"][0]["fault_type"] = "bad_deploy"
    source["cases"][0]["fix"]["action"] = "rollback"
    relabeled = construct(source)
    assert relabeled[0].metrics == original[0].metrics
    assert relabeled[0].logs == original[0].logs
    assert relabeled[0].events == original[0].events
