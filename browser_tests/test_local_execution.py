"""Browser-to-worker-to-journal workflows with the real offline runner."""
from threading import Event, Thread

import pytest
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import ROOT
from local_app import create_local_app
from local_jobs import JobManager
from inquest.backends import AlertHeuristic, BackendError


@pytest.fixture(scope="module")
def local_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def local_env(tmp_path, local_browser):
    manager = JobManager(tmp_path / "jobs", ROOT / "datasets", autostart=False)
    app = create_local_app(manager)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    url = f"http://127.0.0.1:{server.server_port}"
    app.config["LOCAL_ORIGIN"] = url
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = local_browser.new_context()
    page = context.new_page()
    errors, requests = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: requests.append(r.url))
    page.goto(url + "/investigate")
    expect(page.locator("#start")).to_be_enabled()
    control = {"manager": manager, "server": server, "thread": thread, "url": url}
    try:
        yield page, control
        assert errors == []
        assert all(request.startswith(url + "/") for request in requests)
        assert page.evaluate("Object.keys(localStorage).length + Object.keys(sessionStorage).length") == 0
    finally:
        context.close()
        control["server"].shutdown()
        control["thread"].join(5)
        control["server"].server_close()
        control["manager"].close()


def start(page):
    page.locator("#suite").select_option("authored-v2")
    page.locator("#case").select_option("authored-v2-004")
    page.locator("#start").click()
    expect(page.locator("#job-detail")).to_contain_text("queued")


def test_start_duplicate_submit_refresh_and_open_saved_result(local_env):
    page, env = local_env
    start(page)
    job_id = env["manager"].list()[0]["id"]
    env["manager"].run_next()
    expect(page.locator("#job-detail")).to_contain_text("completed")
    expect(page.locator("#job-detail .timeline li")).not_to_have_count(0)
    page.reload()
    expect(page.locator("#job-detail")).to_contain_text("completed")
    assert env["manager"].get(job_id)["result"]["usage"]["model_requests"] == 0
    page.get_by_role("link", name="Open saved result").click()
    expect(page.locator("#import-status")).to_contain_text("Opened 1 planned episodes")
    expect(page.locator("#episode-detail")).to_contain_text("authored-v2-004")
    citation = page.locator("button.citation").first
    citation.click()
    expect(page.locator(".timeline li:focus")).to_be_visible()


def test_cancel_live_work_and_resume_with_old_attempt_preserved(local_env):
    page, env = local_env
    entered, release = Event(), Event()

    class Pausing(AlertHeuristic):
        def complete(self, messages, emit):
            if len(messages) > 2 and not release.is_set():
                entered.set()
                assert release.wait(8)
            return super().complete(messages, emit)

    env["manager"]._backend_factory = Pausing
    start(page)
    worker = Thread(target=env["manager"].run_next)
    worker.start()
    try:
        assert entered.wait(5)
        expect(page.locator("#job-detail")).to_contain_text("o1 / get_alerts")
        page.get_by_role("button", name="Cancel investigation", exact=True).click()
        release.set()
        worker.join(5)
        expect(page.locator("#job-detail .pill")).to_have_text("cancelled")
        page.get_by_role("button", name="Resume investigation").click()
        expect(page.locator("#job-detail .pill")).to_have_text("queued")
        env["manager"].run_next()
        expect(page.locator("#job-detail .pill")).to_have_text("completed")
        job = env["manager"].list()[0]
        assert env["manager"].get(job["id"])["result"]["attempt"] == 2
    finally:
        release.set()
        worker.join(5)


def test_lost_start_response_retry_reuses_same_job(local_env):
    page, env = local_env

    def lose_response(route):
        if route.request.method == "POST":
            route.fetch()
            route.abort()
            page.unroute("**/api/local/jobs", lose_response)
        else:
            route.continue_()

    page.route("**/api/local/jobs", lose_response)
    page.locator("#start").click()
    expect(page.locator("#execution-error")).to_contain_text("unavailable")
    assert len(env["manager"].list()) == 1
    page.locator("#start").click()
    expect(page.locator("#execution-error")).to_be_hidden()
    expect(page.locator("#job-detail")).to_contain_text("queued")
    assert len(env["manager"].list()) == 1


def test_server_restart_recovers_queue_and_reconnects_without_auto_execution(local_env):
    page, env = local_env
    start(page)
    job_id = env["manager"].list()[0]["id"]
    root = env["manager"].root
    port = env["server"].server_port
    env["server"].shutdown()
    env["thread"].join(5)
    env["server"].server_close()
    env["manager"].close()
    manager = JobManager(root, ROOT / "datasets", autostart=False)
    server = make_server("127.0.0.1", port, create_local_app(manager, env["url"]), threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    env.update(manager=manager, server=server, thread=thread)
    thread.start()
    expect(page.locator("#job-detail .pill")).to_have_text("interrupted", timeout=15000)
    assert not (root / job_id).exists()
    page.reload()
    expect(page.get_by_role("button", name="Resume investigation")).to_be_visible()


def test_execution_error_and_mobile_layout(local_env):
    page, env = local_env

    class Failing(AlertHeuristic):
        def complete(self, messages, emit):
            raise BackendError("scripted_provider_error")

    env["manager"]._backend_factory = Failing
    page.set_viewport_size({"width": 390, "height": 844})
    start(page)
    env["manager"].run_next()
    expect(page.locator("#job-detail .pill")).to_have_text("failed")
    expect(page.locator("#job-detail")).to_contain_text("No final report saved")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.get_by_role("link", name="Open saved result").click()
    expect(page.locator("#episode-detail")).to_contain_text("does not mean a malformed report was submitted")
