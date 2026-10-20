"""Budgeted episodes, durable run journals, and failure-inclusive evaluation."""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import re
from pathlib import Path
import subprocess
import tempfile
import time

from .agent_protocol import POLICIES, PROTOCOL_VERSION, ProtocolError, parse_action, strict_json, system_prompt
from .backends import Backend, BackendError, RunPaused
from .env import InvestigationEnv
from .frozen import load_frozen_set
from .grader import grade

FORMAT_VERSION = 1


class RunError(ValueError):
    pass


@dataclass(frozen=True)
class EpisodeConfig:
    max_steps: int = 10
    max_model_turns: int = 32
    max_protocol_errors: int = 2
    max_prompt_chars: int = 100_000
    max_lines: int = 20
    policy: str = "v1"

    def __post_init__(self):
        for name in ("max_steps", "max_model_turns", "max_protocol_errors", "max_prompt_chars", "max_lines"):
            value = getattr(self, name)
            if type(value) is not int or value < (0 if name == "max_steps" else 1):
                raise ValueError(f"Invalid {name}")
        if self.policy not in POLICIES:
            raise ValueError("Unknown investigation policy")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(data: bytes):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value):
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pending-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def run_lock(directory: Path):
    try:
        import fcntl
    except ImportError:
        raise RunError("Runner locking requires Linux or macOS") from None
    with (directory / ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RunError("Another process is using this run directory") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class Journal:
    def __init__(self, path: Path):
        self.stream = path.open("x", encoding="utf-8")
        self.sequence = 0

    def emit(self, kind, body):
        self.sequence += 1
        self.stream.write(canonical({"seq": self.sequence, "time_utc": now(), "kind": kind, **body}) + "\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def close(self):
        self.stream.close()


def run_episode(scenario, backend: Backend, config: EpisodeConfig, emit):
    """Only detached public messages reach the backend; grading stays evaluator-side."""
    env = InvestigationEnv(scenario, max_steps=config.max_steps, max_lines=config.max_lines)
    messages = [{"role": "system", "content": system_prompt(config.policy)},
                {"role": "user", "content": canonical({"kind": "start", "steps_left": env.steps_left})}]
    is_model = backend.identity()["is_model"]
    usage = {"input_tokens_known": 0, "output_tokens_known": 0,
             "input_usage_missing_calls": 0, "output_usage_missing_calls": 0,
             "model_requests": 0, "transport_attempts": 0, "failed_transport_attempts": 0}

    def record(kind, body):
        if kind == "transport_attempt":
            usage["transport_attempts"] += 1
        elif kind == "transport_result" and body.get("outcome") != "received":
            usage["failed_transport_attempts"] += 1
        emit(kind, body)

    start = time.perf_counter()
    report, status, error_code = None, "model_turn_limit", None
    turns = protocol_errors = 0
    try:
        for turn in range(1, config.max_model_turns + 1):
            if sum(len(m["content"]) for m in messages) > config.max_prompt_chars:
                status, error_code = "context_limit", "prompt_character_limit"
                break
            turns = turn
            record("model_request", {"turn": turn, "messages": deepcopy(messages)})
            if is_model:
                usage["model_requests"] += 1
                usage["input_usage_missing_calls"] += 1
                usage["output_usage_missing_calls"] += 1
            try:
                reply = backend.complete(deepcopy(messages), record)
            except RunPaused as exc:
                record("paused", {"turn": turn, "code": exc.code, "steps": env.steps, "usage": usage})
                raise
            except BackendError as exc:
                status, error_code = "backend_error", exc.code
                record("backend_error", {"turn": turn, "code": exc.code})
                break
            record("model_reply", {"turn": turn, **asdict(reply)})
            if is_model:
                for name in ("input", "output"):
                    count = getattr(reply, name + "_tokens")
                    if type(count) is int and count >= 0:
                        usage[name + "_tokens_known"] += count
                        usage[name + "_usage_missing_calls"] -= 1
            messages.append({"role": "assistant", "content": reply.content})
            try:
                action = parse_action(reply.content)
            except ProtocolError as exc:
                protocol_errors += 1
                record("protocol_error", {"turn": turn, "code": str(exc)})
                if protocol_errors >= config.max_protocol_errors:
                    status, error_code = "protocol_error", str(exc)
                    break
                messages.append({"role": "user", "content": canonical({
                    "kind": "protocol_error", "error": str(exc), "steps_left": env.steps_left,
                    "instruction": ("Return one valid JSON tool action or final report envelope."
                                    if config.policy == "v1" else
                                    'Return one valid envelope. Put every tool argument inside args, e.g. '
                                    '{"kind":"tool","tool":"get_alerts","args":{}}. '
                                    'For a report use {"kind":"report","report":{...}}. No extra fields.'),
                })})
                continue
            if action["kind"] == "report":
                report, status = action["report"], "reported"
                record("report", {"report": report})
                break
            if env.steps_left == 0:
                status, error_code = "tool_budget_exhausted", "tool_requested_after_budget"
                record("budget_error", {"turn": turn, "code": error_code})
                break
            observation = env.call(action["tool"], **action["args"])
            body = {"kind": "observation", "steps_left": env.steps_left,
                    "observation": asdict(observation)}
            record("observation", {"observation": asdict(observation), "steps_left": env.steps_left})
            messages.append({"role": "user", "content": canonical(body)})
    except KeyboardInterrupt:
        record("interrupted", {"turn": turns, "steps": env.steps, "usage": usage})
        raise
    score = grade(scenario, env, report)
    result = {"status": status, "error_code": error_code, "report": report, "score": score,
              "model_turns": turns, "protocol_errors": protocol_errors,
              "latency_seconds": time.perf_counter() - start, "usage": usage}
    record("episode_finished", result)
    return result


def code_identity():
    package = Path(__file__).parent
    try:
        root = package.parents[1]
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True,
                                           stderr=subprocess.DEVNULL, timeout=5).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True,
                                            stderr=subprocess.DEVNULL, timeout=5).strip())
    except (OSError, subprocess.SubprocessError):
        revision = dirty = None
    return {"revision": revision, "dirty": dirty,
            "package_sha256": {path.name: sha256(path.read_bytes()) for path in sorted(package.glob("*.py"))}}


def wilson(successes, count):
    if not count:
        return None
    z = 1.959963984540054
    p = successes / count
    divisor = 1 + z * z / count
    center = (p + z * z / (2 * count)) / divisor
    half = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / divisor
    return [max(0.0, center - half), min(1.0, center + half)]


def _read_result(directory, job, fingerprint):
    path = directory / "episodes" / job["job_id"] / "result.json"
    if not path.exists():
        return None
    try:
        result = strict_json(path.read_text())
        if not isinstance(result, dict) or result.get("fingerprint") != fingerprint:
            raise ValueError()
        if any(result.get(key) != job[key] for key in ("job_id", "case_id", "max_steps", "difficulty")):
            raise ValueError()
        if type(result.get("attempt")) is not int or result["attempt"] < 1:
            raise ValueError()
        if not isinstance(result.get("score"), dict) or any(type(result["score"].get(k)) is not bool for k in
                                                        ("success", "evidence_relevant_success", "report_valid")):
            raise ValueError()
        score = result["score"]
        if result.get("status") not in ("reported", "backend_error", "protocol_error", "tool_budget_exhausted", "context_limit", "model_turn_limit"):
            raise ValueError()
        if "brier" not in score or (score["brier"] is not None and
                (type(score["brier"]) not in (int, float) or not math.isfinite(score["brier"]) or not 0 <= score["brier"] <= 1)):
            raise ValueError()
        if score["evidence_relevant_success"] and not score["success"]:
            raise ValueError()
        if not (path.parent / f"attempt-{result['attempt']:03d}.jsonl").is_file():
            raise ValueError()
        if score.get("scenario") != job["case_id"] or type(score.get("steps")) is not int or not 0 <= score["steps"] <= job["max_steps"]:
            raise ValueError()
        if type(result.get("latency_seconds")) not in (int, float) or not math.isfinite(result["latency_seconds"]) or result["latency_seconds"] < 0:
            raise ValueError()
        return result
    except (ValueError, KeyError, TypeError, RecursionError):
        raise RunError(f"Invalid saved result for {job['job_id']}") from None


def read_run_manifest(directory: str | Path):
    try:
        manifest = strict_json((Path(directory) / "run.json").read_text())
        if not isinstance(manifest, dict) or type(manifest.get("format_version")) is not int or manifest["format_version"] != FORMAT_VERSION:
            raise ValueError()
        config, jobs = manifest["config"], manifest["jobs"]
        if not isinstance(config, dict) or not isinstance(jobs, list):
            raise ValueError()
        if sha256(canonical(config).encode()) != manifest.get("fingerprint"):
            raise ValueError()
        expected = [(f"case-{i:04d}-budget-{budget:03d}", case_id, budget)
                    for budget in config["budgets"] for i, case_id in enumerate(config["suite"]["case_ids"], 1)]
        if len(expected) != len(jobs) or len({j[0] for j in expected}) != len(expected):
            raise ValueError()
        for job, (job_id, case_id, budget) in zip(jobs, expected):
            if not isinstance(job, dict) or not re.fullmatch(r"case-[0-9]{4,}-budget-[0-9]{3,}", job_id):
                raise ValueError()
            if any(job.get(k) != v for k, v in (("job_id", job_id), ("case_id", case_id), ("max_steps", budget))):
                raise ValueError()
            if job.get("difficulty") not in ("easy", "medium", "hard"):
                raise ValueError()
        return manifest
    except (ValueError, TypeError, KeyError, RecursionError):
        raise RunError("Invalid saved run manifest") from None


def summarize(directory: str | Path):
    """Pure read of saved artifacts; incomplete groups have no final success rate."""
    directory = Path(directory)
    manifest = read_run_manifest(directory)
    jobs = manifest["jobs"]
    results = {job["job_id"]: _read_result(directory, job, manifest["fingerprint"]) for job in jobs}
    groups = {}
    for budget in manifest["config"]["budgets"]:
        selected = [job for job in jobs if job["max_steps"] == budget]
        for difficulty in ["all"] + sorted({job["difficulty"] for job in selected}):
            members = [job for job in selected if difficulty == "all" or job["difficulty"] == difficulty]
            completed = [results[job["job_id"]] for job in members if results[job["job_id"]] is not None]
            successes = sum(r["score"]["success"] for r in completed)
            relevant = sum(r["score"]["evidence_relevant_success"] for r in completed)
            briers = [r["score"]["brier"] for r in completed if r["score"]["brier"] is not None]
            full = len(completed) == len(members)
            groups[f"budget_{budget}/{difficulty}"] = {
                "planned": len(members), "completed": len(completed), "unfinished": len(members) - len(completed),
                "successes": successes, "evidence_relevant_successes": relevant,
                "success_rate": successes / len(members) if full else None,
                "evidence_relevant_success_rate": relevant / len(members) if full else None,
                "success_wilson_95": wilson(successes, len(members)) if full else None,
                "invalid_reports": sum(not r["score"]["report_valid"] for r in completed),
                "status_counts": dict(Counter(r["status"] for r in completed)),
                "mean_brier_available": sum(briers) / len(briers) if briers else None,
                "brier_available": len(briers), "brier_missing": len(completed) - len(briers),
                "mean_steps": sum(r["score"]["steps"] for r in completed) / len(completed) if completed else None,
                "mean_latency_seconds": sum(r["latency_seconds"] for r in completed) / len(completed) if completed else None,
            }
    usage = Counter()
    prior_attempts = 0
    unreadable_lines = 0
    # Count usage from every attempt, including abandoned/interrupted attempts.
    for job in jobs:
        attempts = sorted((directory / "episodes" / job["job_id"]).glob("attempt-*.jsonl"))
        prior_attempts += max(0, len(attempts) - 1)
        for path in attempts:
            requests = replies = input_known_calls = output_known_calls = 0
            for line in path.read_text().splitlines():
                try:
                    event = strict_json(line)
                    if not isinstance(event, dict):
                        raise ValueError()
                except (ValueError, RecursionError):
                    unreadable_lines += 1
                    continue
                kind = event.get("kind")
                if kind == "model_request" and manifest["config"]["backend"]["is_model"]:
                    requests += 1
                if kind == "transport_attempt":
                    usage["transport_attempts"] += 1
                if kind == "transport_result" and event.get("outcome") != "received":
                    usage["failed_transport_attempts"] += 1
                if kind == "model_reply" and manifest["config"]["backend"]["is_model"]:
                    replies += 1
                    for name in ("input", "output"):
                        value = event.get(name + "_tokens")
                        if type(value) is int and value >= 0:
                            usage[name + "_tokens_known"] += value
                            if name == "input":
                                input_known_calls += 1
                            else:
                                output_known_calls += 1
            usage["model_requests"] += requests
            usage["model_replies"] += replies
            usage["input_usage_missing_calls"] += max(0, requests - input_known_calls)
            usage["output_usage_missing_calls"] += max(0, requests - output_known_calls)
    return {"format_version": FORMAT_VERSION, "fingerprint": manifest["fingerprint"],
            "kind": "model_evaluation" if manifest["config"]["backend"]["is_model"] else "offline_heuristic_evaluation",
            "planned_episodes": len(jobs), "completed_episodes": sum(r is not None for r in results.values()),
            "groups": groups, "usage_all_attempts": dict(usage),
            "prior_attempts_preserved": prior_attempts, "unreadable_journal_lines": unreadable_lines,
            "limitations": ["Public synthetic cases; fixed topology; coarse evidence relevance",
                            "Wilson intervals describe these case proportions, not production generalization",
                            "Known token totals exclude missing usage and may omit billing from failed requests",
                            "Brier means use available confidence values; missingness is reported"]}


def run_experiment(*, suite: str | Path, set_name: str, backend: Backend,
                   budgets: tuple[int, ...], output: str | Path, case_limit: int | None = None,
                   episode_options: dict | None = None, resume: bool = False,
                   allow_dirty: bool = False, progress=None,
                   case_ids: tuple[str, ...] | None = None, event_hook=None):
    suite, output = Path(suite), Path(output)
    if not budgets or len(set(budgets)) != len(budgets) or any(type(b) is not int or b < 1 for b in budgets):
        raise RunError("Budgets must be distinct positive integers")
    cases = load_frozen_set(suite, set_name)
    if case_ids is not None:
        if (not isinstance(case_ids, tuple) or not case_ids or
                any(not isinstance(case_id, str) for case_id in case_ids) or
                len(set(case_ids)) != len(case_ids) or case_limit is not None or
                not set(case_ids).issubset({case.id for case in cases})):
            raise RunError("Select distinct known case IDs without case_limit")
        cases = [case for case in cases if case.id in case_ids]
    if case_limit is not None:
        if type(case_limit) is not int or not 1 <= case_limit <= len(cases):
            raise RunError("Case limit must be within the selected set")
        cases = cases[:case_limit]
    options = dict(episode_options or {})
    if "max_steps" in options:
        raise RunError("Tool budgets are set by budgets, not episode_options")
    for budget in budgets:
        EpisodeConfig(max_steps=budget, **options)
    code = code_identity()
    if code["dirty"] and not allow_dirty:
        raise RunError("Commit changes before evaluation, or explicitly use --allow-dirty for development")
    data_manifest = strict_json((suite / "manifest.json").read_text())
    shared_options = asdict(EpisodeConfig(**options))
    del shared_options["max_steps"]
    config = {"protocol": PROTOCOL_VERSION, "backend": backend.identity(), "budgets": list(budgets),
              "episode_options": shared_options, "code": code,
              "prompt_sha256": sha256(system_prompt(shared_options["policy"]).encode()),
              "suite": {"suite_id": data_manifest["suite_id"], "set_name": set_name,
                        "manifest_sha256": sha256((suite / "manifest.json").read_bytes()),
                        "catalog_sha256": sha256((suite / "SHA256SUMS").read_bytes()),
                        "data_sha256": data_manifest["sets"][set_name]["sha256"],
                        "case_ids": [case.id for case in cases]}}
    fingerprint = sha256(canonical(config).encode())
    jobs = [{"job_id": f"case-{i:04d}-budget-{budget:03d}", "case_id": case.id,
             "difficulty": case.difficulty, "max_steps": budget}
            for budget in budgets for i, case in enumerate(cases, 1)]
    if resume:
        if not output.is_dir():
            raise RunError("Resume directory does not exist")
    else:
        try:
            output.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            raise RunError("Output already exists; use --resume with identical settings") from None
    with run_lock(output):
        manifest_path = output / "run.json"
        if resume:
            previous = read_run_manifest(output)
            if previous.get("fingerprint") != fingerprint or previous.get("config") != config or previous.get("jobs") != jobs:
                raise RunError("Resume configuration, model identity, data, prompt, or code changed")
        else:
            atomic_json(manifest_path, {"format_version": FORMAT_VERSION, "created_at_utc": now(),
                                       "fingerprint": fingerprint, "config": config, "jobs": jobs})
        by_id = {case.id: case for case in cases}
        try:
            for job in jobs:
                if _read_result(output, job, fingerprint) is not None:
                    continue
                directory = output / "episodes" / job["job_id"]
                directory.mkdir(parents=True, exist_ok=True)
                attempts = list(directory.glob("attempt-*.jsonl"))
                numbers = []
                for path in attempts:
                    try:
                        numbers.append(int(path.stem.removeprefix("attempt-")))
                    except ValueError:
                        raise RunError("Unexpected attempt filename") from None
                attempt = max(numbers, default=0) + 1
                journal = Journal(directory / f"attempt-{attempt:03d}.jsonl")
                def emit(kind, body):
                    journal.emit(kind, body)
                    if event_hook is not None:
                        event_hook(dict(job), kind, deepcopy(body))
                try:
                    journal.emit("episode_started", {**job, "attempt": attempt, "fingerprint": fingerprint})
                    result = run_episode(by_id[job["case_id"]], backend,
                                         EpisodeConfig(max_steps=job["max_steps"], **options), emit)
                    atomic_json(directory / "result.json", {**job, **result, "attempt": attempt,
                                                            "fingerprint": fingerprint})
                finally:
                    journal.close()
                atomic_json(output / "summary.json", summarize(output))
                if progress is not None:
                    progress(dict(job), deepcopy(result))
        except (KeyboardInterrupt, RunPaused):
            atomic_json(output / "summary.json", summarize(output))
            raise
        summary = summarize(output)
        atomic_json(output / "summary.json", summary)
        return summary
