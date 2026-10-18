"""Prompt privately for a key and run the 16-case, budget-five Gemini evaluation."""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

from inquest.cli import main


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true", help="Resume this same saved configuration")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    key = getpass.getpass("Paste Gemini API key, then press Enter: ").strip()
    if not key:
        parser.error("No API key entered")
    os.environ["GEMINI_API_KEY"] = key
    print("Evaluating 16 incidents at budget 5, with 15 seconds between API requests.", flush=True)
    print("Allow roughly 20–35 minutes. Each completed incident will print a status line.", flush=True)
    command = [
        "run", "--suite", str(root / "datasets/authored-v1"), "--set", "holdout",
        "--backend", "compatible", "--api-key-env", "GEMINI_API_KEY",
        "--base-url", "https://generativelanguage.googleapis.com/v1beta/openai",
        "--model", "gemini-3.5-flash-lite", "--omit-temperature",
        "--token-limit-param", "max_tokens", "--json-mode",
        "--max-output-tokens", "2048", "--max-model-turns", "8",
        "--request-interval", "15", "--progress", "--budgets", "5",
        "--output", str(root / "runs/gemini-3-5-authored-budget5-v1"),
    ]
    if args.resume:
        command.append("--resume")
    return main(command)


if __name__ == "__main__":
    raise SystemExit(run())
