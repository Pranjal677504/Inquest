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
    if not isinstance(name, str) or not re.fullmatch(r"(?:dev|test|ood)-(?:easy|medium|hard)", name):
        raise ValueError("Unknown frozen set name")
    checksums = {}
    for line in (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (manifest\.json|(?:dev|test|ood)-(?:easy|medium|hard)\.jsonl)", line)
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
    if manifest.get("format_version") != 1 or manifest.get("suite_id") != "inquest-smoke-v1":
        raise ValueError("Unsupported frozen suite format or version")
    entry = manifest.get("sets", {}).get(name)
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
    split, difficulty = name.split("-")
    if entry.get("split") != split or entry.get("difficulty") != difficulty:
        raise ValueError("Manifest generation settings do not match set name")
    if any(s.split != split or s.difficulty != difficulty for s in scenarios):
        raise ValueError("Scenario generation settings do not match set name")
    if len({s.id for s in scenarios}) != len(scenarios):
        raise ValueError("Frozen set contains duplicate scenario IDs")
    return scenarios
