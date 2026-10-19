"""Exercise the private-key launcher without calling an external provider."""
from pathlib import Path
import runpy
import sys

import pytest


@pytest.mark.parametrize("resume", [False, True])
@pytest.mark.parametrize("policy", ["v1", "v2"])
def test_gemini_launcher_uses_full_suite_and_keeps_key_out_of_arguments(monkeypatch, capsys, resume, policy):
    captured = []
    monkeypatch.setenv("GEMINI_API_KEY", "before-test")
    monkeypatch.setattr("getpass.getpass", lambda prompt: " synthetic-test-key ")
    monkeypatch.setattr("inquest.cli.main", lambda argv: captured.append(argv) or 0)
    monkeypatch.setattr(sys, "argv", ["run_gemini_eval.py", "--policy", policy] + (["--resume"] if resume else []))
    path = Path(__file__).resolve().parents[1] / "scripts/run_gemini_eval.py"
    namespace = runpy.run_path(str(path))
    assert namespace["run"]() == 0
    arguments = captured[0]
    assert "--case-limit" not in arguments
    assert arguments[arguments.index("--request-interval") + 1] == "15"
    assert arguments[arguments.index("--budgets") + 1] == "5"
    assert arguments[arguments.index("--policy") + 1] == policy
    assert "--pause-on-rate-limit" in arguments
    assert Path(arguments[arguments.index("--output") + 1]).name == (
        "gemini-3-5-authored-budget5-v1" if policy == "v1" else "gemini-3-5-authored-budget5-policy-v2")
    assert ("--resume" in arguments) == resume
    assert "synthetic-test-key" not in repr(arguments) + capsys.readouterr().out
    # Environment handoff exists only in this test process; pytest restores it.
    import os
    assert os.environ["GEMINI_API_KEY"] == "synthetic-test-key"


def test_empty_key_never_starts_a_model_request(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda prompt: " ")
    monkeypatch.setattr("inquest.cli.main", lambda argv: pytest.fail("Must not start without a key"))
    monkeypatch.setattr(sys, "argv", ["run_gemini_eval.py"])
    path = Path(__file__).resolve().parents[1] / "scripts/run_gemini_eval.py"
    with pytest.raises(SystemExit):
        runpy.run_path(str(path))["run"]()
