"""Real Chromium workflows against the Flask API and committed incident files.

Run separately: python -m pytest browser_tests -q
"""
import re
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import app
from inquest.frozen import load_frozen_set

DATA = Path(__file__).resolve().parents[1] / "datasets" / "smoke-v1"


@pytest.fixture(scope="module")
def server_url():
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser, server_url):
    context = browser.new_context()
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(server_url)
    expect(page.locator("#case-label")).to_have_text("CASE 01 / 8")
    expect(page.locator(".diagnose-btn")).to_be_enabled()
    try:
        yield page
        assert errors == []
    finally:
        context.close()


def fill_answer(page, index=0):
    scenario = load_frozen_set(DATA, "dev-easy")[index]
    page.locator("#answer-service").select_option(scenario.root_service)
    page.locator("#answer-fault").select_option(scenario.fault_type)
    page.locator("#answer-action").select_option(scenario.fix["action"])


def load_second_case(page):
    page.locator("#case-index").select_option("1")
    page.get_by_role("button", name=re.compile("Load incident")).click()
    expect(page.locator("#case-label")).to_have_text("CASE 02 / 8")


def delay_diagnosis_response(page):
    # Hold a fully read HTTP response at the transport boundary; the real API
    # still runs. Release is explicit, so the race does not depend on sleeps.
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.fetch = async (...args) => {
        const response = await original(...args);
        if (args[0] !== '/api/diagnosis') return response;
        const body = await response.text();
        return new Promise(resolve => {
          window.releaseDiagnosis = () => resolve(new Response(body, {
            status: response.status, headers: {'Content-Type': 'application/json'}
          }));
        });
      };
    }""")


def release_diagnosis(page):
    page.evaluate("""async () => {
      window.releaseDiagnosis();
      await new Promise(requestAnimationFrame);
    }""")


def test_frozen_diagnosis_keyboard_navigation_and_case_reset(page):
    expect(page.locator("#topology .node")).to_have_count(8)
    node = page.locator("#topology .node").filter(has_text="postgres")
    node.focus()
    node.press("Enter")
    expect(page.locator("#selected-service")).to_have_text("POSTGRES")
    page.get_by_role("tab", name="Metrics", exact=True).focus()
    page.keyboard.press("ArrowRight")
    expect(page.get_by_role("tab", name="Logs", exact=True)).to_be_focused()
    expect(page.locator("#panel-logs")).to_be_visible()
    page.locator("#log-search").fill("no-such-log-marker")
    expect(page.locator("#log-list")).to_contain_text("No log lines match")
    page.get_by_role("tab", name="Logs", exact=True).focus()
    page.keyboard.press("End")
    expect(page.get_by_role("tab", name="Traces", exact=True)).to_be_focused()
    page.keyboard.press("Home")
    expect(page.locator("#panel-metrics")).to_be_visible()
    fill_answer(page)
    page.locator(".diagnose-btn").click()
    expect(page.locator("#diagnosis-result")).to_contain_text("Correct diagnosis")
    load_second_case(page)
    expect(page.locator("#diagnosis-result")).to_be_hidden()
    expect(page.locator("#answer-service")).to_have_value("")
    fill_answer(page, 1)
    page.locator(".diagnose-btn").click()
    expect(page.locator("#diagnosis-result")).to_contain_text("Correct diagnosis")


@pytest.mark.parametrize("failed", [False, True])
def test_late_diagnosis_cannot_change_a_new_case(page, failed):
    if failed:
        page.route("**/api/diagnosis", lambda route: route.fulfill(
            status=503, json={"error": "Old case unavailable"}))
    delay_diagnosis_response(page)
    fill_answer(page)
    page.locator(".diagnose-btn").click()
    page.wait_for_function("typeof window.releaseDiagnosis === 'function'")
    expect(page.locator(".diagnose-btn")).to_be_disabled()
    load_second_case(page)
    release_diagnosis(page)
    expect(page.locator("#diagnosis-result")).to_be_hidden()
    expect(page.locator("#error-banner")).to_be_hidden()
    expect(page.locator(".diagnose-btn")).to_be_enabled()


def test_duplicate_submit_sends_one_request(page):
    requests = []
    page.on("request", lambda request: requests.append(request.url)
            if request.url.endswith("/api/diagnosis") else None)
    delay_diagnosis_response(page)
    fill_answer(page)
    page.locator(".diagnose-btn").click()
    page.wait_for_function("typeof window.releaseDiagnosis === 'function'")
    # Even a programmatic duplicate submit is ignored while the request runs.
    page.locator("#diagnosis-form").dispatch_event("submit")
    release_diagnosis(page)
    expect(page.locator("#diagnosis-result")).to_contain_text("Correct diagnosis")
    assert len(requests) == 1


def test_failed_case_load_keeps_current_case_and_allows_retry(page):
    fill_answer(page)
    page.route("**/api/incident", lambda route: route.fulfill(
        status=503, content_type="text/html", body="Temporarily unavailable"), times=1)
    page.locator("#case-index").select_option("1")
    page.get_by_role("button", name=re.compile("Load incident")).click()
    expect(page.locator("#error-banner")).to_have_text("Request failed (503)")
    expect(page.locator("#case-label")).to_have_text("CASE 01 / 8")
    expect(page.locator(".diagnose-btn")).to_be_enabled()
    page.get_by_role("button", name=re.compile("Load incident")).click()
    expect(page.locator("#case-label")).to_have_text("CASE 02 / 8")
    expect(page.locator("#error-banner")).to_be_hidden()
    expect(page.locator("#answer-service")).to_have_value("")


def test_generated_case_runs_through_real_api(page):
    page.locator("#source").select_option("generated")
    page.locator("#seed").fill("7")
    page.get_by_role("button", name=re.compile("Load incident")).click()
    expect(page.locator("#case-label")).to_have_text("SEED 7")
    page.locator("#answer-service").select_option("postgres")
    page.locator("#answer-fault").select_option("bad_migration")
    page.locator("#answer-action").select_option("rollback_migration")
    page.locator(".diagnose-btn").click()
    expect(page.locator("#diagnosis-result")).to_contain_text("Correct diagnosis")
