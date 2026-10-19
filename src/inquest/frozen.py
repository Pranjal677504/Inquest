"""Load published incident files after verifying their exact bytes."""

import hashlib
import json
import re
from pathlib import Path

from .scenario import Scenario


def load_frozen_set(directory: str | Path, name: str) -> tuple[Scenario, ...]:
    """Read one versioned set without invoking the incident generator.

    SHA256SUMS verifies the manifest; the manifest and checksum catalog both
    verify the requested JSONL file. Trust the catalog through a pinned Git
    revision: checksums detect changed bytes, not a maliciously replaced catalog.
    Returned bundles include labels and belong on the evaluation side.
    """
    directory = Path(directory)
    if not isinstance(name, str) or not re.fullmatch(r"(?:(?:dev|test|ood)-(?:easy|medium|hard)|holdout)", name):
        raise ValueError("Unknown frozen set name")
    checksums = {}
    for line in (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (manifest\.json|casebook\.json|authoring\.json|holdout\.jsonl|(?:dev|test|ood)-(?:easy|medium|hard)\.jsonl)", line)
        if not match or match[2] in checksums:
            raise ValueError("Invalid checksum catalog")
        checksums[match[2]] = match[1]

    def read_verified(filename):
        if filename not in checksums:
            raise ValueError(f"Missing checksum for {filename}")
        data = (directory / filename).read_bytes()
        if hashlib.sha256(data).hexdigest() != checksums[filename]:
            raise ValueError(f"Checksum mismatch for {filename}")
        return data

    manifest = json.loads(read_verified("manifest.json"))
    if not isinstance(manifest, dict) or type(manifest.get("format_version")) is not int:
        raise ValueError("Invalid frozen suite manifest")
    suite = (manifest.get("suite_id"), manifest.get("format_version"))
    if suite not in (("inquest-smoke-v1", 1), ("inquest-authored-v1", 2), ("inquest-authored-v2", 2)):
        raise ValueError("Unsupported frozen suite format or version")
    authored = suite[0] in ("inquest-authored-v1", "inquest-authored-v2")
    if (name == "holdout") != authored:
        raise ValueError("Set name does not belong to this frozen suite")
    if not isinstance(manifest.get("sets"), dict):
        raise ValueError("Invalid frozen suite set catalog")
    entry = manifest["sets"].get(name)
    filename = f"{name}.jsonl"
    if not isinstance(entry, dict) or entry.get("file") != filename:
        raise ValueError("Frozen set is missing from the manifest")
    data = read_verified(filename)
    if entry.get("sha256") != checksums[filename] or entry.get("bytes") != len(data):
        raise ValueError("Manifest does not match frozen set bytes")
    lines = data.decode("utf-8").splitlines()
    if type(entry.get("count")) is not int or entry["count"] <= 0 or len(lines) != entry["count"]:
        raise ValueError("Frozen set count does not match the manifest")
    scenarios = tuple(Scenario.from_json(line) for line in lines)
    if [s.id for s in scenarios] != entry.get("scenario_ids"):
        raise ValueError("Scenario order or identity does not match the manifest")
    if authored:
        if entry.get("split") != "holdout" or entry.get("difficulty") != "mixed":
            raise ValueError("Invalid authored set settings")
        prefix = manifest["suite_id"].removeprefix("inquest-") + "-"
        if any(s.origin != "authored" or s.split != "holdout" or not s.id.startswith(prefix) for s in scenarios):
            raise ValueError("Authored set contains an incompatible scenario")
        casebook = json.loads(read_verified("casebook.json"))
        if not isinstance(casebook, dict) or casebook.get("suite_id") != manifest["suite_id"] or casebook.get("format_version") != 1 or not isinstance(casebook.get("cases"), list):
            raise ValueError("Invalid authored casebook")
        if any(not isinstance(case, dict) for case in casebook["cases"]):
            raise ValueError("Invalid authored casebook record")
        if [case.get("id") for case in casebook["cases"]] != [s.id for s in scenarios]:
            raise ValueError("Casebook identity or order does not match frozen cases")
        for scenario, case in zip(scenarios, casebook["cases"]):
            if any(case.get(field) != getattr(scenario, field) for field in
                   ("root_service", "fault_type", "fix", "difficulty", "onset")):
                raise ValueError("Casebook labels do not match frozen cases")
        read_verified("authoring.json")
    else:
        split, difficulty = name.split("-")
        if entry.get("split") != split or entry.get("difficulty") != difficulty:
            raise ValueError("Manifest generation settings do not match set name")
        if any(s.origin != "generated" or s.split != split or s.difficulty != difficulty for s in scenarios):
            raise ValueError("Scenario generation settings do not match set name")
    if len({s.id for s in scenarios}) != len(scenarios):
        raise ValueError("Frozen set contains duplicate scenario IDs")
    return scenarios
