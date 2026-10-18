"""Load authored frozen inputs and make two predetermined, unscored queries."""
from dataclasses import asdict
import json
from pathlib import Path

from inquest.env import InvestigationEnv
from inquest.frozen import load_frozen_set


def main():
    directory = Path(__file__).resolve().parents[1] / "datasets/authored-v1"
    cases = load_frozen_set(directory, "holdout")
    manifest = json.loads((directory / "manifest.json").read_text())
    # Evaluator retains labeled cases. This manual example is not an agent.
    env = InvestigationEnv(cases[0], max_steps=2)
    observations = [env.call("get_alerts"), env.call("search_logs", service="auth")]
    print(json.dumps({
        "kind": "manual_authored_case_demo", "suite_id": manifest["suite_id"],
        "set": "holdout", "case_count": len(cases),
        "set_sha256": manifest["sets"]["holdout"]["sha256"],
        "observations": [asdict(o) for o in observations], "steps_left": env.steps_left,
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
