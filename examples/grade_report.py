"""Score two handcrafted reports on a frozen case; no agent results are claimed."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess

from inquest.env import InvestigationEnv
from inquest.frozen import load_frozen_set
from inquest.grader import grade


def main():
    root = Path(__file__).resolve().parents[1]
    directory = root / "datasets" / "smoke-v1"
    set_name = "test-easy"
    scenario = load_frozen_set(directory, set_name)[7]
    env = InvestigationEnv(scenario, max_steps=3)
    env.call("query_metric", service="postgres", metric="lock_wait_ms")
    env.call("get_events", service="postgres")
    env.call("search_logs", service="postgres", level="WARN", limit=5)

    # These are authored fixtures, with chosen confidence, not agent predictions.
    report = {
        "service": "postgres", "fault_type": "bad_migration",
        "fix": {"action": "rollback_migration", "target": "postgres"},
        "evidence": ["o1", "o2", "o3"], "confidence": 0.8,
        "summary": "Database lock waits and the migration are consistent with blocked queries.",
    }
    invalid_report = deepcopy(report)
    invalid_report["evidence"] = ["o1", "o999"]
    manifest = json.loads((directory / "manifest.json").read_text())
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True,
                                           stderr=subprocess.DEVNULL, timeout=5).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root,
                                             text=True, stderr=subprocess.DEVNULL, timeout=5).strip())
    except (OSError, subprocess.SubprocessError):
        revision = dirty = None
    print(json.dumps({
        "kind": "handcrafted_grading_demo", "suite_id": manifest["suite_id"],
        "set_name": set_name, "set_sha256": manifest["sets"][set_name]["sha256"],
        "repository_revision": revision, "working_tree_dirty": dirty,
        "results": [grade(scenario, env, report), grade(scenario, env, invalid_report)],
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
