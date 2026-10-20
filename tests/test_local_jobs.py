"""Durable local lifecycle tests use the actual runner and no model endpoint."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import time

import pytest

from app import ROOT, create_app
from local_app import create_local_app
from local_jobs import JobConflict, JobManager, JobMissing
from inquest.backends import AlertHeuristic, BackendError
from inquest.runner import RunError, run_experiment


@pytest.fixture
def manager(tmp_path):
    instance = JobManager(tmp_path / "jobs", ROOT / "datasets", autostart=False)
    yield instance
    instance.close()


def submit(manager, key="1" * 32, case_id="authored-v2-004", budget=5):
    return manager.submit(suite="authored-v2", case_id=case_id, budget=budget, request_key=key)


def test_selected_case_streamed_after_journal_write_and_budget_preserved(tmp_path):
    output = tmp_path / "run"
    callbacks = []

    def record(job, kind, body):
        path = next(output.glob("episodes/*/attempt-001.jsonl"))
        last = json.loads(path.read_text().splitlines()[-1])
        assert last["kind"] == kind  # Hook cannot observe an event before it is durable.
        callbacks.append(kind)

    summary = run_experiment(suite=ROOT / "datasets/authored-v2", set_name="holdout", backend=AlertHeuristic(),
                             budgets=(5,), output=output, allow_dirty=True,
                             case_ids=("authored-v2-004",), event_hook=record)
    manifest = json.loads((output / "run.json").read_text())
    assert [job["case_id"] for job in manifest["jobs"]] == ["authored-v2-004"]
    assert summary["completed_episodes"] == 1
    assert callbacks.count("observation") <= 5
    assert callbacks[-1] == "episode_finished"


@pytest.mark.parametrize("case_ids", [(), ("missing",), ("authored-v2-001", "authored-v2-001"), ["authored-v2-001"]])
def test_runner_rejects_invalid_case_selection(tmp_path, case_ids):
    with pytest.raises(RunError):
        run_experiment(suite=ROOT / "datasets/authored-v2", set_name="holdout", backend=AlertHeuristic(),
                       budgets=(5,), output=tmp_path / "run", allow_dirty=True, case_ids=case_ids)
    assert not (tmp_path / "run").exists()


def test_idempotent_concurrent_submit_and_setting_conflict(manager):
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: submit(manager)["id"], range(8)))
    assert len(set(ids)) == len(manager.list()) == 1
    with pytest.raises(JobConflict, match="different settings"):
        submit(manager, budget=10)


def test_queued_cancel_never_runs_and_explicit_resume_completes(manager):
    job = submit(manager)
    assert manager.cancel(job["id"])["state"] == "cancelled"
    assert manager.run_next() is False
    assert not (manager.root / job["id"]).exists()
    manager.resume(job["id"])
    assert manager.run_next() is True
    result = manager.get(job["id"])
    assert result["state"] == "completed"
    assert result["result"]["case_id"] == "authored-v2-004"
    assert result["result"]["score"]["steps"] <= 5
    assert result["result"]["usage"]["model_requests"] == 0
    assert manager.cancel(job["id"])["state"] == "completed"
    with pytest.raises(JobConflict):
        manager.resume(job["id"])


def test_cancel_running_preserves_attempt_and_resume_creates_new_attempt(tmp_path):
    entered, release = threading.Event(), threading.Event()

    class PausingHeuristic(AlertHeuristic):
        def complete(self, messages, emit):
            if len(messages) > 2 and not release.is_set():
                entered.set()
                assert release.wait(5)
            return super().complete(messages, emit)

    instance = JobManager(tmp_path / "jobs", ROOT / "datasets", autostart=False,
                          backend_factory=PausingHeuristic)
    job = submit(instance)
    worker = threading.Thread(target=instance.run_next)
    worker.start()
    try:
        assert entered.wait(5)
        assert instance.get(job["id"])["steps"] == 1
        assert instance.cancel(job["id"])["state"] == "cancelling"
        release.set()
        worker.join(5)
        assert not worker.is_alive()
        saved = instance.get(job["id"])
        assert saved["state"] == "cancelled" and saved["result"] is None
        journal = next((instance.root / job["id"]).glob("episodes/*/attempt-001.jsonl"))
        previous = journal.read_bytes()
        assert json.loads(previous.splitlines()[-1])["kind"] == "interrupted"
        instance.resume(job["id"])
        instance.run_next()
        result = instance.get(job["id"])
        assert result["state"] == "completed" and result["result"]["attempt"] == 2
        assert journal.read_bytes() == previous
        assert len(instance.files(job["id"])) == 4
    finally:
        release.set()
        worker.join(5)
        instance.close()


def test_recovery_marks_jobs_interrupted_and_skips_finished_artifacts(manager):
    finished, queued = submit(manager), submit(manager, key="2" * 32)
    manager.run_next()
    assert manager.get(finished["id"])["state"] == "completed"
    original = manager.get(finished["id"])["result"]
    # Simulate a crash after result.json was committed but before SQL completion.
    with manager._db() as db:
        db.execute("UPDATE jobs SET state='running' WHERE id=?", (finished["id"],))
    manager.close()

    class MustNotRun(AlertHeuristic):
        def complete(self, messages, emit):
            raise AssertionError("Completed artifact was executed again")

    recovered = JobManager(manager.root, ROOT / "datasets", autostart=False, backend_factory=MustNotRun)
    try:
        assert {job["state"] for job in recovered.list()} == {"interrupted"}
        assert recovered.run_next() is False  # No silent restart of either job.
        recovered.resume(finished["id"])
        recovered.run_next()
        assert recovered.get(finished["id"])["state"] == "completed"
        assert recovered.get(finished["id"])["result"] == original
        assert recovered.get(queued["id"])["state"] == "interrupted"
    finally:
        recovered.close()


def test_owner_lock_and_queue_limits(manager):
    with pytest.raises(RunError, match="Another process"):
        JobManager(manager.root, ROOT / "datasets", autostart=False)
    jobs = [submit(manager, key=f"{i:032x}") for i in range(8)]
    with pytest.raises(JobConflict, match="Queue is full"):
        submit(manager, key="f" * 32)
    manager.cancel(jobs[0]["id"])
    assert submit(manager, key="f" * 32)["state"] == "queued"


def test_execution_failure_and_cooperative_deadline(tmp_path):
    class Failing(AlertHeuristic):
        def complete(self, messages, emit):
            raise BackendError("scripted_failure")

    instance = JobManager(tmp_path / "failure", ROOT / "datasets", autostart=False, backend_factory=Failing)
    try:
        job = submit(instance)
        instance.run_next()
        saved = instance.get(job["id"])
        assert saved["state"] == "failed" and saved["error"] == "scripted_failure"
        assert saved["result"]["report"] is None
    finally:
        instance.close()
    instance = JobManager(tmp_path / "deadline", ROOT / "datasets", autostart=False, wall_seconds=-1)
    try:
        job = submit(instance)
        instance.run_next()
        assert instance.get(job["id"])["error"] == "wall_time_limit"
    finally:
        instance.close()


def test_resume_rejects_changed_source_without_overwriting_history(manager, monkeypatch):
    job = submit(manager)
    manager.run_next()
    with manager._db() as db:
        db.execute("UPDATE jobs SET state='interrupted' WHERE id=?", (job["id"],))
    journal = next((manager.root / job["id"]).glob("episodes/*/attempt-001.jsonl"))
    before = journal.read_bytes()
    from inquest.runner import code_identity
    changed = code_identity()
    changed["package_sha256"]["runner.py"] = "changed"
    monkeypatch.setattr("inquest.runner.code_identity", lambda: changed)
    manager.resume(job["id"])
    manager.run_next()
    assert manager.get(job["id"])["state"] == "failed"
    assert "changed" in manager.get(job["id"])["error"]
    assert journal.read_bytes() == before


def test_local_http_boundary_and_hosted_routes_are_disabled(manager):
    hosted = create_app().test_client()
    assert hosted.get("/investigate").status_code == 404
    assert hosted.get("/api/local/config").status_code == 404
    app = create_local_app(manager)
    client = app.test_client()

    def call(path, **kwargs):
        return client.open(path, base_url="http://127.0.0.1:8000", **kwargs)

    config = call("/api/local/config").get_json()
    assert "root_service" not in json.dumps(config)
    token = {"X-Inquest-Token": config["token"]}
    assert call("/api/local/jobs").status_code == 403
    assert call("/api/local/jobs", headers=token).status_code == 200
    assert call("/api/local/config", headers={"Origin": "https://untrusted.invalid"}).status_code == 403
    assert call("/api/local/config", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.get("/api/local/config", base_url="http://untrusted.invalid:8000").status_code == 403
    assert call("/api/local/config", environ_overrides={"REMOTE_ADDR": "192.0.2.1"}).status_code == 403
    payload = {"suite": "authored-v2", "case_id": "authored-v2-004", "budget": 5, "request_key": "1" * 32}
    response = call("/api/local/jobs", method="POST", headers=token, json=payload)
    assert response.status_code == 202
    job_id = response.get_json()["id"]
    assert call("/api/local/jobs", method="POST", headers=token, json={**payload, "backend": "compatible"}).status_code == 400
    assert call("/api/local/jobs", method="POST", headers=token, json={**payload, "budget": True}).status_code == 400
    assert call("/api/local/jobs", method="POST", headers=token, data="x" * 17000, content_type="application/json").status_code == 413
    assert call("/runs?job=../../untrusted").status_code == 404
    manager.run_next()
    viewer = call(f"/runs?job={job_id}")
    assert viewer.status_code == 200 and b"local-run-files" in viewer.data
    assert "connect-src 'none'" in viewer.headers["Content-Security-Policy"]
    assert viewer.headers["Cache-Control"] == "no-store"
    assert call(f"/api/local/jobs/{job_id}", headers=token).get_json()["result"]["case_id"] == payload["case_id"]
    with pytest.raises(JobMissing):
        manager.files("../run.json")


def test_background_worker_consumes_queue(tmp_path):
    instance = JobManager(tmp_path / "jobs", ROOT / "datasets")
    try:
        job = submit(instance)
        deadline = time.monotonic() + 5
        while instance.get(job["id"])["state"] in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(.01)
        assert instance.get(job["id"])["state"] == "completed"
        assert instance.run_next() is False
    finally:
        instance.close()


def test_graceful_shutdown_preserves_running_work_for_resume(tmp_path):
    entered, release = threading.Event(), threading.Event()

    class Pausing(AlertHeuristic):
        def complete(self, messages, emit):
            if len(messages) > 2:
                entered.set()
                assert release.wait(5)
            return super().complete(messages, emit)

    instance = JobManager(tmp_path / "jobs", ROOT / "datasets", backend_factory=Pausing)
    job = submit(instance)
    closer = None
    try:
        assert entered.wait(5)
        closer = threading.Thread(target=instance.close)
        closer.start()
        assert instance._stop.wait(2)
        release.set()
        closer.join(5)
        assert not closer.is_alive()
        assert instance.get(job["id"])["state"] == "interrupted"
    finally:
        release.set()
        if closer:
            closer.join(5)
        instance.close()
    recovered = JobManager(instance.root, ROOT / "datasets", autostart=False)
    try:
        recovered.resume(job["id"])
        recovered.run_next()
        assert recovered.get(job["id"])["result"]["attempt"] == 2
    finally:
        recovered.close()


@pytest.mark.parametrize("has_saved_data", [False, True])
def test_incomplete_header_recovery_preserves_unstarted_directory(manager, has_saved_data):
    job = submit(manager)
    output = manager.root / job["id"]
    output.mkdir()
    (output / ".lock").touch()
    (output / ".pending-header").write_text("partial")
    if has_saved_data:
        (output / "episodes").mkdir()
    manager.run_next()
    if has_saved_data:
        assert manager.get(job["id"])["state"] == "failed"
        assert "Incomplete run header" in manager.get(job["id"])["error"]
        assert (output / ".pending-header").read_text() == "partial"
    else:
        assert manager.get(job["id"])["state"] == "completed"
        archive = next(manager.root.glob(f"{job['id']}-unstarted-*"))
        assert (archive / ".pending-header").read_text() == "partial"


def test_model_backend_cannot_be_used_by_local_worker(tmp_path):
    class Model(AlertHeuristic):
        def identity(self):
            return {"kind": "scripted_model", "is_model": True}

        def complete(self, messages, emit):
            raise AssertionError("No provider call is permitted")

    instance = JobManager(tmp_path / "jobs", ROOT / "datasets", autostart=False, backend_factory=Model)
    try:
        job = submit(instance)
        instance.run_next()
        assert instance.get(job["id"])["state"] == "failed"
        assert "only permits the offline heuristic" in instance.get(job["id"])["error"]
    finally:
        instance.close()


def test_shutdown_rejects_further_mutations(manager):
    job = submit(manager)
    manager.close()
    for action in (lambda: submit(manager, key="2" * 32),
                   lambda: manager.cancel(job["id"]), lambda: manager.resume(job["id"])):
        with pytest.raises(JobConflict, match="shutting down"):
            action()
    assert len(manager.list()) == 1
