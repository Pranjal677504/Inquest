import json
import shutil
from pathlib import Path

import pytest

from inquest.frozen import load_frozen_set
from inquest.scenario import FAULTS

SUITE = Path(__file__).resolve().parents[1] / "datasets" / "smoke-v1"


@pytest.mark.parametrize("split,count", [("dev", 8), ("test", 16), ("ood", 16)])
@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_published_sets_without_generation(split, count, difficulty, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Frozen data must not be regenerated")

    monkeypatch.setattr("inquest.scenario.generate", forbidden)
    monkeypatch.setattr("inquest.generate", forbidden)
    monkeypatch.setattr("random.Random", forbidden)
    scenarios = load_frozen_set(SUITE, f"{split}-{difficulty}")
    assert len(scenarios) == count
    assert {s.fault_type for s in scenarios} == set(FAULTS)
    assert all(sum(s.fault_type == fault for s in scenarios) == count // 8 for fault in FAULTS)


@pytest.fixture
def copied_suite(tmp_path):
    target = tmp_path / "suite"
    target.mkdir()
    for name in ("manifest.json", "SHA256SUMS", "test-hard.jsonl"):
        shutil.copyfile(SUITE / name, target / name)
    return target


@pytest.mark.parametrize("filename", ["manifest.json", "test-hard.jsonl"])
def test_changed_file_rejected_before_parsing(copied_suite, filename):
    path = copied_suite / filename
    data = path.read_bytes()
    path.write_bytes(b"!" + data[1:])
    with pytest.raises(ValueError, match="Checksum mismatch"):
        load_frozen_set(copied_suite, "test-hard")


def test_truncation_rejected(copied_suite):
    path = copied_suite / "test-hard.jsonl"
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(ValueError, match="Checksum mismatch"):
        load_frozen_set(copied_suite, "test-hard")


def test_missing_checksum_rejected(copied_suite):
    path = copied_suite / "SHA256SUMS"
    path.write_text("\n".join(line for line in path.read_text().splitlines() if not line.endswith("test-hard.jsonl")) + "\n")
    with pytest.raises(ValueError, match="Missing checksum"):
        load_frozen_set(copied_suite, "test-hard")


@pytest.mark.parametrize("name", ["../test-hard", "test-hard.jsonl", "test-invalid", "train-hard"])
def test_unknown_set_names(name):
    with pytest.raises(ValueError, match="Unknown frozen set"):
        load_frozen_set(SUITE, name)


def test_manifest_provenance_is_recorded():
    manifest = json.loads((SUITE / "manifest.json").read_text())
    assert len(manifest["generation"]["git_revision"]) == 40
    assert set(manifest["generation"]["source_sha256"]) == {"src/inquest/scenario.py", "src/inquest/topology.py"}
