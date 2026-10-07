"""Small browser workbench for the Inquest incident generator.

The API deliberately separates observable telemetry from construction labels.
This is an educational demo, not the budgeted benchmark environment on the roadmap.
"""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from inquest import generate  # noqa: E402
from inquest.frozen import load_frozen_set  # noqa: E402
from inquest.scenario import DIFFICULTY, FAULTS, FIX_ACTIONS, SPLITS  # noqa: E402
from inquest.topology import EDGES, SERVICES  # noqa: E402

app = Flask(__name__, static_folder=None)
FROZEN_DIR = ROOT / "datasets" / "smoke-v1"
MAX_SEED = 1_000_000


def _selection(payload):
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    source = payload.get("source", "frozen")
    difficulty = payload.get("difficulty", "easy")
    split = payload.get("split", "dev")
    if not isinstance(difficulty, str) or not isinstance(split, str) or difficulty not in DIFFICULTY or split not in SPLITS:
        raise ValueError("Choose a valid difficulty and split")
    if source == "frozen":
        index = payload.get("index", 0)
        if type(index) is not int or index < 0 or index >= (8 if split == "dev" else 16):
            raise ValueError("Choose a valid frozen case number")
        scenario = load_frozen_set(FROZEN_DIR, f"{split}-{difficulty}")[index]
        return scenario, {"source": source, "split": split, "difficulty": difficulty, "index": index}
    if source == "generated":
        seed = payload.get("seed", 7)
        if type(seed) is not int or not 0 <= seed <= MAX_SEED:
            raise ValueError(f"Seed must be an integer from 0 to {MAX_SEED}")
        scenario = generate(seed=seed, difficulty=difficulty, split=split)
        return scenario, {"source": source, "split": split, "difficulty": difficulty, "seed": seed}
    raise ValueError("Choose frozen or generated cases")


def _summary(scenario):
    return {
        "topology": {"services": SERVICES, "edges": EDGES},
        "metrics": scenario.metrics,
        "logs": scenario.logs,
        "events": scenario.events,
        "traces": scenario.traces,
        "health": scenario.health,
    }

@app.get("/")
def index():
    return send_from_directory(ROOT / "public", "index.html")


@app.get("/assets/<path:name>")
def assets(name):
    return send_from_directory(ROOT / "public" / "assets", name)


@app.get("/api/config")
def config():
    return jsonify({
        "splits": list(SPLITS),
        "difficulties": list(DIFFICULTY),
        "faults": FAULTS,
        "fixActions": FIX_ACTIONS,
        "frozenCounts": {split: 8 if split == "dev" else 16 for split in SPLITS},
        "maxSeed": MAX_SEED,
    })


@app.post("/api/incident")
def incident():
    try:
        scenario, selection = _selection(request.get_json(silent=True))
    except (ValueError, OSError) as exc:
        return jsonify({"error": str(exc)}), 400
    response = _summary(scenario)
    response["selection"] = selection
    return jsonify(response)


@app.post("/api/diagnosis")
def diagnosis():
    payload = request.get_json(silent=True)
    try:
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object")
        scenario, _ = _selection(payload.get("selection"))
        answer = payload.get("answer")
        if not isinstance(answer, dict):
            raise ValueError("Provide a diagnosis")
        service, fault, action = (answer.get(k) for k in ("service", "fault", "action"))
        if service not in SERVICES or fault not in FAULTS or action not in FIX_ACTIONS:
            raise ValueError("Choose a valid service, fault, and fix action")
    except (ValueError, OSError) as exc:
        return jsonify({"error": str(exc)}), 400
    checks = {
        "service": service == scenario.root_service,
        "fault": fault == scenario.fault_type,
        "action": action == scenario.fix["action"],
    }
    return jsonify({
        "checks": checks,
        "correct": all(checks.values()),
        "answer": {"service": scenario.root_service, "fault": scenario.fault_type, "fix": scenario.fix},
    })


@app.get("/api/health")
def api_health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=8000)
