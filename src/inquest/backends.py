"""Small synchronous model adapters with bounded, observable transport retries.

Only the public chat history crosses this boundary. There is no code execution,
filesystem tool, dataset loader, or evaluator object in the backend interface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import json
import math
import os
import time
from typing import Callable, Protocol
import urllib.error
import urllib.parse
import urllib.request

from .agent_protocol import strict_json
from .scenario import FIX_ACTION
from .topology import SERVICES

EventSink = Callable[[str, dict], None]


class BackendError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ModelReply:
    content: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    metadata: dict = field(default_factory=dict)


class Backend(Protocol):
    def identity(self) -> dict: ...
    def complete(self, messages: list[dict], emit: EventSink) -> ModelReply: ...


def token_count(value):
    return value if type(value) is int and value >= 0 else None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def validate_endpoint(base: str) -> str:
    parsed = urllib.parse.urlsplit(base)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Base URL must have a host and no credentials, query, or fragment")
    try:
        local = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        local = parsed.hostname == "localhost"
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise ValueError("Use HTTPS, or HTTP on a loopback host for a local model")
    return base.rstrip("/")


class HTTPBackend:
    """Ollama native chat or compatible chat-completions; never auto-pull models."""
    def __init__(self, *, provider: str, model: str, base_url: str,
                 api_key_env: str = "INQUEST_API_KEY", model_revision: str | None = None,
                 temperature: float | None = 0.0, max_output_tokens: int = 768,
                 token_limit_param: str = "max_completion_tokens",
                 request_interval: float = 0.0,
                 timeout: float = 60.0, retries: int = 2, json_mode: bool = False):
        if provider not in ("ollama", "compatible") or not isinstance(model, str) or not model.strip():
            raise ValueError("Choose ollama or compatible and an explicit model name")
        if temperature is not None and (type(temperature) not in (int, float) or not math.isfinite(temperature) or not 0 <= temperature <= 2):
            raise ValueError("Temperature must be in [0, 2]")
        if token_limit_param not in ("max_completion_tokens", "max_tokens"):
            raise ValueError("Token limit parameter must be max_completion_tokens or max_tokens")
        if provider == "ollama" and token_limit_param != "max_completion_tokens":
            raise ValueError("Token limit parameter applies only to compatible providers")
        if type(max_output_tokens) is not int or max_output_tokens < 1:
            raise ValueError("Output token limit must be positive")
        if type(retries) is not int or not 0 <= retries <= 5:
            raise ValueError("Retries must be an integer in [0, 5]")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 600:
            raise ValueError("Timeout must be in (0, 600]")
        if type(request_interval) not in (int, float) or not math.isfinite(request_interval) or not 0 <= request_interval <= 60:
            raise ValueError("Request interval must be in [0, 60] seconds")
        self.provider, self.model = provider, model
        self.base_url = validate_endpoint(base_url)
        self.api_key_env = api_key_env
        self._api_key = os.environ.get(api_key_env, "")
        self.model_revision = model_revision
        self.temperature, self.max_output_tokens = temperature, max_output_tokens
        self.token_limit_param = token_limit_param
        self.request_interval = request_interval
        self._last_request_at = None
        self.timeout, self.retries, self.json_mode = timeout, retries, json_mode
        self._digest = None
        self._opener = urllib.request.build_opener(_NoRedirect())

    def preflight(self):
        if self.provider == "ollama":
            data = self._request("/api/tags", None, lambda *args: None)
            if not isinstance(data.get("models"), list):
                raise BackendError("provider_response_invalid_model_list")
            matches = [entry for entry in data["models"]
                       if isinstance(entry, dict) and entry.get("name") == self.model]
            if not matches or not isinstance(matches[0].get("digest"), str) or not matches[0]["digest"]:
                raise BackendError("local_model_not_installed_use_exact_tag")
            self._digest = matches[0]["digest"]
        elif not self._api_key and urllib.parse.urlsplit(self.base_url).scheme == "https":
            raise BackendError("api_key_environment_variable_not_configured")

    def identity(self):
        return {
            "kind": self.provider, "is_model": True, "requested_model": self.model,
            "declared_model_revision": self.model_revision, "local_digest": self._digest,
            "base_url": self.base_url, "api_key_env": self.api_key_env,
            "temperature": self.temperature, "max_output_tokens": self.max_output_tokens,
            "token_limit_param": self.token_limit_param,
            "request_interval_seconds": self.request_interval,
            "timeout_seconds": self.timeout, "transport_retries": self.retries,
            "json_mode": self.json_mode,
        }

    def _request(self, path, payload, emit):
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = "Bearer " + self._api_key
        for attempt in range(1, self.retries + 2):
            if self._last_request_at is not None and self.request_interval:
                delay = max(0.0, self._last_request_at + self.request_interval - time.monotonic())
                if delay:
                    emit("transport_wait", {"reason": "request_interval", "seconds": delay})
                    time.sleep(delay)
            self._last_request_at = time.monotonic()
            emit("transport_attempt", {"attempt": attempt})
            try:
                request = urllib.request.Request(self.base_url + path, data=body, headers=headers)
                with self._opener.open(request, timeout=self.timeout) as response:
                    raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise BackendError("provider_response_too_large")
                try:
                    data = strict_json(raw.decode())
                except (ValueError, UnicodeError, RecursionError):
                    raise BackendError("provider_response_invalid_json") from None
                if not isinstance(data, dict):
                    raise BackendError("provider_response_invalid_shape")
                emit("transport_result", {"attempt": attempt, "outcome": "received"})
                return data
            except urllib.error.HTTPError as exc:
                status = exc.code
                exc.close()
                emit("transport_result", {"attempt": attempt, "outcome": "http_error", "status": status})
                retryable = status in (429, 500, 502, 503, 504)
                code = f"provider_http_{status}"
            except (urllib.error.URLError, TimeoutError, OSError):
                emit("transport_result", {"attempt": attempt, "outcome": "network_error", "usage_uncertain": True})
                retryable, code = True, "provider_network_error"
            if not retryable or attempt > self.retries:
                raise BackendError(code)
            time.sleep(min(0.5 * 2 ** (attempt - 1), 2.0))
        raise AssertionError("unreachable")

    def complete(self, messages, emit):
        if self.provider == "ollama":
            payload = {"model": self.model, "messages": messages, "stream": False,
                       "options": {"num_predict": self.max_output_tokens}}
            if self.temperature is not None:
                payload["options"]["temperature"] = self.temperature
            if self.json_mode:
                payload["format"] = "json"
            data = self._request("/api/chat", payload, emit)
            message = data.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            incoming, outgoing = data.get("prompt_eval_count"), data.get("eval_count")
            metadata = {"finish_reason": data.get("done_reason")}
            if data.get("done") is not True:
                raise BackendError("provider_response_incomplete")
        else:
            payload = {"model": self.model, "messages": messages, "stream": False,
                       self.token_limit_param: self.max_output_tokens}
            if self.temperature is not None:
                payload["temperature"] = self.temperature
            if self.json_mode:
                payload["response_format"] = {"type": "json_object"}
            data = self._request("/chat/completions", payload, emit)
            choices = data.get("choices")
            if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
                raise BackendError("provider_response_invalid_choices")
            message = choices[0].get("message")
            content = message.get("content") if isinstance(message, dict) else None
            usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
            incoming, outgoing = usage.get("prompt_tokens"), usage.get("completion_tokens")
            metadata = {"finish_reason": choices[0].get("finish_reason"),
                        "response_id": data.get("id"), "system_fingerprint": data.get("system_fingerprint")}
        if not isinstance(content, str):
            raise BackendError("provider_response_missing_content")
        if not isinstance(data.get("model"), str):
            raise BackendError("provider_response_missing_model")
        return ModelReply(content, data["model"], token_count(incoming), token_count(outgoing), metadata)


class AlertHeuristic:
    """Transparent non-LLM baseline; examines only returned observations."""
    def identity(self):
        return {"kind": "heuristic", "is_model": False, "policy": "earliest-alert-v1"}

    def complete(self, messages, emit):
        observations, steps_left = [], 0
        for message in messages:
            if message["role"] != "user":
                continue
            try:
                body = json.loads(message["content"])
            except ValueError:
                continue
            steps_left = body.get("steps_left", steps_left)
            if body.get("kind") == "observation":
                observations.append(body["observation"])
        if not observations and steps_left:
            action = {"kind": "tool", "tool": "get_alerts", "args": {}}
        else:
            alerts = next((o["data"].get("alerts", []) for o in observations if o["tool"] == "get_alerts"), [])
            candidates = list(dict.fromkeys(a["service"] for a in sorted(alerts, key=lambda a: a["since"]))) or list(SERVICES)
            probes = [(tool, {"service": service, **extra}) for service in candidates for tool, extra in (
                ("health_check", {}), ("search_logs", {"limit": 20}), ("get_events", {}),
                ("query_metric", {"metric": "rps"}), ("query_metric", {"metric": "memory"}))]
            used = {(o["tool"], json.dumps(o["args"], sort_keys=True)) for o in observations}
            remaining = [(tool, args) for tool, args in probes if (tool, json.dumps(args, sort_keys=True)) not in used]
            if steps_left and remaining:
                tool, args = remaining[0]
                action = {"kind": "tool", "tool": tool, "args": args}
            else:
                service = candidates[0]
                evidence = [o for o in observations if o.get("error") is None and
                            (o["data"].get("service") == service or any(e.get("service") == service for e in o["data"].get("events", [])))]
                text = " ".join(o["text"] for o in evidence).lower()
                health = next((o["data"] for o in evidence if o["tool"] == "health_check"), {})
                metrics = {o["data"]["metric"]: o["data"] for o in evidence if o["tool"] == "query_metric"}
                events = [e for o in evidence for e in o["data"].get("events", [])]
                if health.get("cert_days_left", 1) <= 0:
                    fault = "cert_expiry"
                elif health.get("status") == "down":
                    fault = "dependency_outage"
                elif metrics.get("rps", {}).get("ratio", 0) > 2:
                    fault = "traffic_surge"
                elif metrics.get("memory", {}).get("ratio", 0) > 1.5 or "descriptor" in text or "retained" in text:
                    fault = "resource_leak"
                elif any(e["kind"] == "migration" for e in events):
                    fault = "bad_migration"
                elif any(e["kind"] == "flag_change" for e in events):
                    fault = "feature_flag"
                elif any(e["kind"] == "config_change" for e in events):
                    fault = "config_regression"
                else:
                    fault = "bad_deploy"
                action = {"kind": "report", "report": {
                    "service": service, "fault_type": fault,
                    "fix": {"action": FIX_ACTION[fault], "target": service},
                    "evidence": [o["id"] for o in evidence] or [o["id"] for o in observations[:1]],
                    "confidence": 0.5, "summary": "Fixed earliest-alert heuristic; confidence is an uncalibrated constant.",
                }}
        return ModelReply(json.dumps(action), "earliest-alert-v1")
