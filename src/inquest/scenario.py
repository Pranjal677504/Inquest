"""Procedural incident scenario generator.

A scenario is a fully self-contained, deterministic "incident bundle": per-service
metrics, logs, change events, traces and health, plus ground truth (root cause
service, fault type, correct fix). No live infrastructure is needed, so the same
bundle replays identically on a laptop, in Colab, or in CI.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field

from .topology import SERVICES, callers_with_hops, callees_with_hops

HORIZON = 120  # minutes of telemetry; "now" is the last minute

FAULTS = [
    "bad_deploy",
    "config_regression",
    "resource_leak",
    "dependency_outage",
    "cert_expiry",
    "traffic_surge",
    "feature_flag",
    "bad_migration",
]

FAULT_TARGETS = {
    "bad_deploy": ["auth", "orders", "payments", "inventory", "search"],
    "config_regression": ["gateway", "auth", "orders", "payments", "inventory", "search"],
    "resource_leak": ["auth", "orders", "payments", "inventory", "search"],
    "dependency_outage": ["cache", "postgres"],
    "cert_expiry": ["auth", "orders", "payments", "inventory", "search"],
    "traffic_surge": ["auth", "orders", "search"],
    "feature_flag": ["orders", "payments", "inventory", "search"],
    "bad_migration": ["postgres"],
}

FIX_ACTION = {
    "bad_deploy": "rollback",
    "config_regression": "revert_config",
    "resource_leak": "rollback",
    "dependency_outage": "failover",
    "cert_expiry": "renew_cert",
    "traffic_surge": "scale_up",
    "feature_flag": "disable_flag",
    "bad_migration": "rollback_migration",
}

FIX_ACTIONS = sorted(set(FIX_ACTION.values()))

# split -> (seed offset, template family)
SPLITS = {"dev": (0, "a"), "test": (10_000, "a"), "ood": (20_000, "b")}

DIFFICULTY = {
    # severity, log density, decoy events, decoys near onset, benign blips, noise, and realism knobs:
    # drop_logs: root-cause service logs are missing; drop_event: the causal change was never recorded;
    # decoy_anom: unrelated service shows a fault-like symptom; misattr: caller logs blame the wrong peer
    "easy": dict(severity=1.0, log_p=0.9, decoys=1, near=0, blips=0, noise=0.6,
                 drop_logs=0.0, drop_event=0.0, decoy_anom=0.0, misattr=0.0),
    "medium": dict(severity=0.8, log_p=0.7, decoys=3, near=1, blips=1, noise=1.0,
                   drop_logs=0.15, drop_event=0.10, decoy_anom=0.5, misattr=0.2),
    "hard": dict(severity=0.6, log_p=0.45, decoys=5, near=2, blips=3, noise=1.5,
                 drop_logs=0.55, drop_event=0.45, decoy_anom=0.9, misattr=0.5),
}

# ---------------------------------------------------------------------------
# Log templates. Family "a" is used for dev/test; family "b" paraphrases every
# signal with different wording so models can be tested out-of-distribution.
# ---------------------------------------------------------------------------
T = {
    "exception": {
        "a": ["Unhandled exception in {handler}: KeyError 'discount_id' (build {ver})",
              "NullPointerException at {handler}:212 (build {ver})"],
        "b": ["handler={handler} raised TypeError: 'NoneType' object is not subscriptable ver={ver}",
              "panic: runtime error: invalid memory address or nil pointer dereference [{ver}]"],
    },
    "pool_exhausted": {
        "a": ["connection pool exhausted (active={n}/{n}), request waited {ms}ms",
              "pool exhausted: cannot serve request, queue depth {n}"],
        "b": ["could not acquire client from pool: no idle connections (max={n})",
              "pool saturated, rejecting work after {ms}ms wait"],
    },
    "rate_limited": {
        "a": ["429 Too Many Requests: rate limit exceeded (limit={n}/s)",
              "rate limit exceeded for tenant default (limit={n}/s)"],
        "b": ["throttled: request rejected, quota of {n} rps reached",
              "admission control: dropping request, ceiling {n} rps"],
    },
    "oom": {
        "a": ["java.lang.OutOfMemoryError: Java heap space",
              "container killed: OOMKilled (exit code 137)"],
        "b": ["fatal: runtime: out of memory",
              "kernel: Out of memory: Killed process {n} ({svc})"],
    },
    "conn_refused": {
        "a": ["dial tcp {peer}:{port}: connect: connection refused",
              "failed to connect to {peer}: ECONNREFUSED"],
        "b": ["upstream {peer} unreachable: retries exhausted (refused)",
              "no route to healthy backend for {peer}: connection refused"],
    },
    "cert_expired": {
        "a": ["x509: certificate has expired or is not yet valid (peer {peer})",
              "TLS handshake error with {peer}: certificate expired"],
        "b": ["tls: handshake with {peer} failed, certificate verify failed (expired)",
              "peer {peer} presented an expired certificate"],
    },
    "lock_timeout": {
        "a": ["ERROR: canceling statement due to lock timeout",
              "deadlock detected while waiting for ShareLock on relation {rel}"],
        "b": ["process {n} still waiting for AccessExclusiveLock on relation {rel} after 1000ms",
              "query blocked > 30s on table {rel}"],
    },
    "load_shed": {
        "a": ["request queue full ({n}), shedding load",
              "overload: shedding requests, queue={n}"],
        "b": ["backpressure engaged: dropping requests, inflight={n} exceeds limit",
              "worker saturation: refusing new connections (inflight {n})"],
    },
    "slow_handler": {
        "a": ["slow handler {handler}: {ms}ms (flag={flag}=on)",
              "slow handler {handler} {ms}ms flag {flag} enabled"],
        "b": ["handler {handler} took {ms}ms; code path gated by {flag}",
              "latency budget exceeded in {handler} ({ms}ms) behind flag {flag}"],
    },
    "timeout": {
        "a": ["upstream {peer} request timed out after {ms}ms",
              "call to {peer} timed out ({ms}ms)"],
        "b": ["deadline exceeded calling {peer} ({ms}ms)",
              "no response from {peer} within {ms}ms"],
    },
    "upstream_5xx": {
        "a": ["upstream {peer} returned HTTP 500", "bad gateway from {peer}: HTTP 502"],
        "b": ["{peer} responded with server error 500", "received 503 from {peer}"],
    },
}
NOISE_WARN = [
    "slow query detected: {ms}ms on SELECT ... (benign, below SLO)",
    "retrying idempotent request (attempt 2/3)",
    "cache miss for key user:{n}",
    "deprecated API field 'legacy_id' used by client",
    "clock drift {n}ms within tolerance",
]
NOISE_ERROR = [
    "failed to flush metrics batch: i/o error, will retry",
    "log shipper backlog {n} lines, falling behind",
    "background job 'report-export' failed: disk quota warning",
]
INFO = ["GET /api/v1/items 200 completed in {ms}ms", "POST /api/v1/checkout 200 completed in {ms}ms",
        "GET /health 200 completed in 2ms", "request id={n} completed in {ms}ms"]
HANDLERS = ["ApplyDiscount", "PriceQuote", "SessionLoad", "OrderSubmit", "StockReserve", "QueryRank"]
FLAGS = ["new_pricing_v2", "recs_engine_beta", "deep_search_rerank", "inline_fraud_scoring"]
RELATIONS = ["orders", "order_items", "payments_ledger", "inventory_levels"]
PORTS = {"cache": 6379, "postgres": 5432}


@dataclass
class Event:
    id: str
    t: int
    service: str
    kind: str  # deploy | config_change | flag_change | migration
    summary: str
    detail: str


@dataclass
class Span:
    service: str
    ms: int
    status: str  # ok | error | timeout
    note: str = ""


@dataclass
class Scenario:
    id: str
    seed: int
    split: str
    difficulty: str
    onset: int
    root_service: str
    fault_type: str
    fix: dict
    metrics: dict  # service -> metric -> list[float]
    logs: dict  # service -> list[{t, level, msg}]
    events: list  # list[Event dict]
    traces: list  # list[{t, spans:[Span dict]}]
    health: dict
    gold_tools: list
    gold_services: list
    meta: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"), allow_nan=False)

    @staticmethod
    def from_json(s: str) -> "Scenario":
        """Load a labeled construction bundle, rejecting malformed records.

        Bundles include ground truth and must never be passed directly to an
        investigation agent. A budgeted observation interface is a later milestone.
        """
        def reject_constant(value):
            raise ValueError(f"Non-finite JSON number: {value}")

        payload = json.loads(s, parse_constant=reject_constant)
        if not isinstance(payload, dict):
            raise ValueError("Scenario JSON must contain an object")
        try:
            scenario = Scenario(**payload)
        except TypeError as exc:
            raise ValueError("Scenario has missing or unexpected fields") from exc
        _validate_bundle(scenario)
        return scenario


def _nonnegative_int(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _validate_options(seed, difficulty, split):
    _nonnegative_int(seed, "seed")
    if not isinstance(difficulty, str) or difficulty not in DIFFICULTY:
        raise ValueError("difficulty must be easy, medium, or hard")
    if not isinstance(split, str) or split not in SPLITS:
        raise ValueError("split must be dev, test, or ood")


def _validate_bundle(scenario):
    _validate_options(scenario.seed, scenario.difficulty, scenario.split)
    expected_id = f"{scenario.split}-{scenario.difficulty}-{scenario.seed}"
    if scenario.id != expected_id:
        raise ValueError("Scenario ID does not match its generation settings")
    if type(scenario.onset) is not int or not 0 <= scenario.onset < HORIZON:
        raise ValueError("onset must be a minute within the telemetry horizon")
    if not isinstance(scenario.fault_type, str) or scenario.fault_type not in FAULTS:
        raise ValueError("Unknown fault type")
    if scenario.root_service not in FAULT_TARGETS[scenario.fault_type]:
        raise ValueError("Root service is not a valid target for this fault")
    if scenario.fix != {"action": FIX_ACTION[scenario.fault_type], "target": scenario.root_service}:
        raise ValueError("Fix does not match the labeled outcome")
    for name in ("metrics", "logs", "health"):
        data = getattr(scenario, name)
        if not isinstance(data, dict) or set(data) != set(SERVICES):
            raise ValueError(f"{name} must include every service exactly once")
    for service, metrics in scenario.metrics.items():
        required = {"rps", "error_rate", "latency_p99", "cpu", "memory"}
        required.update({"lock_wait_ms", "conn_used"} if service == "postgres" else set())
        required.update({"hit_rate"} if service == "cache" else set())
        if not isinstance(metrics, dict) or set(metrics) != required:
            raise ValueError(f"Unexpected metrics for {service}")
        for series in metrics.values():
            if not isinstance(series, list) or len(series) != HORIZON:
                raise ValueError("Every metric must have 120 samples")
            if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in series):
                raise ValueError("Metric samples must be finite non-negative numbers")
    for service in SERVICES:
        if not isinstance(scenario.logs[service], list) or not isinstance(scenario.health[service], dict):
            raise ValueError("Service logs and health must be a list and an object")
        for record in scenario.logs[service]:
            if not isinstance(record, dict) or set(record) != {"t", "level", "msg"}:
                raise ValueError("Invalid log record")
            _validate_minute(record["t"])
            if record["level"] not in ("INFO", "WARN", "ERROR") or not isinstance(record["msg"], str):
                raise ValueError("Invalid log level or message")
    if not isinstance(scenario.events, list) or not isinstance(scenario.traces, list):
        raise ValueError("Events and traces must be lists")
    for event in scenario.events:
        if not isinstance(event, dict) or set(event) != {"id", "t", "service", "kind", "summary", "detail"}:
            raise ValueError("Invalid event record")
        _validate_minute(event["t"])
        if event["service"] not in SERVICES or any(not isinstance(event[k], str) for k in ("id", "kind", "summary", "detail")):
            raise ValueError("Invalid event service or text")
    for trace in scenario.traces:
        if not isinstance(trace, dict) or set(trace) != {"t", "spans"} or not isinstance(trace["spans"], list):
            raise ValueError("Invalid trace record")
        _validate_minute(trace["t"])
        for span in trace["spans"]:
            if not isinstance(span, dict) or set(span) != {"service", "ms", "status", "note"}:
                raise ValueError("Invalid span record")
            if span["service"] not in SERVICES or span["status"] not in ("ok", "error", "timeout") or not isinstance(span["note"], str):
                raise ValueError("Invalid span service, status, or note")
            _nonnegative_int(span["ms"], "span duration")
    if not isinstance(scenario.meta, dict):
        raise ValueError("Metadata must be an object")
    if not isinstance(scenario.gold_tools, list) or any(not isinstance(x, str) for x in scenario.gold_tools):
        raise ValueError("Gold tools must be a list of names")
    if not isinstance(scenario.gold_services, list) or any(x not in SERVICES for x in scenario.gold_services):
        raise ValueError("Gold services must belong to the topology")


def _validate_minute(value):
    if type(value) is not int or not 0 <= value < HORIZON:
        raise ValueError("Telemetry timestamp must be within minutes 0–119")


# ---------------------------------------------------------------------------
def _fmt(rng: random.Random, template: str, **kw) -> str:
    base = dict(handler=rng.choice(HANDLERS), ver="v2.%d.%d" % (rng.randint(1, 9), rng.randint(0, 9)),
                n=rng.randint(8, 400), ms=rng.randint(300, 5000), peer="upstream", port=0,
                rel=rng.choice(RELATIONS), flag=rng.choice(FLAGS), svc="svc")
    base.update(kw)
    return template.format(**base)


def _signal(rng, family, name, **kw):
    return _fmt(rng, rng.choice(T[name][family]), **kw)


def generate(seed: int, difficulty: str = "medium", split: str = "dev") -> Scenario:
    """Construct a labeled incident using a private random-number generator."""
    _validate_options(seed, difficulty, split)
    offset, family = SPLITS[split]
    seed_full = offset + seed
    rng = random.Random(seed_full * 7919 + 13)
    D = DIFFICULTY[difficulty]
    sev = D["severity"]

    fault = FAULTS[seed % len(FAULTS)]
    root = rng.choice(FAULT_TARGETS[fault])
    onset = rng.randint(62, 90)
    now = HORIZON - 1
    # Symptom magnitudes are drawn from ONE distribution shared by bad_deploy, config_regression and
    # feature_flag, so metrics alone cannot separate them; only logs / change records can.
    sym = dict(err=rng.uniform(5, 18) * sev, lat=1 + rng.uniform(0.2, 2.5) * sev, cpu=rng.uniform(0, 40) * sev)
    callers = callers_with_hops(root)
    direct_callers = [s for s, h in callers.items() if h == 1]

    # ---- baseline metrics --------------------------------------------------
    base = {}
    for s in SERVICES:
        scale = {"gateway": 1.6, "postgres": 1.2}.get(s, 1.0)
        base[s] = dict(
            rps=rng.uniform(120, 300) * scale,
            error_rate=rng.uniform(0.15, 0.6),
            latency_p99=rng.uniform(60, 200),
            cpu=rng.uniform(22, 42),
            memory=rng.uniform(36, 55),
        )
    metrics: dict[str, dict[str, list[float]]] = {}
    for s in SERVICES:
        m = {}
        for name, b in base[s].items():
            rel_noise = 0.04 * D["noise"] if name in ("rps", "latency_p99") else 0.0
            abs_noise = {"error_rate": 0.08, "cpu": 1.5, "memory": 0.6}.get(name, 0.0) * D["noise"]
            m[name] = [max(0.0, b * (1 + rng.gauss(0, rel_noise)) + rng.gauss(0, abs_noise)) for _ in range(HORIZON)]
        if s == "postgres":
            m["lock_wait_ms"] = [max(0.0, 8 + rng.gauss(0, 2 * D["noise"])) for _ in range(HORIZON)]
            m["conn_used"] = [min(100.0, max(0.0, 35 + rng.gauss(0, 3 * D["noise"]))) for _ in range(HORIZON)]
        if s == "cache":
            m["hit_rate"] = [min(100.0, max(0.0, 94 + rng.gauss(0, 1.2 * D["noise"]))) for _ in range(HORIZON)]
        metrics[s] = m

    def apply(s, name, t_from, fn):
        series = metrics[s][name]
        for t in range(max(0, t_from), HORIZON):
            series[t] = max(0.0, fn(series[t], t - t_from))

    def degrade_callers(err, lat_mult, lag=1):
        for c, h in callers.items():
            apply(c, "error_rate", onset + lag, lambda v, k, h=h: v + err * (0.6 ** h))
            apply(c, "latency_p99", onset + lag, lambda v, k, h=h: v * (1 + (lat_mult - 1) * (0.7 ** h)))

    # ---- logs / events containers -----------------------------------------
    logs: dict[str, list[dict]] = {s: [] for s in SERVICES}
    events: list[Event] = []

    def log(s, t, level, msg):
        logs[s].append({"t": int(t), "level": level, "msg": msg})

    root_logs_dropped = rng.random() < D["drop_logs"]
    meta_flags = {"logs_dropped": root_logs_dropped}

    def fault_logs(s, name, level="ERROR", per_min=(1, 3), **kw):
        if root_logs_dropped and s == root:
            return
        for t in range(onset, HORIZON):
            if rng.random() < D["log_p"]:
                for _ in range(rng.randint(*per_min)):
                    log(s, t, level, _signal(rng, family, name, **kw))

    def caller_logs(names, p_scale=0.9, **kw):
        for c in direct_callers:
            for t in range(onset + 1, HORIZON):
                if rng.random() < D["log_p"] * p_scale:
                    nm = rng.choice(names)
                    extra = dict(kw)
                    blamed = root
                    if rng.random() < D["misattr"]:
                        blamed = rng.choice([x for x in SERVICES if x not in (root, c)])
                    extra.setdefault("peer", blamed)
                    extra.setdefault("port", PORTS.get(blamed, 8080))
                    log(c, t, "ERROR", _signal(rng, family, nm, **extra))

    def add_event(t, s, kind, summary, detail):
        events.append(Event(id="", t=int(t), service=s, kind=kind, summary=summary, detail=detail))

    gold_tools: list[str] = []
    gold_services = [root]
    meta: dict = {}

    # ---- the true fault ----------------------------------------------------
    if fault == "bad_deploy":
        t_dep = onset - rng.randint(0, 2)
        v_old, v_new = "v1.%d.%d" % (rng.randint(3, 9), rng.randint(0, 9)), "v1.%d.0" % rng.randint(10, 19)
        add_event(t_dep, root, "deploy", f"deploy {v_old} -> {v_new}",
                  f"Release {v_new}: refactor request validation and discount handling. Rollback target: {v_old}.")
        apply(root, "error_rate", onset, lambda v, k: v + sym["err"])
        apply(root, "latency_p99", onset, lambda v, k: v * sym["lat"])
        apply(root, "cpu", onset, lambda v, k: min(98.0, v + sym["cpu"]))
        degrade_callers(sym["err"], sym["lat"])
        fault_logs(root, "exception", ver=v_new)
        caller_logs(["timeout", "upstream_5xx"], ms=rng.randint(800, 3000))
        gold_tools = ["events", "logs"]
        meta.update(version=v_new)
    elif fault == "config_regression":
        key = rng.choice(["pool_size", "rate_limit_rps"])
        old, new = (50, 4) if key == "pool_size" else (900, 60)
        add_event(onset - rng.randint(0, 2), root, "config_change", f"config change: {key} {old} -> {new}",
                  f"- {key}: {old}\n+ {key}: {new}\nchange-id CHG-{rng.randint(1000, 9999)} (tuning)")
        apply(root, "error_rate", onset, lambda v, k: v + sym["err"])
        apply(root, "latency_p99", onset, lambda v, k: v * sym["lat"])
        apply(root, "cpu", onset, lambda v, k: min(98.0, v + sym["cpu"]))
        degrade_callers(sym["err"], sym["lat"])
        fault_logs(root, "pool_exhausted" if key == "pool_size" else "rate_limited",
                   level="ERROR" if key == "pool_size" else "WARN", n=new)
        caller_logs(["timeout", "upstream_5xx"], ms=rng.randint(800, 3000))
        gold_tools = ["events", "logs"]
        meta.update(config_key=key)
    elif fault == "resource_leak":
        t_dep = onset - rng.randint(32, 42)
        v_old, v_new = "v2.%d.1" % rng.randint(1, 8), "v2.%d.0" % rng.randint(9, 15)
        add_event(t_dep, root, "deploy", f"deploy {v_old} -> {v_new}",
                  f"Release {v_new}: add in-memory session cache. Rollback target: {v_old}.")
        period = 50
        base_mem = base[root]["memory"]
        for t in range(t_dep, HORIZON):
            frac = ((t - t_dep) % period) / period
            metrics[root]["memory"][t] = min(99.5, base_mem + (99 - base_mem) * min(1.0, frac * 1.15))
        restarts = []
        for t in range(t_dep + 1, HORIZON):
            if (t - t_dep) % period == 0 and t >= onset - 4:
                restarts.append(t)
        for t in restarts:
            apply(root, "error_rate", t, lambda v, k: v + (14 * sev if k < 4 else 0))
            if rng.random() < 0.95 and not root_logs_dropped:
                log(root, t, "ERROR", _signal(rng, family, "oom", svc=root))
        apply(root, "error_rate", onset, lambda v, k: v + 3 * sev)
        apply(root, "latency_p99", onset, lambda v, k: v * (1 + 0.5 * sev))
        degrade_callers(6 * sev, 1.4)
        for t in range(onset, HORIZON):
            if rng.random() < D["log_p"] * 0.5 and not root_logs_dropped:
                log(root, t, "WARN", "GC overhead high: %d%% of CPU time in garbage collection" % rng.randint(40, 80))
        caller_logs(["timeout"], p_scale=0.7, ms=rng.randint(800, 3000))
        meta.update(restarts=len(restarts) + 1)
        gold_tools = ["metric", "logs", "health", "events"]
    elif fault == "dependency_outage":
        apply(root, "error_rate", onset, lambda v, k: v + rng.uniform(30, 60))
        apply(root, "latency_p99", onset, lambda v, k: v * 5)
        apply(root, "rps", onset, lambda v, k: v * 0.3)
        if root == "cache":
            apply(root, "hit_rate", onset, lambda v, k: v * 0.1)
        else:
            apply(root, "conn_used", onset, lambda v, k: min(100.0, v + 62))
        degrade_callers(rng.uniform(10, 25) * sev, 2.0)
        caller_logs(["conn_refused", "timeout"], ms=rng.randint(800, 3000))
        gold_tools = ["logs", "health", "metric"]
        gold_services = [root] + direct_callers
    elif fault == "cert_expiry":
        apply(root, "rps", onset, lambda v, k: v * rng.uniform(0.05, 0.2))
        apply(root, "cpu", onset, lambda v, k: v * 0.55)
        degrade_callers(rng.uniform(9, 20) * sev, 1.5)
        fault_logs(root, "cert_expired", peer="client-%d" % rng.randint(1, 9), per_min=(1, 2))
        caller_logs(["cert_expired"], p_scale=1.0)
        gold_tools = ["logs", "health"]
        gold_services = [root] + direct_callers
    elif fault == "traffic_surge":
        mult = rng.uniform(3.0, 5.0) * (0.5 + 0.5 * sev)
        apply(root, "rps", onset, lambda v, k: v * (1 + (mult - 1) * min(1.0, (k + 1) / 5)))
        apply(root, "cpu", onset, lambda v, k: min(99.0, v + 55 * sev + 8))
        apply(root, "latency_p99", onset, lambda v, k: v * (1 + 3 * sev))
        apply(root, "error_rate", onset, lambda v, k: v + rng.uniform(4, 10) * sev)
        for c in callees_with_hops(root):
            apply(c, "rps", onset, lambda v, k: v * 1.25)
        degrade_callers(rng.uniform(4, 10) * sev, 1.6)
        fault_logs(root, "load_shed")
        caller_logs(["timeout"], p_scale=0.7, ms=rng.randint(800, 3000))
        gold_tools = ["metric", "logs"]
    elif fault == "feature_flag":
        flag = rng.choice(FLAGS)
        add_event(onset - rng.randint(0, 2), root, "flag_change", f"flag {flag}: off -> on (100%)",
                  f"Flag {flag} enabled for 100% of traffic by release-bot. Owner: growth-team.")
        apply(root, "cpu", onset, lambda v, k: min(98.0, v + sym["cpu"]))
        apply(root, "latency_p99", onset, lambda v, k: v * sym["lat"])
        apply(root, "error_rate", onset, lambda v, k: v + sym["err"])
        degrade_callers(sym["err"], sym["lat"])
        fault_logs(root, "slow_handler", level="WARN", flag=flag)
        caller_logs(["timeout"], p_scale=0.7, ms=rng.randint(800, 3000))
        gold_tools = ["events", "logs"]
        meta.update(flag=flag)
    elif fault == "bad_migration":
        add_event(onset - rng.randint(0, 2), root, "migration",
                  "apply migration 0042_add_index_orders",
                  "ALTER TABLE orders ADD COLUMN region text NOT NULL DEFAULT 'eu'; CREATE INDEX ... (non-concurrent)")
        apply(root, "lock_wait_ms", onset, lambda v, k: v + rng.uniform(1500, 6000) * sev)
        apply(root, "conn_used", onset, lambda v, k: min(100.0, v + 55 * sev + 10))
        apply(root, "latency_p99", onset, lambda v, k: v * (1 + 3 * sev))
        apply(root, "error_rate", onset, lambda v, k: v + rng.uniform(5, 12) * sev)
        degrade_callers(rng.uniform(8, 18) * sev, 2.0)
        fault_logs(root, "lock_timeout", level="WARN", rel="orders")
        caller_logs(["lock_timeout", "timeout"], ms=rng.randint(800, 3000))
        gold_tools = ["events", "logs", "metric"]
        gold_services = [root] + direct_callers

    # ---- realism: unrecorded change & unrelated fault-like anomalies --------
    meta.update(meta_flags)
    meta["event_dropped"] = False
    if events and rng.random() < D["drop_event"]:
        events.pop()  # the causal change was made out-of-band and never recorded
        meta["event_dropped"] = True
    n_anom = int(rng.random() < D["decoy_anom"]) + int(D["decoy_anom"] > 0.8 and rng.random() < 0.4)
    pool = [x for x in SERVICES if x != root and x not in callers and x not in callees_with_hops(root)]
    rng.shuffle(pool)
    meta["decoy_anomalies"] = []
    for d in pool[:n_anom]:
        kind = rng.choice(["cpu_slow", "mem_creep", "exceptions"])
        t_s = rng.randint(max(5, onset - 25), onset - 3)
        if kind == "cpu_slow":
            apply(d, "cpu", t_s, lambda v, k: min(97.0, v + rng.uniform(40, 55)))
            apply(d, "latency_p99", t_s, lambda v, k: v * 1.25)
            for t in range(t_s, HORIZON):
                if rng.random() < 0.5:
                    log(d, t, "WARN", _signal(rng, family, "slow_handler", flag=rng.choice(FLAGS)))
        elif kind == "mem_creep":
            apply(d, "memory", t_s, lambda v, k: min(95.0, v + k * 0.9))
        else:
            apply(d, "error_rate", t_s, lambda v, k: v + 0.8)
            for t in range(t_s, HORIZON):
                if rng.random() < 0.35:
                    log(d, t, "ERROR", _signal(rng, family, "exception", ver="v3.0.%d" % rng.randint(0, 9)))
        meta["decoy_anomalies"].append({"service": d, "kind": kind})

    # ---- decoys & noise ----------------------------------------------------
    others = [s for s in SERVICES if s != root]
    benign = [("deploy", "deploy {a} -> {b}", "Release {b}: dependency patch bump, no functional change."),
              ("config_change", "config change: log_level info -> debug", "- log_level: info\n+ log_level: debug"),
              ("flag_change", "flag dark_mode_ui: off -> on (5%)", "Flag dark_mode_ui enabled for 5% of traffic."),
              ("config_change", "config change: batch_size 100 -> 120", "- batch_size: 100\n+ batch_size: 120")]
    for i in range(D["decoys"]):
        near = i < D["near"]
        t = rng.randint(max(2, onset - 8), onset + 3) if near else rng.randint(2, HORIZON - 3)
        # Avoid giving the leak scenario a competing decoy deploy on its own service.
        s = rng.choice(others if i else (list(callers) or others))
        kind, summ, det = rng.choice(benign)
        a, b = "v3.%d.%d" % (rng.randint(0, 5), rng.randint(0, 9)), "v3.%d.%d" % (rng.randint(6, 9), rng.randint(0, 9))
        add_event(t, s, kind, summ.format(a=a, b=b), det.format(a=a, b=b))

    for s in SERVICES:
        for t in range(0, HORIZON, 2):
            if rng.random() < 0.55:
                log(s, t, "INFO", _fmt(rng, rng.choice(INFO)))
        for _ in range(rng.randint(5, 9)):
            log(s, rng.randint(0, HORIZON - 1), "WARN", _fmt(rng, rng.choice(NOISE_WARN)))
    # a benign noisy service with a (misleading) error stream, unrelated to root
    unrelated = [s for s in others if s not in callers and s not in callees_with_hops(root)] or others
    nz = rng.choice(unrelated)
    for t in range(rng.randint(20, 55), HORIZON):
        if rng.random() < 0.25 * D["noise"]:
            log(nz, t, "ERROR", _fmt(rng, rng.choice(NOISE_ERROR)))
    for s in rng.sample(others, k=min(len(others), 2 + D["blips"])):
        for t in range(0, HORIZON):
            if rng.random() < 0.012 * D["noise"]:
                log(s, t, "WARN", _signal(rng, family, "timeout", peer=rng.choice(SERVICES), ms=rng.randint(400, 1500)))
    for _ in range(D["blips"]):  # short benign metric blips unrelated to the incident
        s = rng.choice(others)
        name = rng.choice(["cpu", "latency_p99", "rps"])
        t0 = rng.randint(5, max(6, onset - 15))
        dur = rng.randint(2, 4)
        for t in range(t0, t0 + dur):
            metrics[s][name][t] *= rng.uniform(1.8, 2.4)

    for s in SERVICES:
        logs[s].sort(key=lambda e: e["t"])
    events.sort(key=lambda e: e.t)
    for i, e in enumerate(events, 1):
        e.id = f"e{i}"

    # ---- health ------------------------------------------------------------
    health = {}
    for s in SERVICES:
        health[s] = dict(status="healthy", version="v1.%d.%d" % (rng.randint(2, 9), rng.randint(0, 9)),
                         restarts_1h=rng.choice([0, 0, 0, 1]), cert_days_left=rng.randint(20, 90))
    for s in SERVICES:
        err_now = metrics[s]["error_rate"][now]
        if err_now > 2.0 or metrics[s]["latency_p99"][now] > 2.2 * base[s]["latency_p99"]:
            health[s]["status"] = "degraded"
    for e in events:
        if e.kind == "deploy":
            health[e.service]["version"] = e.summary.split("-> ")[-1]
    if fault == "bad_deploy":
        health[root]["status"] = "degraded"
    if fault == "resource_leak":
        health[root]["restarts_1h"] = meta["restarts"] + rng.randint(0, 1)
        health[root]["status"] = "degraded"
    if fault == "dependency_outage":
        health[root]["status"] = "down"
    if fault == "cert_expiry":
        health[root]["cert_days_left"] = -rng.randint(0, 2)
        health[root]["status"] = "degraded"

    # ---- traces ------------------------------------------------------------
    traces = []
    chains = [["gateway", "orders", "payments", "postgres"], ["gateway", "orders", "inventory", "cache"],
              ["gateway", "search", "cache"], ["gateway", "auth", "cache"], ["gateway", "orders", "inventory", "postgres"]]
    for _ in range(60):
        t = rng.randint(onset - 20, HORIZON - 1)
        chain = rng.choice(chains)
        spans = [Span(s, rng.randint(5, 40), "ok") for s in chain]
        if t >= onset and root in chain:
            i = chain.index(root)
            if fault == "cert_expiry" and i > 0:
                spans[i - 1] = Span(chain[i - 1], 30, "error", f"tls handshake to {root} failed: certificate expired")
                spans = spans[:i]
            else:
                st = "timeout" if fault in ("traffic_surge", "bad_migration", "feature_flag") else "error"
                spans[i] = Span(root, rng.randint(900, 4000), st, "request timed out" if st == "timeout" else "request failed")
                spans = spans[: i + 1]
            for j in range(len(spans) - 1):
                if spans[j].status == "ok":
                    spans[j] = Span(spans[j].service, spans[j].ms + 2500, "error", "upstream failure")
        traces.append({"t": t, "spans": [asdict(s) for s in spans]})
    traces.sort(key=lambda x: x["t"])

    return Scenario(
        id=f"{split}-{difficulty}-{seed}", seed=seed, split=split, difficulty=difficulty, onset=onset,
        root_service=root, fault_type=fault, fix={"action": FIX_ACTION[fault], "target": root},
        metrics={s: {k: [round(x, 3) for x in v] for k, v in m.items()} for s, m in metrics.items()},
        logs=logs, events=[asdict(e) for e in events], traces=traces, health=health,
        gold_tools=gold_tools, gold_services=gold_services, meta=meta,
    )


def iter_scenarios(split: str, n: int, difficulty: str = "medium", start: int = 0):
    """Yield a reproducible seed range; zero cases yields an empty iterator."""
    _validate_options(start, difficulty, split)
    _nonnegative_int(n, "n")
    for i in range(start, start + n):
        yield generate(i, difficulty, split)
