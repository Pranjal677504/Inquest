"""Construct one labeled incident and verify JSON replay; no API key needed."""

import hashlib
import json

from inquest import Scenario, generate


def main():
    scenario = generate(seed=7, difficulty="easy", split="dev")
    serialized = scenario.to_json()
    restored = Scenario.from_json(serialized)
    if restored != scenario:
        raise RuntimeError("Incident changed during JSON replay")
    print(json.dumps({
        "scenario": scenario.id,
        "services": len(scenario.metrics),
        "telemetry_minutes": len(scenario.metrics["postgres"]["latency_p99"]),
        "events": len(scenario.events),
        "traces": len(scenario.traces),
        "sha256": hashlib.sha256(serialized.encode()).hexdigest(),
        "round_trip": "identical",
        "construction_labels": {
            "service": scenario.root_service,
            "fault": scenario.fault_type,
            "fix": scenario.fix,
        },
    }, indent=2))


if __name__ == "__main__":
    main()
