# Release walkthrough and checklist

Latest completed walkthrough: [2026-10-25, candidate 6eaa023](releases/2026-10-25/README.md). The unchecked items below are the reusable checklist for each new candidate.

Use this checklist for the replay-based workbench release. Record results for the exact commit being released; an unchecked item is not a verified release claim. Local execution is opt-in and uses the recorded offline heuristic, not a live model evaluation. V2 is the working evaluation baseline; the CLI still defaults to V1 for backward compatibility. See [Testing](TESTING.md), [Local execution](LOCAL_EXECUTION.md), and [Roadmap](ROADMAP.md).

## Record the candidate

- Commit SHA:
- Date, OS, and Python version:
- CI run URL and result:
- Hosted deployment URL and commit:
- Reviewer and notes:

## Fresh checkout

Clone into a separate empty directory, check out the candidate SHA recorded above, and confirm the checkout is clean. With Python 3.14 available, run:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
```

- [ ] Installation and Python tests pass. Record the test count and any skipped tests.
- [ ] Frozen dataset checksums pass for each versioned dataset (`shasum -a 256 -c SHA256SUMS` on macOS, or `sha256sum -c SHA256SUMS` on Linux, from each dataset directory). Record the directories checked.
- [ ] The candidate's GitHub Actions Python matrix and Chromium job pass. Link the run above.

## Public replay workbench

Run `python app.py`, open `http://127.0.0.1:8000/`, and inspect `http://127.0.0.1:8000/runs`.

- [ ] The home page and `/api/health` load.
- [ ] The published sample opens in the saved-run viewer. Inspect at least one accepted and one incorrect episode and confirm the outcome and evidence shown match the saved artifact.
- [ ] No API key or live model call is needed for this replay workflow.

## Opt-in local investigation

Stop the public server, then run `python scripts/serve_local.py` and open `http://127.0.0.1:8000/investigate`. Follow [Local execution](LOCAL_EXECUTION.md) for the job controls.

- [ ] Start one offline investigation with a small budget. Record the case, budget, job ID, and final status.
- [ ] Review events, budget use, and the saved result in the browser.
- [ ] Restart the local server and confirm the saved job remains available.
- [ ] Confirm this local heuristic result is presented separately from model evaluation results.

## Hosted deployment

On the deployment for the candidate commit:

- [ ] Open `/`, `/runs`, and `/api/health`; record the URL and observations.
- [ ] Confirm the public saved sample loads without private run files or provider credentials.
- [ ] Confirm `/investigate` and `/api/local/config` are unavailable on the hosted deployment.

The browser tests in CI exercise a local Flask server. They do not prove the hosted routes work; record the hosted check separately.

## Release decision

- [ ] All applicable checks above have evidence and no unresolved release blocker.
- [ ] Known limitations and any deferred checks are written below before calling the candidate ready.

Decision, limitations, and follow-up:

