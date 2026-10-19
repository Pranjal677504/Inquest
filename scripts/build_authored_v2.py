"""Render and review authored-v2 into a new directory without model/API calls.

The v1 renderer expands explicit keyframes; it does not dispatch on fault labels.
Probe paths are evaluator-authored reachability checks, not agent performance.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.build_authored_v1 import construct, digest, encoded  # noqa: E402
from inquest.agent_protocol import system_prompt  # noqa: E402
from inquest.env import InvestigationEnv  # noqa: E402
from inquest.grader import grade  # noqa: E402
from inquest.scenario import FAULTS  # noqa: E402

FROZEN_V2_PROMPT = "6c94ffeaf6dbde3eeea84e5d5f1e1f34c24a0b9fd8284bfd13a28a8d9d8a411a"


def review(source, scenarios):
    if len(scenarios) != 16 or [s.id for s in scenarios] != [f"authored-v2-{i:03d}" for i in range(1, 17)]:
        raise ValueError("authored-v2 requires 16 ordered, unique v2 cases")
    if Counter(s.fault_type for s in scenarios) != Counter({fault: 2 for fault in FAULTS}):
        raise ValueError("Require two cases per fault")
    for fault in FAULTS:
        if sorted(s.difficulty for s in scenarios if s.fault_type == fault) != ["hard", "medium"]:
            raise ValueError("Require one medium and one hard case per fault")
    contract = source["evaluation_contract"]
    if contract["policy"] != "v2" or contract["prompt_sha256"] != FROZEN_V2_PROMPT or digest(system_prompt("v2").encode()) != FROZEN_V2_PROMPT:
        raise ValueError("Frozen v2 policy differs; create a new experiment version")
    if contract["budget"] != 5:
        raise ValueError("Review budget must be five")
    for scenario, case in zip(scenarios, source["cases"]):
        probes = case["probes"]
        if not 1 <= len(probes) <= contract["budget"] or probes[0]["tool"] != "get_alerts":
            raise ValueError("Review path must start with alerts and fit the tool budget")
        roles = Counter(p["role"] for p in probes)
        if roles["support"] < 2 or roles["counterevidence"] < 1:
            raise ValueError("Review requires support and counterevidence")
        if not case["narrative"] or not case["distractors"] or not scenario.events:
            raise ValueError("Missing causal explanation or distractor")
        env = InvestigationEnv(scenario, max_steps=contract["budget"])
        citations = []
        for probe in probes:
            observation = env.call(probe["tool"], **probe["args"])
            if observation.error or not probe["contains"] or probe["contains"] not in observation.text:
                raise ValueError(f"Unreachable clue in {scenario.id}: {probe['contains']}")
            if probe["role"] == "support":
                citations.append(observation.id)
        report = {"service": scenario.root_service, "fault_type": scenario.fault_type,
                  "fix": deepcopy(scenario.fix), "evidence": citations, "confidence": 0.5}
        score = grade(scenario, env, report)
        if not score["success"] or not score["evidence_relevant_success"]:
            raise ValueError(f"Authored path does not satisfy the grader: {scenario.id}")


def build(source_path: Path, destination: Path):
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Refusing to overwrite a nonempty suite directory")
    source_bytes = source_path.read_bytes()
    source = json.loads(source_bytes)
    if source.get("suite_id") != "inquest-authored-v2" or source.get("source_format_version") != 1:
        raise ValueError("Unsupported authored source")
    scenarios = construct(source)
    review(source, scenarios)
    fields = ("id", "title", "fault_type", "root_service", "fix", "difficulty", "onset",
              "narrative", "distractors", "missing_logs", "probes")
    book = {"suite_id": source["suite_id"], "format_version": 1, "author": source["author"],
            "review_status": source["review_status"],
            "cases": [{key: deepcopy(case[key]) for key in fields} for case in source["cases"]]}
    data = ("\n".join(s.to_json() for s in scenarios) + "\n").encode()
    files = {"authoring.json": source_bytes, "holdout.jsonl": data, "casebook.json": encoded(book)}
    paths = ("scripts/build_authored_v2.py", "scripts/build_authored_v1.py", "src/inquest/scenario.py",
             "src/inquest/topology.py", "src/inquest/env.py", "src/inquest/grader.py", "src/inquest/agent_protocol.py")
    manifest = {
        "suite_id": source["suite_id"], "format_version": 2, "labels_included": True,
        **{key: source[key] for key in ("freeze_date_utc", "author", "construction", "review_status", "evaluation_contract")},
        "provenance": {"source_hashes_are_authoritative": True,
                       "source_sha256": {p: digest((ROOT / p).read_bytes()) for p in paths},
                       "authoring_sha256": digest(source_bytes)},
        "sets": {"holdout": {"file": "holdout.jsonl", "split": "holdout", "difficulty": "mixed",
                             "count": len(scenarios), "bytes": len(data), "sha256": digest(data),
                             "scenario_ids": [s.id for s in scenarios],
                             "fault_counts": dict(sorted(Counter(s.fault_type for s in scenarios).items())),
                             "difficulty_counts": dict(sorted(Counter(s.difficulty for s in scenarios).items()))}},
        "limitations": ["Public synthetic fixed-topology cases; shared ontology and baseline telemetry with authored-v1",
                        "New mechanisms authored after inspecting v1 development results; not independent or secret holdout data",
                        "Same author prepared cases and policy; independent expert review remains pending",
                        "Frozen v2 prompt predates these cases; no live model calls, rejection sampling, or tuning on this suite",
                        "Scripted paths prove clue reachability and grading compatibility, not model performance or unique causality",
                        "Legacy coarse evidence metric unchanged; health is intentionally included where relevant in this new suite"],
    }
    files["manifest.json"] = encoded(manifest)
    files["SHA256SUMS"] = "".join(f"{digest(content)}  {name}\n" for name, content in sorted(files.items())).encode()
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (destination / name).write_bytes(content)
    return scenarios


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "datasets/authored-v2/authoring.json")
    parser.add_argument("--output-dir", type=Path, required=True, help="New or empty review directory")
    args = parser.parse_args()
    cases = build(args.source, args.output_dir)
    print(f"Rendered and checked {len(cases)} fresh authored cases in {args.output_dir}")


if __name__ == "__main__":
    main()
