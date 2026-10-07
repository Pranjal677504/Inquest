"""Manually inspect one frozen incident using only budgeted tool observations."""

from dataclasses import asdict
import json
from pathlib import Path

from inquest.env import InvestigationEnv
from inquest.frozen import load_frozen_set


def main():
    directory = Path(__file__).resolve().parents[1] / "datasets" / "smoke-v1"
    # The evaluator chooses the case; only tool observations are printed.
    scenario = load_frozen_set(directory, "test-easy")[7]
    env = InvestigationEnv(scenario, max_steps=5, max_lines=5)
    queries = [
        ("get_alerts", {}),
        ("get_events", {"service": "postgres"}),
        ("query_metric", {"service": "postgres", "metric": "lock_wait_ms"}),
        ("search_logs", {"service": "postgres", "level": "WARN", "limit": 5}),
        ("get_trace", {"status": "timeout"}),
    ]
    for tool, args in queries:
        print(json.dumps(asdict(env.call(tool, **args)), indent=2))
    print(f"Steps used: {env.steps}; steps left: {env.steps_left}")


if __name__ == "__main__":
    main()
