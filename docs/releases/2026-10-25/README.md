# Release walkthrough verification — 2026-10-25

The replay and opt-in local execution walkthrough passed for commit `6eaa02310185c98439e8177beb50540362cadfdd`. This record covers automated checks driven from the VS Code integrated terminal, including headless Chromium interaction with the actual launch scripts. Screenshots were inspected. It is product behavior evidence; the offline heuristic run is not model evaluation evidence.

## Candidate and environment

- Candidate: [`6eaa023`](https://github.com/Pranjal677504/Inquest/commit/6eaa02310185c98439e8177beb50540362cadfdd) (PR #12 merge).
- Started: `2026-10-25T07:59:33.126008+05:30`.
- Platform: `macOS-27.0.1-arm64-arm-64bit-Mach-O`; Python 3.14.8.
- Dependencies installed in a new virtual environment: Flask 3.1.3, pytest 9.1.1, Playwright 1.64.1.
- Browser: Chromium headless shell 156.0.8078.4.
- [Candidate CI run](https://github.com/Pranjal677504/Inquest/actions/runs/40154371024): all five Python 3.10–3.14 jobs and the Chromium job passed.
- Hosted URL: <https://inquestbench.vercel.app>. Vercel reports production deployment `dpl_5J9fggNKPG1txHGc7nZYg9TjRSZG` as READY for this exact candidate SHA.

## Fresh checkout

- [x] Cloned the public GitHub repository into a new temporary directory and checked out the full candidate SHA with detached HEAD. The checkout was clean before setup and after all verification.
- [x] Installed `.[dev]` in a new Python 3.14 virtual environment. `python -m pytest -q`: **473 passed in 26.59s**, no skips.
- [x] Verified all **18 checksum entries**: ten in smoke-v1, four in authored-v1, and four in authored-v2. All returned OK.
- [x] Installed `.[dev,browser]` and Chromium using `python -m playwright install --only-shell chromium`. `python -m pytest browser_tests -q`: **18 passed in 24.18s**, no skips.
- [x] The candidate CI matrix and browser job passed.

The package commands followed [Testing](../../TESTING.md). The new virtual environment was outside the fresh checkout; no existing project environment or private run files were reused.

## Public replay workbench

- [x] Started the actual `python app.py` entry point on `http://127.0.0.1:8000`. `/`, `/runs`, and `/api/health` returned 200; health returned `{"status":"ok"}`.
- [x] Opened the published sample in the browser and reviewed both episodes: authored-v1-001 was accepted; authored-v1-003 was reported but not accepted. Each displayed five observations. The outcome flags matched the bundled result JSON.
- [x] Followed a citation to its focused timeline observation.
- [x] The sample recorded zero model requests, and its policy label was `earliest-alert-v1`. No credentials were supplied. The viewer made no requests outside its origin and used no browser storage.
- [x] Confirmed `/investigate` and `/api/local/config` returned 404 in the public app.

## Opt-in local investigation

- [x] Stopped the public server and launched the actual `python scripts/serve_local.py --data-dir <isolated-store>` entry point on port 8000.
- [x] Started authored-v2-004 through the browser with a five-call budget. Job `29e14ec35d78813b06cee78a8ba5864e` reached `completed`, used 5 tool calls, and recorded an accepted report with **zero model requests**. This single synthetic result is a smoke check, not an accuracy estimate.
- [x] Reviewed the durable event timeline, budget use, saved report, and citation navigation.
- [x] Stopped and restarted the local server with the same isolated store. The completed job remained available, its saved result reopened, and the result bytes remained identical (SHA-256 `4779457c8e5ad96f8f29675d04a8c68af60d27533e54f1d641ab5c2d9e41fa31`).
- [x] The page explicitly identified the deterministic heuristic and distinguished it from an LLM. Browser requests stayed on the loopback origin, browser storage stayed empty, and no JavaScript page errors occurred.

## Hosted deployment

- [x] `/`, `/runs`, and `/api/health` returned 200 on the production alias; health returned `{"status":"ok"}`.
- [x] Opened both sample outcomes and followed a citation in Chromium. The sample asset bytes matched the candidate checkout (SHA-256 `5dcf9b460bb129036be00695066e293fc5d4dd0ff57801039ced4dbbe988fdc1`).
- [x] `/investigate` and `/api/local/config` returned 404.
- [x] The hosted viewer needed no credentials, loaded no private run files, made no requests outside its origin, and produced no page errors or failed viewer requests.

## Reproduce the launcher checks

Copy the [executed walkthrough script](walkthrough.py) into an empty scratch directory, then run these commands from that directory. Port 8000 must be free. The script starts and stops its own local servers, creates an isolated job store, checks the public production URL, and writes JSON and screenshots alongside itself.

```bash
git clone https://github.com/Pranjal677504/Inquest.git checkout
git -C checkout checkout --detach 6eaa02310185c98439e8177beb50540362cadfdd
python3.14 -m venv venv
venv/bin/python -m pip install -e './checkout[dev,browser]'
venv/bin/python -m playwright install --only-shell chromium
venv/bin/python walkthrough.py
```

The production alias can change after this record; verify its deployment commit before comparing a later hosted result with this historical candidate.

## Evidence and limitations

[Machine-readable results](verification.json), [test output](test-results.txt), [dataset checksums](checksums.txt), [local job screenshot](local-job.png), [hosted accepted result](hosted-accepted.png), and [hosted incorrect result](hosted-incorrect.png). Verify these evidence files with `shasum -a 256 -c SHA256SUMS` from this directory.

The initial walkthrough harness incorrectly applied a same-origin-only assertion to the home page, which intentionally loads Google Fonts. The assertion was corrected to cover the saved-run viewer and the walkthrough passed. Both home pages contacted fonts.googleapis.com and fonts.gstatic.com; the saved viewer and local execution page used their own origins only. Fully offline home-page typography is not established by this run.

Coverage here is macOS ARM64 with Chromium and the existing Linux CI matrix. Windows, Safari/Firefox, power-loss durability, live model execution, and independent causal assessment were not exercised. Dependency versions above are the versions resolved during this run; dependencies are not locked by this record. All servers started for this walkthrough were stopped afterward.

## Decision

- [x] The applicable setup, replay, local execution, restart, and hosted route checks passed for the candidate. No blocker was found in those flows.
- [x] Known limitations and evidence are recorded above.
- [ ] Full release milestone 18: the benchmark card, changelog, and versioned release remain pending maintainer review and completion.

This record completes the walkthrough verification portion of milestone 18. It does not mark the whole release milestone complete.
