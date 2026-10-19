"""Read-only paired comparisons; no provider or dataset construction is invoked."""
from __future__ import annotations

from pathlib import Path

from .runner import RunError, _read_result, read_run_manifest, summarize

SCORING_FILES = ("grader.py", "env.py", "scenario.py", "frozen.py", "topology.py")
OPERATIONAL_FIELDS = ("api_key_env", "request_interval_seconds", "timeout_seconds",
                      "transport_retries", "pause_on_rate_limit")


def compare_runs(baseline: str | Path, candidate: str | Path):
    directories = (Path(baseline), Path(candidate))
    manifests = [read_run_manifest(path) for path in directories]
    summaries = [summarize(path) for path in directories]
    left, right = [m["config"] for m in manifests]
    if not manifests[0]["jobs"] or manifests[0]["jobs"] != manifests[1]["jobs"]:
        raise RunError("Comparison requires identical cases, budgets, and designed difficulties")
    for field in ("protocol", "suite"):
        if left[field] != right[field]:
            raise RunError(f"Comparison requires identical {field}")
    for config in (left, right):
        if config["code"].get("dirty") is not False:
            raise RunError("Comparison requires clean source runs")
    for filename in SCORING_FILES:
        hashes = [c["code"]["package_sha256"].get(filename) for c in (left, right)]
        if any(not isinstance(value, str) or len(value) != 64 for value in hashes) or hashes[0] != hashes[1]:
            raise RunError(f"Comparison scoring source differs: {filename}")
    options = [{k: v for k, v in c["episode_options"].items() if k != "policy"} for c in (left, right)]
    if options[0] != options[1]:
        raise RunError("Comparison requires identical episode limits")
    providers = [{k: v for k, v in c["backend"].items() if k not in OPERATIONAL_FIELDS} for c in (left, right)]
    if providers[0] != providers[1]:
        raise RunError("Comparison requires identical model and generation settings")
    if any(s["completed_episodes"] != s["planned_episodes"] for s in summaries):
        raise RunError("Complete both runs before comparing; unfinished cases cannot be dropped")
    rows = []
    for job in manifests[0]["jobs"]:
        results = [_read_result(path, job, m["fingerprint"]) for path, m in zip(directories, manifests)]
        if any(result is None for result in results):
            raise RunError("A result disappeared during comparison; retry after the runs are stable")
        if any(type(result.get("protocol_errors")) is not int or result["protocol_errors"] < 0 for result in results):
            raise RunError("Invalid saved protocol-error count")
        rows.append({"case_id": job["case_id"], "budget": job["max_steps"], "difficulty": job["difficulty"],
                     "baseline_success": results[0]["score"]["success"],
                     "candidate_success": results[1]["score"]["success"],
                     "baseline_evidence_success": results[0]["score"]["evidence_relevant_success"],
                     "candidate_evidence_success": results[1]["score"]["evidence_relevant_success"],
                     "baseline_protocol_errors": results[0]["protocol_errors"],
                     "candidate_protocol_errors": results[1]["protocol_errors"]})
    groups = {}
    for key, original in summaries[0]["groups"].items():
        updated = summaries[1]["groups"][key]
        budget, difficulty = key.split("/")
        selected = [r for r in rows if r["budget"] == int(budget.removeprefix("budget_"))
                    and (difficulty == "all" or r["difficulty"] == difficulty)]
        groups[key] = {
            "cases": len(selected), "baseline_successes": original["successes"],
            "candidate_successes": updated["successes"],
            "success_delta_percentage_points": 100 * (updated["success_rate"] - original["success_rate"]),
            "baseline_evidence_successes": original["evidence_relevant_successes"],
            "candidate_evidence_successes": updated["evidence_relevant_successes"],
            "improvements": [r["case_id"] for r in selected if r["candidate_success"] and not r["baseline_success"]],
            "regressions": [r["case_id"] for r in selected if r["baseline_success"] and not r["candidate_success"]],
            "both_successful": sum(r["baseline_success"] and r["candidate_success"] for r in selected),
            "both_failed": sum(not r["baseline_success"] and not r["candidate_success"] for r in selected),
            "baseline_brier": original["mean_brier_available"], "candidate_brier": updated["mean_brier_available"],
            "baseline_brier_missing": original["brier_missing"], "candidate_brier_missing": updated["brier_missing"],
            "baseline_invalid_reports": original["invalid_reports"], "candidate_invalid_reports": updated["invalid_reports"],
            "baseline_protocol_errors": sum(r["baseline_protocol_errors"] for r in selected),
            "candidate_protocol_errors": sum(r["candidate_protocol_errors"] for r in selected),
            "baseline_mean_steps": original["mean_steps"], "candidate_mean_steps": updated["mean_steps"],
            "baseline_mean_elapsed_seconds": original["mean_latency_seconds"],
            "candidate_mean_elapsed_seconds": updated["mean_latency_seconds"],
        }
    return {
        "kind": "paired_policy_comparison", "groups": groups, "cases": rows,
        "baseline": {"fingerprint": manifests[0]["fingerprint"], "policy": left["episode_options"].get("policy", "v1"),
                     "usage": summaries[0]["usage_all_attempts"]},
        "candidate": {"fingerprint": manifests[1]["fingerprint"], "policy": right["episode_options"].get("policy", "v1"),
                      "usage": summaries[1]["usage_all_attempts"]},
        "operational_differences": {k: {"baseline": left["backend"].get(k), "candidate": right["backend"].get(k)}
                                    for k in OPERATIONAL_FIELDS if left["backend"].get(k) != right["backend"].get(k)},
        "limitations": ["Descriptive paired results on public synthetic cases; no significance or production claim",
                        "Policy v2 was developed after inspecting v1 results; these cases are development data",
                        "Provider aliases and default sampling do not guarantee identical remote weights or determinism",
                        "Operational differences and retries affect usage and elapsed latency"],
    }
