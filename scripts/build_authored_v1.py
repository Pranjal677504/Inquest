"""Expand audited authored definitions into a NEW directory; never overwrite a suite.

This renderer interpolates explicit keyframes and copies authored telemetry. It
has no random sampling, fault-dispatch logic, or generator-template imports.
Published bytes are canonical; this script is a provenance/review aid.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inquest.env import InvestigationEnv  # noqa: E402
from inquest.scenario import HORIZON, Scenario  # noqa: E402
from inquest.topology import SERVICES  # noqa: E402


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def interpolate(points):
    """Linear interpolation of explicitly authored minute/value pairs."""
    if not isinstance(points, list) or len(points) < 2:
        raise ValueError("A profile needs at least two keyframes")
    times = [p[0] for p in points]
    if any(type(t) is not int for t in times) or times != sorted(set(times)) or times[0] != 0 or times[-1] != HORIZON - 1:
        raise ValueError("Keyframes must be unique, increasing, and span minutes 0–119")
    values = []
    for (start, first), (end, last) in zip(points, points[1:]):
        values.extend(round(first + (last - first) * (t - start) / (end - start), 3)
                      for t in range(start, end))
    return values + [points[-1][1]]


def construct(source):
    """Render supplied definitions, without knowing how faults create symptoms."""
    scenarios = []
    for case in source["cases"]:
        metrics = {s: {name: [value] * HORIZON for name, value in source["baseline_metrics"][s].items()}
                   for s in SERVICES}
        seen = set()
        for profile in case["profiles"]:
            service, metric = profile["service"], profile["metric"]
            if (service, metric) in seen or metric not in metrics[service]:
                raise ValueError("Duplicate or unknown authored metric profile")
            seen.add((service, metric))
            metrics[service][metric] = interpolate(profile["points"])
        logs = {s: [] for s in SERVICES}
        for record in case["logs"]:
            record = deepcopy(record)
            service = record.pop("service")
            logs[service].append(record)
        if any(logs[service] for service in case["missing_logs"]):
            raise ValueError("A missing-log case cannot contain that service's logs")
        for rows in logs.values():
            rows.sort(key=lambda row: row["t"])
        events = [dict(event, id=f"e{index}") for index, event in
                  enumerate(sorted(case["events"], key=lambda event: event["t"]), 1)]
        health = {s: {**source["baseline_health"], **case["health_overrides"].get(s, {})} for s in SERVICES}
        scenario = Scenario(
            id=case["id"], seed=None, origin="authored", split="holdout",
            difficulty=case["difficulty"], onset=case["onset"],
            root_service=case["root_service"], fault_type=case["fault_type"], fix=deepcopy(case["fix"]),
            metrics=metrics, logs=logs, events=events, traces=deepcopy(case["traces"]), health=health,
            gold_tools=deepcopy(case["gold_tools"]), gold_services=deepcopy(case["gold_services"]),
            meta={"construction": "authored-keyframes-v1"},
        )
        scenarios.append(Scenario.from_json(scenario.to_json()))
    return tuple(scenarios)


def review_probes(scenarios, cases):
    """Check clue reachability, not independent validity or agent performance."""
    for scenario, case in zip(scenarios, cases):
        env = InvestigationEnv(scenario, max_steps=len(case["probes"]))
        for probe in case["probes"]:
            observation = env.call(probe["tool"], **probe["args"])
            if observation.error or probe["contains"] not in observation.text:
                raise ValueError(f"Unreachable clue in {scenario.id}: {probe['contains']}")


def build(source_path: Path, destination: Path):
    source_bytes = source_path.read_bytes()
    source = json.loads(source_bytes)
    if source.get("suite_id") != "inquest-authored-v1" or source.get("source_format_version") != 1:
        raise ValueError("Unsupported authored source")
    scenarios = construct(source)
    if len(scenarios) != 16 or len({s.id for s in scenarios}) != 16:
        raise ValueError("authored-v1 requires 16 unique cases")
    review_probes(scenarios, source["cases"])
    casebook = {
        "suite_id": source["suite_id"], "format_version": 1,
        "author": source["author"], "review_status": source["review_status"],
        "cases": [{key: deepcopy(case[key]) for key in
                   ("id", "title", "fault_type", "root_service", "fix", "difficulty", "onset",
                    "narrative", "distractors", "missing_logs", "probes")}
                  for case in source["cases"]],
    }
    data = ("\n".join(scenario.to_json() for scenario in scenarios) + "\n").encode()
    try:
        base_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.SubprocessError):
        base_revision = None
    files = {"authoring.json": source_bytes, "holdout.jsonl": data, "casebook.json": encoded(casebook)}
    manifest = {
        "suite_id": source["suite_id"], "format_version": 2, "labels_included": True,
        "freeze_date_utc": source["freeze_date_utc"], "author": source["author"],
        "construction": source["construction"], "review_status": source["review_status"],
        "provenance": {
            "base_revision": base_revision,
            "source_hashes_are_authoritative": True,
            "note": "Source hashes identify the construction code even when built from uncommitted changes.",
            "source_sha256": {str(path): digest((ROOT / path).read_bytes()) for path in
                              (Path("scripts/build_authored_v1.py"), Path("src/inquest/scenario.py"), Path("src/inquest/topology.py"))},
            "authoring_sha256": digest(source_bytes),
        },
        "sets": {"holdout": {
            "file": "holdout.jsonl", "split": "holdout", "difficulty": "mixed",
            "count": len(scenarios), "bytes": len(data), "sha256": digest(data),
            "scenario_ids": [s.id for s in scenarios],
            "fault_counts": dict(sorted(Counter(s.fault_type for s in scenarios).items())),
            "difficulty_counts": dict(sorted(Counter(s.difficulty for s in scenarios).items())),
        }},
        "limitations": ["Public synthetic fixed-topology cases", "Sparse logs and piecewise-linear metrics",
                        "AI-authored and single-author reviewed; no independent domain-expert review",
                        "No model fitting, prompt tuning, or agent results used during construction"],
    }
    files["manifest.json"] = encoded(manifest)
    files["SHA256SUMS"] = "".join(f"{digest(content)}  {name}\n" for name, content in sorted(files.items())).encode()
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise ValueError("Refusing to overwrite a nonempty suite directory")
    for name, content in files.items():
        (destination / name).write_bytes(content)
    return scenarios


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "datasets/authored-v1/authoring.json")
    parser.add_argument("--output-dir", type=Path, required=True, help="New or empty review directory")
    args = parser.parse_args()
    cases = build(args.source, args.output_dir)
    print(f"Rendered and checked {len(cases)} authored cases in {args.output_dir}")


if __name__ == "__main__":
    main()
