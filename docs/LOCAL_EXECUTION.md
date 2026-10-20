# Run an investigation from the browser

This opt-in local server connects the browser to the existing budgeted runner. It supports the built-in **offline heuristic only**. It needs no API key, model server, paid infrastructure, database server, or new runtime package. SQLite is included with the supported Python installation.

The public application (`python app.py`, including its hosted deployment) does not register execution endpoints or start a worker. The local service runs from the repository on Linux or macOS; it is not a multi-user or production hosting service.

## Start

From Inquest with the virtual environment activated, stop any previous server with **Ctrl+C**, then run:

```bash
python scripts/serve_local.py
```

Open the exact printed address: <http://127.0.0.1:8000/investigate>. The server binds only to `127.0.0.1`, checks its Host/Origin, and runs without a debugger or reloader. A different hostname such as `localhost` is intentionally rejected. If port 8000 is in use, stop the old server or select a different port:

```bash
python scripts/serve_local.py --port 8001
```

1. Select `authored-v1` or `authored-v2`, a case, and a budget of 5, 10 or 20 calls.
2. Click **Start investigation**. The page polls local job state and displays actual durable observations and calls used. The heuristic often finishes before the first poll, so its full timeline may appear together; no artificial inference delay is added.
3. Reload the page to verify the job remains available. Job selection uses the URL, and history comes from the local store rather than browser storage.
4. Select **Open saved result** to inspect citations, grades, usage and all recorded attempts in the existing viewer. No folder selection is needed for these managed jobs.

The heuristic is a fixed earliest-alert procedure with a constant, uncalibrated confidence. It does not interpret or improve itself from the V2 prompt. The run records V2 as the episode prompt configuration and the actual heuristic identity separately. These are software demonstrations, not new LLM evaluation evidence. A completed job may still contain an incorrect diagnosis or invalid report.

## Jobs, cancellation and recovery

| State | Meaning |
|---|---|
| `queued` | Accepted and waiting for the single worker |
| `running` | Runner is executing the selected case |
| `cancelling` | Cancellation requested; waiting for a cooperative checkpoint |
| `completed` | A report was saved; inspect its grade separately |
| `failed` | Execution or strict-resume validation failed; inspect the saved error/result |
| `cancelled` | Stopped before completion; existing attempts remain on disk |
| `interrupted` | Server stopped or restarted before SQL completion; explicit resume required |

Queued cancellation runs no tools. Running cancellation is checked before and after backend turns. A finished result wins a cancellation arriving after the last checkpoint; completed outcomes are never rewritten to cancelled. This is cooperative cancellation, not forced interruption of arbitrary code.

Stop with **Ctrl+C**. At restart, queued/running/cancelling records become interrupted; none starts silently. Click **Resume investigation** for an interrupted or cancelled job. The existing strict runner resumes under identical source, data, prompt and backend identity, preserves old journals and starts a new attempt only where no completed result exists. If a result was saved immediately before a crash, it is reused without executing the episode again.

Source identity includes the package hashes, Git revision/dirty state and the local worker source hash. Committing, pulling, editing source or changing datasets between attempts can reject strict resume. Finish active work before changing the checkout, or start a new job under the new revision. Local development runs explicitly record `allow_dirty` behavior through their dirty provenance; they are not clean published experiments.

A crash before the first manifest write can leave an empty header directory. If it contains only lock/pending-header files, recovery preserves it as an `ID-unstarted-*` directory before starting the unexecuted job. A missing manifest alongside saved episode data is rejected for manual inspection rather than silently rerunning that data.

## Storage and limits

The default store is `runs/local-web/`, ignored by Git. It contains `jobs.sqlite3`, a lifetime ownership lock, and one run directory per generated job ID. A second server cannot own the same store. Individual directories retain the normal `run.json`, `summary.json`, `episodes/.../attempt-NNN.jsonl`, and `result.json` format. They also work with the existing folder viewer and CLI summary/replay tools.

One worker executes at a time, with at most 8 active jobs and 200 total job records per store. Each job selects one case, at most 20 tool calls and 32 backend turns. A 120-second elapsed-time check runs at cooperative checkpoints; it is not an operating-system kill timer. The built-in heuristic makes no provider/network request. API request bodies are limited to 16 KiB and the managed viewer handoff to 20 MiB. Use the folder viewer for larger artifacts.

To keep a separate experiment history, choose a new store explicitly:

```bash
python scripts/serve_local.py --data-dir runs/local-web-next
```

Keep the SQLite store and run directories together. No automatic deletion, overwrite of completed results, paid fallback, credential entry or production repair is offered. Files remain on disk after the browser closes.

## Implementation and boundaries

- `scripts/serve_local.py` starts a single opt-in loopback server and owns shutdown.
- `local_jobs.py` uses a process ownership lock, SQLite transactions, idempotent start keys and one worker. Shutdown rejects/drains mutations before releasing ownership.
- `local_app.py` registers the local API only in the opt-in app, limits input, checks loopback/Host/Origin and uses a rotating same-origin request token. HTTP responses disable caching.
- `run_experiment` now accepts an optional explicit case selection and a detached event hook, called after journal flush/fsync. Existing CLI defaults, episode loop, tools, prompts, grader and frozen data stay intact.
- The local `/runs?job=ID` response embeds bounded saved files as escaped inert JSON. The viewer still uses `connect-src 'none'`; the default folder viewer retains its no-upload behavior. The execution page connects only to its own local server and loads local assets/system fonts.

The service is for one trusted local user. SQLite coordinates the job lifecycle, not distributed agents or cross-machine workers. Direct local file edits are not authenticated. Hardware/power-loss durability, Windows locking, hosted model execution from the browser, and production deployment remain unverified or out of scope.

See [Testing](TESTING.md) for lifecycle and browser checks. Apply, review, commit, push and merge through the maintainer's VS Code workflow.
