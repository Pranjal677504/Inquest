import json
import random
from statistics import mean

import pytest

from inquest import Scenario, generate, iter_scenarios
from inquest.scenario import DIFFICULTY, FAULTS, FAULT_TARGETS, HORIZON, SPLITS
from inquest.topology import SERVICES, callees_with_hops


@pytest.mark.parametrize("split", SPLITS)
@pytest.mark.parametrize("difficulty", DIFFICULTY)
@pytest.mark.parametrize("seed", range(8))
def test_all_faults_round_trip_with_complete_telemetry(seed, difficulty, split):
    scenario = generate(seed, difficulty, split)
    assert scenario.fault_type == FAULTS[seed]
    assert scenario.root_service in FAULT_TARGETS[scenario.fault_type]
    assert set(scenario.metrics) == set(SERVICES)
    assert all(len(series) == HORIZON for metrics in scenario.metrics.values() for series in metrics.values())
    assert Scenario.from_json(scenario.to_json()) == scenario
    assert generate(seed, difficulty, split).to_json() == scenario.to_json()
    assert all("root span" not in span["note"] for trace in scenario.traces for span in trace["spans"])


def test_generation_does_not_change_global_random_state():
    before = random.getstate()
    generate(123)
    assert random.getstate() == before


def test_seed_range_and_split_identity():
    cases = list(iter_scenarios("test", 3, "hard", start=7))
    assert [s.id for s in cases] == ["test-hard-7", "test-hard-8", "test-hard-9"]
    assert list(iter_scenarios("dev", 0)) == []
    assert generate(7, split="dev").metrics != generate(7, split="test").metrics


@pytest.mark.parametrize("options", [
    {"seed": -1}, {"seed": True}, {"seed": 1.5}, {"seed": "1"},
    {"difficulty": "extreme"}, {"difficulty": []}, {"split": "train"}, {"split": None},
])
def test_invalid_generation_options(options):
    settings = {"seed": 0, **options}
    with pytest.raises(ValueError):
        generate(**settings)


@pytest.mark.parametrize("options", [{"n": -1}, {"n": False}, {"start": -1}, {"split": "invalid"}])
def test_invalid_seed_ranges(options):
    settings = {"split": "dev", "n": 1, **options}
    with pytest.raises(ValueError):
        list(iter_scenarios(**settings))


@pytest.mark.parametrize("field,value", [
    ("id", "wrong"), ("seed", -1), ("onset", HORIZON),
    ("root_service", "unknown"), ("fault_type", "unknown"),
    ("fix", {"action": "scale_up", "target": "postgres"}),
    ("metrics", {}), ("logs", {}), ("events", {}), ("traces", {}),
    ("gold_services", ["unknown"]), ("gold_tools", [1]), ("meta", []),
])
def test_malformed_bundle_fields(field, value):
    payload = json.loads(generate(7).to_json())
    payload[field] = value
    with pytest.raises(ValueError):
        Scenario.from_json(json.dumps(payload))


@pytest.mark.parametrize("text", ["[]", "null", "{}", "{", '{"seed": NaN}'])
def test_invalid_json_documents(text):
    with pytest.raises(ValueError):
        Scenario.from_json(text)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True, "12"])
def test_invalid_metric_sample(value):
    payload = json.loads(generate(7).to_json())
    payload["metrics"]["postgres"]["cpu"][0] = value
    with pytest.raises(ValueError):
        Scenario.from_json(json.dumps(payload))


def test_truncated_metrics_and_invalid_trace_timestamp():
    payload = json.loads(generate(7).to_json())
    payload["metrics"]["postgres"]["cpu"].pop()
    with pytest.raises(ValueError, match="120 samples"):
        Scenario.from_json(json.dumps(payload))
    payload = json.loads(generate(7).to_json())
    payload["traces"][0]["t"] = -1
    with pytest.raises(ValueError, match="timestamp"):
        Scenario.from_json(json.dumps(payload))


def test_migration_causes_lock_contention_and_caller_errors():
    scenario = generate(7, "easy")
    assert scenario.root_service == "postgres"
    locks = scenario.metrics["postgres"]["lock_wait_ms"]
    assert max(locks[:scenario.onset]) < min(locks[scenario.onset:])
    assert scenario.metrics["orders"]["error_rate"][scenario.onset + 1] > 2
    assert any(event["kind"] == "migration" for event in scenario.events)


def test_traffic_surge_reaches_callees():
    scenario = generate(5, "easy")
    root_rps = scenario.metrics[scenario.root_service]["rps"]
    assert root_rps[-1] > 2 * root_rps[scenario.onset - 1]
    for service in callees_with_hops(scenario.root_service):
        rps = scenario.metrics[service]["rps"]
        assert mean(rps[scenario.onset:]) > 1.15 * mean(rps[:scenario.onset])
