"""Saved-run review uses invented fixtures and never calls a model provider."""
import json
from threading import Thread

import pytest
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import app


@pytest.fixture(scope="module")
def viewer_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def viewer_url():
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/runs"
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()


@pytest.fixture
def viewer(viewer_browser, viewer_url):
    context = viewer_browser.new_context()
    page = context.new_page()
    errors, requests = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(viewer_url)
    page.on("request", lambda r: requests.append(r.url))
    yield page
    assert errors == []
    assert requests == []  # No uploads, model requests, analytics or remote fonts.
    assert page.evaluate("Object.keys(localStorage).length + Object.keys(sessionStorage).length") == 0
    context.close()


@pytest.fixture
def run_folder(tmp_path):
    folder = tmp_path / "invented-run"
    folder.mkdir()
    jobs = [{"job_id": f"case-{i:04}-budget-005", "case_id": f"demo-{i:03}",
             "max_steps": 5, "difficulty": "hard"} for i in range(1, 4)]
    manifest = {"format_version": 1, "fingerprint": "a" * 64, "jobs": jobs,
                "config": {"episode_options": {"policy": "v2"},
                           "backend": {"kind": "scripted"}, "suite": {"suite_id": "demo", "set_name": "dev"}}}
    (folder / "run.json").write_text(json.dumps(manifest))
    report = {"service": "search", "fault_type": "traffic_surge",
              "fix": {"action": "scale_up", "target": "search"},
              "confidence": .7, "evidence": ["o1", "o9"],
              "summary": "<img src=x onerror=alert('unsafe')>"}
    for i, job in enumerate(jobs[:2]):
        directory = folder / "episodes" / job["job_id"]
        directory.mkdir(parents=True)
        score = {"scenario": job["case_id"], "steps": 1, "success": not i,
                 "evidence_relevant_success": not i, "submitted": not i, "report_valid": not i,
                 "service_ok": not i, "type_ok": not i, "fix_ok": not i,
                 "brier": .09 if not i else None,
                 "validation_errors": [] if not i else ["report: expected object"]}
        result = {**job, "fingerprint": "a" * 64, "attempt": 1,
                  "latency_seconds": 1.2, "score": score, "protocol_errors": 0,
                  "status": "reported" if not i else "backend_error",
                  "error_code": None if not i else "provider_response_missing_content",
                  "report": report if not i else None, "usage": {"input_usage_missing_calls": i}}
        (directory / "result.json").write_text(json.dumps(result))
        events = [{**job, "fingerprint": "a" * 64, "attempt": 1, "seq": 1, "kind": "episode_started"},
                  {"seq": 2, "kind": "observation", "steps_left": 4,
                   "observation": {"id": "o1", "tool": "query_metric", "args": {"service": "search", "metric": "rps"},
                                   "text": "Request rate rose twelvefold <script>unsafe()</script>", "data": {"ratio": 12}, "error": None}},
                  {"seq": 3, "kind": "episode_finished", **result}]
        if i:
            events.insert(2, {"seq": 3, "kind": "backend_error", "code": "provider_response_missing_content"})
            events[-1]["seq"] = 4
        (directory / "attempt-001.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return folder


def open_run(page, folder):
    page.locator("#run-folder").set_input_files(str(folder))
    expect(page.locator("#import-status")).to_contain_text("Opened 3 planned episodes")


def test_folder_citations_backend_failure_and_unfinished(viewer, run_folder):
    open_run(viewer, run_folder)
    expect(viewer.locator("#run-stats")).to_contain_text("2 / 3")
    expect(viewer.locator("#episode-list button")).to_have_count(3)
    expect(viewer.locator("#episode-detail")).to_contain_text("<img src=x")
    assert viewer.locator("#episode-detail img, #episode-detail script").count() == 0
    citation = viewer.get_by_role("button", name="o1", exact=True)
    citation.focus()
    citation.press("Enter")
    expect(viewer.locator("#observation-0")).to_be_focused()
    expect(viewer.locator("#episode-detail")).to_contain_text("o9 · unavailable")
    viewer.locator("#episode-filter").select_option("errors")
    expect(viewer.locator("#episode-list button")).to_have_count(1)
    expect(viewer.locator("#episode-detail")).to_contain_text("provider_response_missing_content")
    expect(viewer.locator("#episode-detail")).to_contain_text("does not mean a malformed report was submitted")
    viewer.locator("#episode-filter").select_option("unfinished")
    expect(viewer.locator("#episode-detail")).to_contain_text("No saved result")
    viewer.locator("#clear").click()
    expect(viewer.locator("#run-review")).to_be_hidden()
    expect(viewer.locator("#episode-detail")).to_be_empty()


def test_bad_import_retains_review_and_missing_journal_is_explicit(viewer, run_folder, tmp_path):
    open_run(viewer, run_folder)
    bad = tmp_path / "bad" / "run.json"
    bad.parent.mkdir()
    bad.write_text('{"format_version":1}')
    viewer.locator("#run-files").set_input_files(str(bad))
    expect(viewer.locator("#import-error")).to_contain_text("Unsupported run.json")
    expect(viewer.locator("#run-title")).to_have_text("invented-run")
    viewer.locator("#clear").click()
    result = run_folder / "episodes/case-0001-budget-005/result.json"
    viewer.locator("#run-files").set_input_files([str(run_folder / "run.json"), str(result)])
    expect(viewer.locator("#import-status")).to_contain_text("Opened 3 planned episodes")
    expect(viewer.locator("#episode-detail")).to_contain_text("Matching attempt journal not imported")
    viewer.locator("#run-files").set_input_files(str(result.parent / "attempt-001.jsonl"))
    expect(viewer.locator("#observation-0")).to_be_visible()


def test_identity_mismatch_rejected_and_truncated_journal_labeled(viewer, run_folder):
    result_path = run_folder / "episodes/case-0001-budget-005/result.json"
    original = result_path.read_text()
    result_path.write_text(original.replace('"a' + 'a' * 63 + '"', '"' + 'b' * 64 + '"'))
    viewer.locator("#run-folder").set_input_files(str(run_folder))
    expect(viewer.locator("#import-error")).to_contain_text("does not match")
    expect(viewer.locator("#run-review")).to_be_hidden()
    result_path.write_text(original)
    with (result_path.parent / "attempt-001.jsonl").open("a") as stream:
        stream.write('{"seq":4,"kind":')
    open_run(viewer, run_folder)
    expect(viewer.locator("#episode-detail")).to_contain_text("Unreadable journal line")


def test_multiple_runs_rejected_and_prior_attempt_never_supplies_citations(viewer, run_folder):
    result_path = run_folder / "episodes/case-0001-budget-005/result.json"
    data = json.loads(result_path.read_text())
    data["attempt"] = 2
    result_path.write_text(json.dumps(data))
    open_run(viewer, run_folder)
    expect(viewer.locator("#episode-detail")).to_contain_text("Matching attempt journal not imported")
    assert viewer.locator(".citation").count() == 0
    # An entire parent runs/ directory must not mix manifests and episodes.
    other = run_folder.parent / "other"
    other.mkdir()
    manifest = json.loads((run_folder / "run.json").read_text())
    manifest["fingerprint"] = "b" * 64
    (other / "run.json").write_text(json.dumps(manifest))
    viewer.locator("#run-folder").set_input_files(str(run_folder.parent))
    expect(viewer.locator("#import-error")).to_contain_text("Multiple runs selected")


def test_saved_comparison_and_mobile_layout(viewer, run_folder, tmp_path):
    comparison = {"kind": "paired_policy_comparison", "baseline": {"policy": "v1", "fingerprint": "a" * 64},
                  "candidate": {"policy": "v2", "fingerprint": "b" * 64},
                  "groups": {"budget_5/all": {"cases": 2, "baseline_successes": 0, "candidate_successes": 1,
                             "baseline_evidence_successes": 0, "candidate_evidence_successes": 1,
                             "success_delta_percentage_points": 50}},
                  "cases": [], "limitations": ["Invented synthetic data; no generalization claim."]}
    path = tmp_path / "comparison.json"
    path.write_text(json.dumps(comparison))
    viewer.locator("#comparison-file").set_input_files(str(path))
    expect(viewer.locator("#comparison-view table")).to_contain_text("budget_5/all")
    expect(viewer.locator("#comparison-view")).to_contain_text("no generalization claim")
    viewer.locator("#comparison-file").set_input_files(str(run_folder / "run.json"))
    expect(viewer.locator("#comparison-error")).to_contain_text("Expected JSON from")
    viewer.set_viewport_size({"width": 390, "height": 844})
    open_run(viewer, run_folder)
    assert viewer.evaluate("document.documentElement.scrollWidth <= innerWidth")
    viewer.locator("#clear").click()
    expect(viewer.locator("#comparison-view")).to_be_empty()


def test_import_cannot_reappear_after_clear(viewer, run_folder):
    viewer.evaluate("""() => {
      const read = File.prototype.text;
      File.prototype.text = function() {
        return new Promise(resolve => {
          window.releaseRead = async () => resolve(await read.call(this));
        });
      };
    }""")
    viewer.locator("#run-folder").set_input_files(str(run_folder))
    viewer.wait_for_function("typeof releaseRead === 'function'")
    viewer.locator("#clear").click()
    viewer.evaluate("async () => { await releaseRead(); await new Promise(requestAnimationFrame); }")
    expect(viewer.locator("#run-review")).to_be_hidden()
    expect(viewer.locator("#import-status")).to_have_text("No run open.")
