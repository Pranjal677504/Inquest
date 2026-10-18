"""Real loopback HTTP contract tests; no external provider/model is invoked."""
from collections import deque
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
import urllib.error

import pytest

from inquest.backends import BackendError, HTTPBackend, validate_endpoint


@contextmanager
def server(responses):
    responses = deque(responses)
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.handle_request()
        def do_POST(self):
            self.handle_request()
        def handle_request(self):
            payload = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append({"method": self.command, "path": self.path,
                             "authorization": self.headers.get("Authorization"),
                             "body": json.loads(payload) if payload else None})
            status, body = responses.popleft()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if status == 302:
                self.send_header("Location", "/unexpected-redirect")
            self.end_headers()
            self.wfile.write(body.encode() if isinstance(body, str) else json.dumps(body).encode())
        def log_message(self, *args):
            pass
    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{http.server_port}", requests
    finally:
        http.shutdown()
        thread.join(timeout=5)
        http.server_close()


def completion(**changes):
    return {"model": "provider-model-r1", "id": "response-1", "system_fingerprint": "fp-1",
            "choices": [{"message": {"role": "assistant", "content": '{"kind":"report","report":{}}'},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8}, **changes}


def adapter(base, **changes):
    return HTTPBackend(provider="compatible", model="requested-model", base_url=base + "/v1", **changes)


def test_compatible_request_and_metadata_match_the_contract(monkeypatch):
    monkeypatch.setenv("TEST_MODEL_KEY", "synthetic-test-key")
    events = []
    with server([(200, completion())]) as (base, requests):
        backend = adapter(base, api_key_env="TEST_MODEL_KEY", json_mode=True)
        backend.preflight()
        reply = backend.complete([{"role": "user", "content": "Return JSON"}], lambda k, b: events.append({"kind": k, **b}))
    assert requests[0]["path"] == "/v1/chat/completions"
    assert requests[0]["authorization"] == "Bearer synthetic-test-key"
    assert requests[0]["body"]["max_completion_tokens"] == 768
    assert requests[0]["body"]["response_format"] == {"type": "json_object"}
    assert requests[0]["body"]["stream"] is False
    assert reply.model == "provider-model-r1"
    assert (reply.input_tokens, reply.output_tokens) == (12, 8)
    assert reply.metadata["system_fingerprint"] == "fp-1"
    assert "synthetic-test-key" not in json.dumps([backend.identity(), events])


def test_ollama_preflight_records_digest_without_pulling():
    tags = {"models": [{"name": "installed:small", "digest": "a" * 64}]}
    chat = {"model": "installed:small", "message": {"content": '{}'}, "done": True,
            "prompt_eval_count": 10, "eval_count": 5, "done_reason": "stop"}
    with server([(200, tags), (200, chat)]) as (base, requests):
        backend = HTTPBackend(provider="ollama", model="installed:small", base_url=base, json_mode=True)
        backend.preflight()
        reply = backend.complete([], lambda *args: None)
        assert backend.identity()["local_digest"] == "a" * 64
    assert [r["path"] for r in requests] == ["/api/tags", "/api/chat"]
    assert requests[1]["body"]["options"]["num_predict"] == 768
    assert requests[1]["body"]["format"] == "json"
    assert reply.input_tokens == 10 and reply.output_tokens == 5


def test_ollama_missing_tag_fails_without_download():
    with server([(200, {"models": []})]) as (base, requests):
        backend = HTTPBackend(provider="ollama", model="missing:tag", base_url=base)
        with pytest.raises(BackendError, match="local_model_not_installed"):
            backend.preflight()
    assert len(requests) == 1 and requests[0]["method"] == "GET"


def test_retryable_status_is_bounded_and_recorded(monkeypatch):
    monkeypatch.setattr("inquest.backends.time.sleep", lambda delay: None)
    events = []
    with server([(429, {"error": "rate limit"}), (200, completion())]) as (base, requests):
        backend = adapter(base, retries=1)
        backend.complete([], lambda k, b: events.append({"kind": k, **b}))
    assert len(requests) == 2
    assert [e["attempt"] for e in events if e["kind"] == "transport_attempt"] == [1, 2]
    assert any(e.get("status") == 429 for e in events)


@pytest.mark.parametrize("status", [400, 401, 403, 302])
def test_nonretryable_errors_and_redirects_do_not_leak_response_bodies(status):
    events = []
    with server([(status, {"error": "SENSITIVE_PROVIDER_ERROR_BODY"})]) as (base, requests):
        with pytest.raises(BackendError, match=f"provider_http_{status}") as error:
            adapter(base).complete([], lambda k, b: events.append({"kind": k, **b}))
    assert len(requests) == 1
    assert "SENSITIVE_PROVIDER_ERROR_BODY" not in str(error.value) + json.dumps(events)


def test_network_failure_is_retried_without_logging_raw_error(monkeypatch):
    backend = adapter("http://127.0.0.1:1", retries=2)
    def fail(*args, **kwargs):
        raise urllib.error.URLError("SENSITIVE_TRANSPORT_DETAIL")
    monkeypatch.setattr(backend._opener, "open", fail)
    monkeypatch.setattr("inquest.backends.time.sleep", lambda delay: None)
    events = []
    with pytest.raises(BackendError, match="provider_network_error"):
        backend.complete([], lambda k, b: events.append({"kind": k, **b}))
    assert sum(e["kind"] == "transport_attempt" for e in events) == 3
    assert "SENSITIVE_TRANSPORT_DETAIL" not in json.dumps(events)


@pytest.mark.parametrize("payload,code", [
    ('<html>not JSON</html>', 'invalid_json'),
    ([], 'invalid_shape'),
    ({'choices': []}, 'invalid_choices'),
    (completion(choices=[{'message': {'content': []}}]), 'missing_content'),
    (completion(model=None), 'missing_model'),
])
def test_malformed_provider_responses_fail_explicitly(payload, code):
    with server([(200, payload)]) as (base, requests):
        with pytest.raises(BackendError, match=code):
            adapter(base).complete([], lambda *args: None)
    assert len(requests) == 1


@pytest.mark.parametrize("usage", [None, {}, {"prompt_tokens": True, "completion_tokens": "12"},
                                  {"prompt_tokens": -1, "completion_tokens": -2}])
def test_missing_or_invalid_usage_is_unavailable_not_zero(usage):
    with server([(200, completion(usage=usage))]) as (base, _):
        reply = adapter(base).complete([], lambda *args: None)
    assert reply.input_tokens is None and reply.output_tokens is None


@pytest.mark.parametrize("url", ['http://example.com', 'https://user:secret@example.com',
                                'https://example.com/?key=secret', 'file:///tmp/model', 'https://example.com/#secret'])
def test_endpoint_rejects_credential_urls_or_plaintext_remote_hosts(url):
    with pytest.raises(ValueError):
        validate_endpoint(url)


def test_hosted_preflight_requires_only_the_named_key(monkeypatch):
    monkeypatch.delenv("MISSING_TEST_KEY", raising=False)
    backend = HTTPBackend(provider="compatible", model="m", base_url="https://example.com/v1", api_key_env="MISSING_TEST_KEY")
    with pytest.raises(BackendError, match="api_key_environment"):
        backend.preflight()


@pytest.mark.parametrize("payload", [{"models": {}}, {"models": None}, {"models": [{"name": "local:tag", "digest": ""}]}])
def test_invalid_ollama_model_catalog_fails_before_an_episode(payload):
    with server([(200, payload)]) as (base, _):
        backend = HTTPBackend(provider="ollama", model="local:tag", base_url=base)
        with pytest.raises(BackendError):
            backend.preflight()
