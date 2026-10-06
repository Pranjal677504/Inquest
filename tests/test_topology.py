import pytest

from inquest.topology import callees_with_hops, callers_with_hops, relation


def test_callers_use_shortest_paths():
    assert callers_with_hops("postgres") == {
        "orders": 1, "payments": 1, "inventory": 1, "gateway": 2,
    }
    assert callers_with_hops("gateway") == {}


def test_callees_and_relations():
    assert callees_with_hops("orders") == {"payments": 1, "inventory": 1, "postgres": 1, "cache": 2}
    assert relation("postgres", "postgres") == "self"
    assert relation("gateway", "postgres") == "caller"
    assert relation("postgres", "orders") == "callee"
    assert relation("auth", "postgres") == "other"


@pytest.mark.parametrize("query", [callers_with_hops, callees_with_hops])
def test_unknown_services(query):
    with pytest.raises(ValueError, match="Unknown service"):
        query("missing")


def test_unknown_equal_services_are_invalid():
    with pytest.raises(ValueError):
        relation("missing", "missing")
