# Review saved investigations

The saved-run viewer opens existing runner artifacts locally in the browser. It makes no model calls and needs no API key, database, or additional runtime package. It does not execute repairs or regrade cases.

## Start and open a run

From the repository with your virtual environment activated:

```bash
python app.py
```

Open <http://127.0.0.1:8000/runs>, or follow **Open saved investigations** from the incident workbench. Select **Choose run folder**, then select **one** completed or partial run, for example `runs/gemini-3-5-authored-v2-budget5-policy-v2`. Do not select the parent `runs/` folder containing multiple runs. Browser folder-access confirmation is expected. Extract `.tar.gz` archives before selecting the extracted run folder.

The viewer reads only `run.json`, per-episode `result.json`, and `attempt-NNN.jsonl` files. It ignores summary files and unrelated files, including environment files. For browsers without folder selection, use **Folder picker unavailable?** to select `run.json` first, then add an episode's result and matching journal; repeat for additional episodes.

Files are read in this browser tab, without upload, network access, browser storage, or model calls. The `/runs` page has a Content Security Policy that disallows connections and external assets. It uses local styles and system fonts. Clear review or reload to discard the imported review. This is not encryption or file deletion: originals remain on disk, and browser memory is managed by the browser.

## What to inspect

- Completion counts include every manifest job; missing results remain unfinished. Filter accepted reports, unaccepted reports, execution errors, or unfinished episodes.
- Select an episode to inspect its final diagnosis, proposed action, confidence, saved validation and correctness checks, usage, and missing values.
- Select an actual citation to focus its observation in the tool timeline. Unavailable or duplicate observation IDs have no citation link. Tool arguments, returned text, structured data, and tool errors are displayed as text.
- The timeline uses the result's exact attempt. If its journal is absent, an older attempt is never substituted. For an unfinished episode, the latest imported attempt is shown and remains unfinished even if a report event exists.
- Provider/backend errors, retried transport errors, protocol errors and incorrect diagnoses remain distinct. An absent report after a backend error is not described as a malformed submitted report.
- Unreadable journal lines and sequence gaps are labeled incomplete. Mismatched identities or unsupported manifests are rejected. Imports have limits of 1000 jobs, 5000 selected files, 20 MiB per relevant file, 128 MiB combined relevant files, and 10000 events per journal.

The browser checks artifact structure and manifest/result/journal identities, not authenticity, cryptographic integrity, source compatibility, or correctness of saved grades. It does not rerun the evaluator. Use the CLI replay/comparison workflows for stronger verification. Coarse relevance does not establish claim-level evidence support. Public synthetic cases do not establish production performance.

## Open a paired comparison

Generate a comparison using the existing CLI, which checks compatible suites, scoring sources and model settings:

```bash
python -m inquest compare \
  --baseline runs/gemini-3-5-authored-v2-budget5-policy-v2 \
  --candidate runs/gemini-3-5-authored-v2-budget5-policy-v3 \
  > runs/authored-v2-policy-comparison.json
```

Then choose that JSON under **Inspect a saved comparison**. The viewer displays saved group counts, evidence successes, percentage-point changes, per-case outcomes, usage, operational differences and limitations. It does not infer compatibility or claim to have rerun the CLI checks. Imported comparison files can also be edited externally; treat them as saved claims until verified.

No live model call is needed for either workflow. Keep run artifacts private unless you intentionally review and publish them. The viewer does not bundle maintainer transcripts, API keys, or evaluation outcomes in its source.

## Development workflow

Keep V2 as the current working evaluation baseline; V3 remains experimental and the launcher default remains V1. This viewer changes neither prompts, runner, grader nor datasets. Local execution controls remain a later milestone.

The maintainer reviews the patch, commits, pushes and merges through VS Code. Browser coverage is described in [Testing](TESTING.md).
