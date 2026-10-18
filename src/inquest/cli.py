"""Explicit offline/model runs and credential-free saved-run inspection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .backends import AlertHeuristic, BackendError, HTTPBackend
from .runner import RunError, read_run_manifest, run_experiment, summarize


def parser():
    root = argparse.ArgumentParser(prog="inquest", description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run a frozen suite under explicit tool budgets")
    run.add_argument("--suite", type=Path, required=True)
    run.add_argument("--set", dest="set_name", required=True)
    run.add_argument("--backend", choices=("heuristic", "ollama", "compatible"), required=True)
    run.add_argument("--model")
    run.add_argument("--base-url")
    run.add_argument("--api-key-env", default="INQUEST_API_KEY")
    run.add_argument("--model-revision")
    run.add_argument("--temperature", type=float, default=0.0)
    run.add_argument("--max-output-tokens", type=int, default=768)
    run.add_argument("--timeout", type=float, default=60.0)
    run.add_argument("--retries", type=int, default=2)
    run.add_argument("--json-mode", action="store_true")
    run.add_argument("--budgets", default="5,10,20")
    run.add_argument("--case-limit", type=int)
    run.add_argument("--max-model-turns", type=int, default=32)
    run.add_argument("--max-protocol-errors", type=int, default=2)
    run.add_argument("--max-prompt-chars", type=int, default=100_000)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--allow-dirty", action="store_true")
    saved = commands.add_parser("summarize", help="Summarize saved results without a model")
    saved.add_argument("--run-dir", type=Path, required=True)
    replay = commands.add_parser("replay", help="Print a saved episode journal as JSON")
    replay.add_argument("--run-dir", type=Path, required=True)
    replay.add_argument("--job-id", required=True)
    replay.add_argument("--attempt", type=int)
    return root


def replay(args):
    # Verify saved manifest/results before resolving an episode path.
    summarize(args.run_dir)
    manifest = read_run_manifest(args.run_dir)
    jobs = {job["job_id"]: job for job in manifest["jobs"]}
    if args.job_id not in jobs:
        raise RunError("Unknown job ID")
    directory = args.run_dir / "episodes" / args.job_id
    paths = sorted(directory.glob("attempt-*.jsonl"))
    if args.attempt is not None:
        if args.attempt < 1:
            raise RunError("Attempt must be positive")
        path = directory / f"attempt-{args.attempt:03d}.jsonl"
    elif paths:
        path = paths[-1]
    else:
        raise RunError("Episode has not started")
    events = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            events.append(json.loads(line))
        except ValueError:
            events.append({"kind": "unreadable_journal_line", "line": number})
    return {"job": jobs[args.job_id], "attempt_file": path.name, "events": events}


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "summarize":
            result = summarize(args.run_dir)
        elif args.command == "replay":
            result = replay(args)
        else:
            try:
                budgets = tuple(int(value.strip()) for value in args.budgets.split(","))
            except ValueError:
                raise RunError("Budgets must be comma-separated integers") from None
            if args.backend == "heuristic":
                if args.model or args.base_url:
                    raise RunError("The offline heuristic does not accept a model or endpoint")
                backend = AlertHeuristic()
            else:
                base = args.base_url or ("http://127.0.0.1:11434" if args.backend == "ollama" else None)
                if not base or not args.model:
                    raise RunError("Specify a model, and a base URL for compatible providers")
                backend = HTTPBackend(
                    provider=args.backend, model=args.model, base_url=base,
                    api_key_env=args.api_key_env, model_revision=args.model_revision,
                    temperature=args.temperature, max_output_tokens=args.max_output_tokens,
                    timeout=args.timeout, retries=args.retries, json_mode=args.json_mode,
                )
                backend.preflight()
            result = run_experiment(
                suite=args.suite, set_name=args.set_name, backend=backend, budgets=budgets,
                output=args.output, case_limit=args.case_limit, resume=args.resume,
                allow_dirty=args.allow_dirty,
                episode_options={"max_model_turns": args.max_model_turns,
                                 "max_protocol_errors": args.max_protocol_errors,
                                 "max_prompt_chars": args.max_prompt_chars},
            )
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except KeyboardInterrupt:
        print("Interrupted. Completed results are preserved; resume with identical settings.", file=sys.stderr)
        return 130
    except (RunError, BackendError, ValueError, OSError) as exc:
        print(f"inquest: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
