from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from inquest import Scenario
from inquest.env import BudgetExceeded, InvestigationEnv, TOOL_SPECS
from inquest.frozen import load_frozen_set
from inquest.topology import SERVICES

SUITE = Path(__file__).resolve().parents[1] / "datasets" / "smoke-v1"


@pytest.fixture(scope="module")
def cases():
    return load_frozen_set(SUITE, "test-easy")


@pytest.fixture
def case(cases):
    return deepcopy(cases[7])


def test_budget_and_observation_ids(case):
    env = InvestigationEnv(case, max_steps=2)
    first = env.call("list_services")
    invalid = env.call("missing")
    assert (first.id, invalid.id) == ("o1", "o2")
    assert invalid.error == "unknown_tool"
    assert env.steps == 2 and env.steps_left == 0
    assert len(env.obs) == 2
    assert env.tokens_used() == first.tokens + invalid.tokens
    with pytest.raises(BudgetExceeded):
        env.call("get_alerts")
    assert env.steps == 2 and len(env.obs) == 2


def test_no_budget_bypass(case):
    env = InvestigationEnv(case, max_steps=1)
    invalid = env.call("list_services", charge=False)
    assert invalid.error == "invalid_arguments"
    assert env.steps_left == 0
    with pytest.raises(BudgetExceeded):
        env.call("list_services")


def test_zero_budget(case):
    env = InvestigationEnv(case, max_steps=0)
    with pytest.raises(BudgetExceeded):
        env.call("get_alerts")
    assert env.obs == ()


@pytest.mark.parametrize("settings", [
    {"max_steps": -1}, {"max_steps": True}, {"max_steps": 1.5},
    {"max_lines": 0}, {"max_lines": False}, {"max_lines": "5"},
])
def test_invalid_settings(case, settings):
    with pytest.raises(ValueError):
        InvestigationEnv(case, **settings)


@pytest.mark.parametrize("tool,args", [
    ("query_metric", {"service": "missing", "metric": "cpu"}),
    ("query_metric", {"service": "orders", "metric": []}),
    ("query_metric", {"service": "orders", "metric": "lock_wait_ms"}),
    ("query_metric", {"service": "orders"}),
    ("query_metric", {"service": "orders", "metric": "cpu", "extra": 1}),
    ("search_logs", {"service": "orders", "limit": 0}),
    ("search_logs", {"service": "orders", "limit": True}),
    ("search_logs", {"service": "orders", "limit": "3"}),
    ("search_logs", {"service": "orders", "query": None}),
    ("search_logs", {"service": "orders", "level": "DEBUG"}),
    ("get_events", {"service": []}),
    ("get_event", {"event_id": "not-found"}),
    ("get_event", {"event_id": None}),
    ("health_check", {"service": None}),
    ("get_trace", {"status": "invalid"}),
    ("get_trace", {"status": None}),
])
def test_invalid_requests_are_charged(case, tool, args):
    env = InvestigationEnv(case)
    observation = env.call(tool, **args)
    assert observation.error == "invalid_arguments"
    assert observation.id == "o1" and env.steps == 1


def test_metrics_and_derived_alerts(case):
    env = InvestigationEnv(case)
    ob = env.call("query_metric", service="postgres", metric="lock_wait_ms")
    assert ob.data["recent"] > ob.data["baseline"] * 100
    assert ob.data["change_point"] is not None
    alerts = env.call("get_alerts").data["alerts"]
    assert any(a["service"] == "orders" for a in alerts)


def test_alert_requires_three_full_samples(case):
    for metrics in case.metrics.values():
        metrics["error_rate"] = [0.1] * 120
        metrics["latency_p99"] = [100] * 120
    case.metrics["orders"]["error_rate"][-2:] = [3, 3]
    assert InvestigationEnv(case).call("get_alerts").data["alerts"] == []
    case.metrics["orders"]["error_rate"][-3:] = [3, 3, 3]
    alerts = InvestigationEnv(case).call("get_alerts").data["alerts"]
    assert alerts == [{"service": "orders", "alert": "error_rate>2%", "since": 117, "value": 3}]


def test_literal_log_filter_and_limits(case):
    case.logs["orders"] = [
        {"t": t, "level": "WARN" if t % 2 else "INFO", "msg": "Pool exhausted [client.*]"}
        for t in range(10)
    ]
    env = InvestigationEnv(case, max_lines=2)
    ob = env.call("search_logs", service="orders", query="POOL", level="warn", limit=99)
    assert ob.data["total"] == 5
    assert [line["t"] for line in ob.data["lines"]] == [7, 9]
    assert env.call("search_logs", service="orders", query=".*").data["total"] == 10
    assert env.call("search_logs", service="orders", query="[invalid(").data["total"] == 0


def test_events_are_bounded_newest_first_and_detail_is_separate(case):
    env = InvestigationEnv(case, max_lines=1)
    listed = env.call("get_events")
    assert len(listed.data["events"]) == 1
    event = listed.data["events"][0]
    assert event["t"] == max(e["t"] for e in case.events)
    assert "detail" not in event
    full = env.call("get_event", event_id=event["id"])
    assert full.data["event"]["detail"]


def test_trace_cycles_and_round_trip_replay(case):
    expected = [tr for tr in case.traces if tr["t"] >= 80 and any(s["status"] == "timeout" for s in tr["spans"])]
    assert expected
    first = InvestigationEnv(case, max_steps=len(expected) + 1)
    second = InvestigationEnv(Scenario.from_json(case.to_json()), max_steps=len(expected) + 1)
    observed = [first.call("get_trace", status="timeout") for _ in range(len(expected) + 1)]
    replayed = [second.call("get_trace", status="timeout") for _ in range(len(expected) + 1)]
    assert observed == replayed
    assert [o.data["trace"] for o in observed] == expected + [expected[0]]


def test_no_matching_recent_traces(case):
    case.traces = [{"t": 79, "spans": [{"service": "orders", "ms": 1000, "status": "timeout", "note": "request timed out"}]}]
    env = InvestigationEnv(case)
    assert env.call("get_trace", status="timeout").data["trace"] is None
    assert env.call("get_trace", status="ok").data["trace"] is None


def test_failed_trace_requests_do_not_advance_cursor(case):
    expected = [tr for tr in case.traces if tr["t"] >= 80 and any(s["status"] == "timeout" for s in tr["spans"])]
    env = InvestigationEnv(case)
    assert env.call("get_trace", status="bogus").error == "invalid_arguments"
    assert env.call("get_trace", status="timeout").data["trace"] == expected[0]
    assert env.call("get_trace", status="timeout", extra=True).error == "invalid_arguments"
    assert env.call("get_trace", status="timeout").data["trace"] == expected[1 % len(expected)]


def test_snapshot_and_detached_observations(case):
    env = InvestigationEnv(case)
    before = env.call("health_check", service="postgres")
    case.health["postgres"]["status"] = "CHANGED"
    before.data["status"] = "EDITED"
    env.obs[0].data["status"] = "EDITED AGAIN"
    after = env.call("health_check", service="postgres")
    assert after.data["status"] not in ("CHANGED", "EDITED", "EDITED AGAIN")
    assert env.obs[0].data["status"] == after.data["status"]


def _probe_all(case):
    env = InvestigationEnv(case, max_steps=100)
    calls = [("list_services", {}), ("get_alerts", {}), ("get_events", {})]
    for service in SERVICES:
        calls += [("health_check", {"service": service}), ("search_logs", {"service": service})]
        calls += [("query_metric", {"service": service, "metric": name}) for name in case.metrics[service] if name != "root_service"]
        calls.append(("get_events", {"service": service}))
    calls += [("get_event", {"event_id": event["id"]}) for event in case.events]
    calls += [("get_trace", {"status": status}) for status in ("ok", "error", "timeout")]
    return [env.call(tool, **args) for tool, args in calls]


def test_observations_do_not_depend_on_construction_labels(case):
    original = _probe_all(case)
    changed = deepcopy(case)
    for field in ("id", "seed", "onset", "root_service", "fault_type", "fix", "gold_tools", "gold_services", "meta", "split", "difficulty"):
        setattr(changed, field, "PRIVATE-LABEL-SENTINEL")
    for health in changed.health.values():
        health["root_service"] = "PRIVATE-LABEL-SENTINEL"
    for metrics in changed.metrics.values():
        metrics["root_service"] = [999] * 120
    for logs in changed.logs.values():
        for log in logs:
            log["meta"] = "PRIVATE-LABEL-SENTINEL"
    for event in changed.events:
        event["gold"] = "PRIVATE-LABEL-SENTINEL"
    for trace in changed.traces:
        trace["gold"] = "PRIVATE-LABEL-SENTINEL"
        for span in trace["spans"]:
            span["gold"] = "PRIVATE-LABEL-SENTINEL"
    observations = _probe_all(changed)
    assert observations == original
    assert "PRIVATE-LABEL-SENTINEL" not in json.dumps([asdict(o) for o in observations])
    assert not hasattr(InvestigationEnv(case), "sc")


@pytest.mark.parametrize("split", ["dev", "test", "ood"])
@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_all_tools_on_every_frozen_case(split, difficulty):
    forbidden = {"root_service", "fault_type", "fix", "gold_tools", "gold_services", "meta", "seed", "onset", "split", "difficulty"}
    def inspect(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for nested in value.values():
                inspect(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                inspect(nested)
    for case in load_frozen_set(SUITE, f"{split}-{difficulty}"):
        observations = _probe_all(case)
        assert {o.tool for o in observations} == {spec["name"] for spec in TOOL_SPECS}
        assert all(o.error is None for o in observations)
        inspect([o.data for o in observations])
        text = json.dumps([asdict(o) for o in observations])
        assert case.id not in text and "root span failing" not in text
