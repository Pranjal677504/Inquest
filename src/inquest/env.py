"""Tool-based investigation environment over a replayable scenario bundle."""
from __future__ import annotations

from copy import deepcopy
import statistics
from dataclasses import dataclass, field

from .scenario import HORIZON, Scenario
from .topology import EDGES, SERVICES

LEVELS = {"INFO": 0, "WARN": 1, "ERROR": 2}

TOOL_SPECS = [
    {"name": "list_services", "args": {}, "desc": "List services and their call dependencies (caller -> callee)."},
    {"name": "get_alerts", "args": {}, "desc": "Currently firing alerts, with first observed sustained threshold crossings."},
    {"name": "query_metric", "args": {"service": "str", "metric": "str"},
     "desc": "Summary of a metric over the last 2h. Metrics: error_rate, latency_p99, cpu, memory, rps; "
             "postgres also lock_wait_ms, conn_used; cache also hit_rate."},
    {"name": "search_logs", "args": {"service": "str", "query": "literal substring (optional)", "level": "INFO|WARN|ERROR minimum (optional)", "limit": "positive int (optional, default 12)"},
     "desc": "Most recent log lines matching filters."},
    {"name": "get_events", "args": {"service": "str (optional)"},
     "desc": "Recent change events (deploys, config changes, flag changes, migrations), newest first."},
    {"name": "get_event", "args": {"event_id": "str"}, "desc": "Full detail of one change event."},
    {"name": "health_check", "args": {"service": "str"}, "desc": "Current health, version, restarts in last hour, TLS certificate days left."},
    {"name": "get_trace", "args": {"status": "error|timeout|ok (optional)"}, "desc": "Cycle deterministically through matching traces in the last 40 minutes."},
]


@dataclass
class Observation:
    id: str
    tool: str
    args: dict
    text: str
    data: dict = field(default_factory=dict)
    error: str | None = None

    @property
    def tokens(self) -> int:
        return len(self.text) // 4 + 1


class BudgetExceeded(Exception):
    pass


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


class InvestigationEnv:
    def __init__(self, scenario: Scenario, max_steps: int = 20, max_lines: int = 20):
        """Snapshot permitted telemetry, without retaining construction labels.

        This is an observation interface, not a sandbox against Python reflection.
        A harness must keep the source Scenario on the evaluator side.
        """
        if type(max_steps) is not int or max_steps < 0:
            raise ValueError("max_steps must be a non-negative integer")
        if type(max_lines) is not int or max_lines < 1:
            raise ValueError("max_lines must be a positive integer")
        self._max_steps = max_steps
        self._max_lines = max_lines
        self._steps = 0
        self._obs: list[Observation] = []
        self._metrics = {}
        for service in SERVICES:
            names = ("rps", "error_rate", "latency_p99", "cpu", "memory")
            names += ("lock_wait_ms", "conn_used") if service == "postgres" else ()
            names += ("hit_rate",) if service == "cache" else ()
            self._metrics[service] = _project(scenario.metrics[service], names)
        self._logs = {service: [_project(e, ("t", "level", "msg")) for e in scenario.logs[service]] for service in SERVICES}
        self._events = [_project(e, ("id", "t", "service", "kind", "summary", "detail")) for e in scenario.events]
        self._health = {service: _project(scenario.health[service], ("status", "version", "restarts_1h", "cert_days_left")) for service in SERVICES}
        self._traces = [{"t": tr["t"], "spans": [_project(s, ("service", "ms", "status", "note")) for s in tr["spans"]]} for tr in scenario.traces]
        self._trace_ix = {"error": 0, "timeout": 0, "ok": 0}

    @property
    def max_steps(self) -> int:
        return self._max_steps

    @property
    def max_lines(self) -> int:
        return self._max_lines

    @property
    def steps(self) -> int:
        return self._steps

    @property
    def obs(self) -> tuple[Observation, ...]:
        """Return detached transcript records in call order."""
        return tuple(deepcopy(self._obs))

    # -- public API ----------------------------------------------------------
    @property
    def steps_left(self) -> int:
        return self.max_steps - self.steps

    def call(self, tool: str, **args) -> Observation:
        """Every attempted call consumes one step, including invalid requests."""
        if self.steps >= self.max_steps:
            raise BudgetExceeded(f"step budget of {self.max_steps} exhausted")
        self._steps += 1
        oid = f"o{self.steps}"
        allowed = {spec["name"] for spec in TOOL_SPECS}
        if not isinstance(tool, str) or tool not in allowed:
            ob = Observation(oid, tool, deepcopy(args), "ERROR: unknown tool", error="unknown_tool")
        else:
            try:
                text, data = getattr(self, f"_t_{tool}")(**args)
                ob = Observation(oid, tool, deepcopy(args), text, data)
            except (TypeError, ValueError) as exc:
                ob = Observation(oid, tool, deepcopy(args), f"ERROR: bad arguments for {tool}: {exc}", error="invalid_arguments")
        self._obs.append(deepcopy(ob))
        return deepcopy(ob)

    def tokens_used(self) -> int:
        return sum(o.tokens for o in self._obs)

    # -- tools ---------------------------------------------------------------
    def _check_service(self, s):
        if not isinstance(s, str) or s not in SERVICES:
            raise ValueError(f"unknown service '{s}'. Known: {', '.join(SERVICES)}")

    def _t_list_services(self):
        text = "services: " + ", ".join(SERVICES) + "\ndependencies: " + ", ".join(f"{a}->{b}" for a, b in EDGES)
        return text, {"services": list(SERVICES), "dependencies": [list(edge) for edge in EDGES]}

    def _alerts(self):
        out = []
        for s in SERVICES:
            m = self._metrics[s]
            base_lat = statistics.median(m["latency_p99"][:40])
            for kind, series, cond in (
                ("error_rate>2%", m["error_rate"], lambda v: v > 2.0),
                ("latency_p99>2x baseline", m["latency_p99"], lambda v, b=base_lat: v > 2 * b),
            ):
                first = next((t for t in range(40, HORIZON - 2) if all(cond(series[u]) for u in range(t, t + 3))), None)
                if first is not None and cond(series[-1]):
                    out.append({"service": s, "alert": kind, "since": first, "value": round(series[-1], 2)})
        return out

    def _t_get_alerts(self):
        al = self._alerts()
        if not al:
            return "no alerts firing", {"alerts": []}
        al.sort(key=lambda a: a["since"])
        lines = [f"[t={a['since']}] {a['service']}: {a['alert']} (now {a['value']})" for a in al]
        return f"now = t={HORIZON - 1}\n" + "\n".join(lines), {"alerts": al, "now": HORIZON - 1}

    def _t_query_metric(self, service, metric):
        self._check_service(service)
        if not isinstance(metric, str):
            raise ValueError("metric must be a name")
        series = self._metrics[service].get(metric)
        if series is None:
            raise ValueError(f"{service} has no metric '{metric}': {sorted(self._metrics[service])}")
        base, recent = series[:40], series[-10:]
        b_mean, b_sd = _mean(base), statistics.pstdev(base)
        r_mean = _mean(recent)
        cp = None
        thr = max(4 * b_sd, 0.15 * abs(b_mean), 1e-6)
        for t in range(40, HORIZON - 2):
            if all(abs(series[u] - b_mean) > thr for u in range(t, t + 3)):
                cp = t
                break
        bins = [f"t{a}-{a + 14}: {_mean(series[a:a + 15]):.1f}" for a in range(0, HORIZON, 15)]
        ratio = r_mean / b_mean if b_mean else 0.0
        text = (f"{service}.{metric} (15-min means) " + " | ".join(bins) +
                f"\nbaseline(t0-39)={b_mean:.2f} recent(last 10m)={r_mean:.2f} ratio={ratio:.2f} "
                f"first sustained deviation: {'t=' + str(cp) if cp is not None else 'none'}")
        return text, {"service": service, "metric": metric, "baseline": b_mean, "recent": r_mean,
                      "ratio": ratio, "change_point": cp}

    def _t_search_logs(self, service, query="", level=None, limit=12):
        self._check_service(service)
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        if not isinstance(query, str):
            raise ValueError("query must be a literal substring")
        if level is None:
            level = "INFO"
        if not isinstance(level, str) or level.upper() not in LEVELS:
            raise ValueError("level must be INFO, WARN, or ERROR")
        limit = min(limit, self.max_lines)
        minlvl = LEVELS[level.upper()]
        hits = [e for e in self._logs[service] if LEVELS[e["level"]] >= minlvl and query.casefold() in e["msg"].casefold()]
        shown = hits[-limit:]
        lines = [f"[t={e['t']}] {e['level']} {e['msg']}" for e in shown]
        text = f"{service}: {len(hits)} matching lines, showing last {len(shown)}\n" + "\n".join(lines)
        return text, {"service": service, "lines": shown, "total": len(hits)}

    def _t_get_events(self, service=None):
        if service is not None:
            self._check_service(service)
        ev = [e for e in self._events if service is None or e["service"] == service]
        ev = [_project(e, ("id", "t", "service", "kind", "summary"))
              for e in sorted(ev, key=lambda e: -e["t"])[: self.max_lines]]
        if not ev:
            return "no change events found", {"events": []}
        lines = [f"{e['id']} [t={e['t']}] {e['service']} {e['kind']}: {e['summary']}" for e in ev]
        return "\n".join(lines), {"events": ev, "service": service}

    def _t_get_event(self, event_id):
        if not isinstance(event_id, str):
            raise ValueError("event_id must be a name")
        for e in self._events:
            if e["id"] == event_id:
                return (f"{e['id']} [t={e['t']}] {e['service']} {e['kind']}\n{e['summary']}\n{e['detail']}", {"event": e})
        raise ValueError(f"unknown event id '{event_id}'")

    def _t_health_check(self, service):
        self._check_service(service)
        h = self._health[service]
        text = (f"{service}: status={h['status']} version={h['version']} restarts_1h={h['restarts_1h']} "
                f"tls_cert_days_left={h['cert_days_left']}")
        return text, {"service": service, **h}

    def _t_get_trace(self, status="error"):
        if not isinstance(status, str) or status not in self._trace_ix:
            raise ValueError("status must be error, timeout or ok")
        pool = [tr for tr in self._traces if tr["t"] >= HORIZON - 40 and
                (all(s["status"] == "ok" for s in tr["spans"]) if status == "ok" else
                 any(s["status"] == status for s in tr["spans"]))]
        if not pool:
            return f"no {status} traces found", {"trace": None}
        tr = pool[self._trace_ix[status] % len(pool)]
        self._trace_ix[status] += 1
        lines = [f"  {s['service']} {s['ms']}ms {s['status']}" + (f" - {s['note']}" if s["note"] else "") for s in tr["spans"]]
        return f"trace at t={tr['t']} (caller first):\n" + "\n".join(lines), {"trace": tr}


def _project(record, fields):
    """Copy only permitted telemetry fields, ignoring construction metadata."""
    return {name: deepcopy(record[name]) for name in fields}
