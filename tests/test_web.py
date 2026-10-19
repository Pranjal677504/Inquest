"""Checks that the browser API serves observations and grades the selected case."""

from app import app
from inquest.frozen import load_frozen_set
from pathlib import Path


def test_saved_run_viewer_is_served_with_no_network_policy():
    client = app.test_client()
    response = client.get("/runs")
    assert response.status_code == 200
    assert b"Choose run folder" in response.data
    assert "connect-src 'none'" in response.headers["Content-Security-Policy"]
    assert b"Open saved investigations" in client.get("/").data
    assert client.get("/assets/runs.js").status_code == 200
    assert client.get("/assets/runs.css").status_code == 200


def test_frozen_case_hides_construction_labels_until_diagnosis():
    client = app.test_client()
    selection = {"source": "frozen", "split": "dev", "difficulty": "easy", "index": 0}
    incident = client.post("/api/incident", json=selection)
    assert incident.status_code == 200
    body = incident.get_json()
    assert len(body["topology"]["services"]) == 8
    assert len(body["metrics"]["gateway"]["error_rate"]) == 120
    assert "root_service" not in body
    assert "fault_type" not in body
    assert "fix" not in body
    assert "meta" not in body
    assert "gold_tools" not in body

    scenario = load_frozen_set(Path(__file__).resolve().parents[1] / "datasets" / "smoke-v1", "dev-easy")[0]
    result = client.post("/api/diagnosis", json={
        "selection": selection,
        "answer": {"service": scenario.root_service, "fault": scenario.fault_type, "action": scenario.fix["action"]},
    })
    assert result.status_code == 200
    assert result.get_json()["correct"] is True


def test_generated_case_and_input_bounds():
    client = app.test_client()
    valid = {"source": "generated", "split": "ood", "difficulty": "hard", "seed": 7}
    first = client.post("/api/incident", json=valid)
    second = client.post("/api/incident", json=valid)
    assert first.status_code == second.status_code == 200
    assert first.get_json() == second.get_json()
    for invalid in ({**valid, "seed": -1}, {**valid, "seed": 1000001}, {**valid, "difficulty": []},
                    {"source": "frozen", "split": "dev", "difficulty": "easy", "index": 8}):
        assert client.post("/api/incident", json=invalid).status_code == 400
