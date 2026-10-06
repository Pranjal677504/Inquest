"""Fixed microservice topology used by every Inquest scenario."""
from __future__ import annotations

from collections import deque

SERVICES = ["gateway", "auth", "orders", "payments", "inventory", "search", "cache", "postgres"]

# (caller, callee)
EDGES = [
    ("gateway", "auth"),
    ("gateway", "orders"),
    ("gateway", "search"),
    ("orders", "payments"),
    ("orders", "inventory"),
    ("orders", "postgres"),
    ("payments", "postgres"),
    ("inventory", "cache"),
    ("inventory", "postgres"),
    ("search", "cache"),
    ("auth", "cache"),
]

CALLERS = {s: [a for a, b in EDGES if b == s] for s in SERVICES}
CALLEES = {s: [b for a, b in EDGES if a == s] for s in SERVICES}


def _bfs(start: str, graph: dict[str, list[str]]) -> dict[str, int]:
    if start not in graph:
        raise ValueError(f"Unknown service: {start!r}")
    dist = {start: 0}
    q = deque([start])
    while q:
        cur = q.popleft()
        for nxt in graph[cur]:
            if nxt not in dist:
                dist[nxt] = dist[cur] + 1
                q.append(nxt)
    return dist


def callers_with_hops(service: str) -> dict[str, int]:
    """Transitive callers (upstream) of `service` with hop distance, excluding itself."""
    d = _bfs(service, CALLERS)
    d.pop(service)
    return d


def callees_with_hops(service: str) -> dict[str, int]:
    d = _bfs(service, CALLEES)
    d.pop(service)
    return d


def relation(observed: str, root: str) -> str:
    """Relation of an observed service to a hypothesised root cause service."""
    if observed not in SERVICES or root not in SERVICES:
        raise ValueError("Both services must belong to the topology")
    if observed == root:
        return "self"
    if observed in callers_with_hops(root):
        return "caller"
    if observed in callees_with_hops(root):
        return "callee"
    return "other"
