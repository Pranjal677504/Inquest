"""Verify and inspect a frozen set from the checkout, without generating cases."""

import json
from pathlib import Path

from inquest.frozen import load_frozen_set


def main():
    directory = Path(__file__).resolve().parents[1] / "datasets" / "smoke-v1"
    scenarios = load_frozen_set(directory, "test-hard")
    print(json.dumps({
        "suite": "inquest-smoke-v1",
        "set": "test-hard",
        "count": len(scenarios),
        "first_case": scenarios[0].id,
        "last_case": scenarios[-1].id,
        "integrity": "SHA-256 verified",
        "generation": "not used",
    }, indent=2))


if __name__ == "__main__":
    main()
