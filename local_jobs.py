"""Single-worker, durable local jobs. Only the built-in offline heuristic is allowed.

The lifetime file lock excludes a second manager, SQLite records state, and the
existing runner remains responsible for fingerprints, budgets and artifacts.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time

from inquest.backends import AlertHeuristic
from inquest.frozen import load_frozen_set
from inquest.runner import RunError, now, run_experiment, run_lock, sha256

ACTIVE = ("queued", "running", "cancelling")
RECOVERABLE = ("interrupted", "cancelled")


class JobConflict(ValueError):
    pass


class JobMissing(ValueError):
    pass


class _Stopped(KeyboardInterrupt):
    def __init__(self, reason):
        self.reason = reason


class JobManager:
    def __init__(self, root: Path, datasets: Path, *, autostart=True,
                 backend_factory=AlertHeuristic, wall_seconds=120):
        self.root, self.datasets = Path(root).resolve(), Path(datasets).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._owner = run_lock(self.root)
        self._owner.__enter__()
        self._stop, self._wake = threading.Event(), threading.Event()
        self._execution = threading.Lock()
        self._thread = None
        self._closed = False
        self._backend_factory, self.wall_seconds = backend_factory, wall_seconds
        self._worker_sha256 = sha256(Path(__file__).read_bytes())
        try:
            self.catalog = {name: [{"case_id": case.id, "difficulty": case.difficulty}
                                  for case in load_frozen_set(self.datasets / name, "holdout")]
                            for name in ("authored-v1", "authored-v2")}
            with self._db() as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL,
                    suite TEXT NOT NULL, case_id TEXT NOT NULL, budget INTEGER NOT NULL,
                    state TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    cancel INTEGER NOT NULL DEFAULT 0, error TEXT,
                    steps INTEGER NOT NULL DEFAULT 0, events TEXT NOT NULL DEFAULT '[]')""")
                # A restart never silently starts queued or partially executed work.
                db.execute("""UPDATE jobs SET state='interrupted', error='server_restarted',
                    updated_at=? WHERE state IN ('queued','running','cancelling')""", (now(),))
            if autostart:
                self._thread = threading.Thread(target=self._loop, daemon=True, name="inquest-local-worker")
                self._thread.start()
        except BaseException:
            self._owner.__exit__(None, None, None)
            raise

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.root / "jobs.sqlite3", timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def _row(self, db, job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise JobMissing("Unknown local job")
        row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise JobMissing("Unknown local job")
        return row

    @staticmethod
    def _public(row, detail=False):
        keys = ("id", "suite", "case_id", "budget", "state", "created_at", "updated_at", "error", "steps")
        result = {key: row[key] for key in keys}
        if detail:
            result["events"] = json.loads(row["events"])
        return result

    def list(self):
        with self._db() as db:
            return [self._public(row) for row in db.execute("SELECT * FROM jobs ORDER BY created_at DESC, id DESC")]

    def get(self, job_id):
        with self._db() as db:
            result = self._public(self._row(db, job_id), detail=True)
        directory = self.root / job_id
        results = list((directory / "episodes").glob("*/result.json"))
        result["result"] = json.loads(results[0].read_text()) if results else None
        result["can_open"] = (directory / "run.json").is_file()
        return result

    @staticmethod
    def _capacity(db):
        if db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running','cancelling')").fetchone()[0] >= 8:
            raise JobConflict("Queue is full (8 active jobs). Wait or cancel a queued job.")

    def _accepting(self):
        if self._stop.is_set():
            raise JobConflict("Local worker is shutting down; restart it before changing jobs")

    def submit(self, *, suite, case_id, budget, request_key):
        if (not isinstance(suite, str) or suite not in self.catalog or
                not isinstance(case_id, str) or case_id not in {case["case_id"] for case in self.catalog[suite]} or
                type(budget) is not int or budget not in (5, 10, 20) or
                not isinstance(request_key, str) or not re.fullmatch(r"[a-f0-9]{32}", request_key)):
            raise ValueError("Choose a known suite, case, budget (5, 10 or 20), and request ID")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self._accepting()
            existing = db.execute("SELECT * FROM jobs WHERE request_key=?", (request_key,)).fetchone()
            if existing:
                if (existing["suite"], existing["case_id"], existing["budget"]) != (suite, case_id, budget):
                    raise JobConflict("Request ID was already used with different settings")
                return self._public(existing)
            self._capacity(db)
            if db.execute("SELECT count(*) FROM jobs").fetchone()[0] >= 200:
                raise JobConflict("This local store has 200 jobs. Start a separate store with --data-dir.")
            job_id, timestamp = secrets.token_hex(16), now()
            db.execute("""INSERT INTO jobs(id,request_key,suite,case_id,budget,state,created_at,updated_at)
                          VALUES(?,?,?,?,?,'queued',?,?)""",
                       (job_id, request_key, suite, case_id, budget, timestamp, timestamp))
            result = self._public(self._row(db, job_id))
        self._wake.set()
        return result

    def cancel(self, job_id):
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self._accepting()
            row = self._row(db, job_id)
            if row["state"] in ACTIVE:
                state = "cancelled" if row["state"] == "queued" else "cancelling"
                db.execute("UPDATE jobs SET state=?, cancel=1, updated_at=? WHERE id=?", (state, now(), job_id))
            return self._public(self._row(db, job_id))

    def resume(self, job_id):
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self._accepting()
            row = self._row(db, job_id)
            if row["state"] not in RECOVERABLE:
                raise JobConflict("Only interrupted or cancelled jobs can be resumed")
            self._capacity(db)
            db.execute("""UPDATE jobs SET state='queued', cancel=0, error=NULL,
                steps=0, events='[]', updated_at=? WHERE id=?""", (now(), job_id))
            result = self._public(self._row(db, job_id))
        self._wake.set()
        return result

    def _loop(self):
        while not self._stop.is_set():
            if not self.run_next():
                self._wake.wait(.25)
                self._wake.clear()

    def run_next(self):
        """Claim at most one queued job. Also usable synchronously by lifecycle tests."""
        if self._stop.is_set() or not self._execution.acquire(blocking=False):
            return False
        try:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1").fetchone()
                if row is None:
                    return False
                job_id = row["id"]
                db.execute("UPDATE jobs SET state='running', updated_at=? WHERE id=?", (now(), job_id))
            self._execute(dict(row))
            return True
        finally:
            self._execution.release()

    def _execute(self, row):
        job_id = row["id"]
        started = time.monotonic()
        manager = self

        def checkpoint():
            with self._db() as db:
                cancelled = self._row(db, job_id)["cancel"]
            if cancelled:
                raise _Stopped("cancelled")
            if self._stop.is_set():
                raise _Stopped("interrupted")
            if time.monotonic() - started > self.wall_seconds:
                raise _Stopped("wall_time_limit")

        class CancellableHeuristic:
            def __init__(self):
                self.backend = manager._backend_factory()
                if self.backend.identity().get("is_model") is not False:
                    raise RunError("Local web execution only permits the offline heuristic")

            def identity(self):
                return {**self.backend.identity(), "local_worker_sha256": manager._worker_sha256}

            def complete(self, messages, emit):
                checkpoint()
                reply = self.backend.complete(messages, emit)
                checkpoint()
                return reply

        events = []

        def record(job, kind, body):
            if kind not in ("observation", "protocol_error", "backend_error", "report"):
                return
            events.append({"kind": kind, **body})
            steps = row["budget"] - body["steps_left"] if kind == "observation" else None
            with self._db() as db:
                db.execute("UPDATE jobs SET events=?, steps=coalesce(?,steps), updated_at=? WHERE id=?",
                           (json.dumps(events, allow_nan=False), steps, now(), job_id))

        output = self.root / job_id
        state, error = "completed", None
        try:
            checkpoint()
            if output.exists() and not (output / "run.json").exists():
                contents = list(output.iterdir())
                if any(not path.is_file() or not (path.name == ".lock" or path.name.startswith(".pending-"))
                       for path in contents):
                    raise RunError("Incomplete run header with saved data; inspect the original directory")
                # A crash between mkdir and the first atomic header write has no
                # executed episode. Preserve that directory before starting anew.
                output.rename(self.root / f"{job_id}-unstarted-{secrets.token_hex(4)}")
            summary = run_experiment(suite=self.datasets / row["suite"], set_name="holdout",
                                     backend=CancellableHeuristic(), budgets=(row["budget"],), output=output,
                                     case_ids=(row["case_id"],),
                                     episode_options={"policy": "v2", "max_model_turns": 32},
                                     resume=(output / "run.json").exists(), allow_dirty=True, event_hook=record)
            # A finished artifact wins a cancellation arriving after the last checkpoint.
            result = next(output.glob("episodes/*/result.json"))
            result_body = json.loads(result.read_text())
            if summary["completed_episodes"] != 1 or result_body["status"] != "reported":
                state, error = "failed", result_body.get("error_code") or result_body["status"]
        except _Stopped as exc:
            state = exc.reason if exc.reason in RECOVERABLE else "failed"
            error = exc.reason
        except RunError as exc:
            state, error = "failed", str(exc)[:500]
        except Exception:
            state, error = "failed", "local_execution_error"
        with self._db() as db:
            db.execute("UPDATE jobs SET state=?, error=?, updated_at=? WHERE id=?", (state, error, now(), job_id))

    def files(self, job_id):
        self.get(job_id)  # Verify the database identity before resolving any path.
        directory = self.root / job_id
        if not (directory / "run.json").is_file():
            raise JobConflict("This job has no saved run yet")
        paths = [directory / "run.json"] + sorted(directory.glob("episodes/*/result.json")) + sorted(directory.glob("episodes/*/attempt-*.jsonl"))
        if sum(path.stat().st_size for path in paths) > 20 * 1024 * 1024:
            raise JobConflict("Open this run using the folder picker; its saved files exceed 20 MiB")
        return [{"path": f"{job_id}/{path.relative_to(directory).as_posix()}", "content": path.read_text()}
                for path in paths]

    def close(self):
        if self._closed:
            return
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise RuntimeError("Local worker has not stopped; keep its ownership lock until process exit")
        # Drain an already accepted SQL mutation before releasing process ownership.
        # Later mutations check _stop while holding this same SQL write lock.
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
        self._owner.__exit__(None, None, None)
        self._closed = True
