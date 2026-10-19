# Authored-v2 casebook

Evaluator-only design notes and paths. These are scripted reachability checks, not model results. Each path uses five calls, beginning with alerts. Public files can be memorized; this is not a secret holdout.

## authored-v2-001: Auth release reads the wrong signing-key slot

Medium · initiating service `auth` · `bad_deploy` · onset minute 55 · repair `rollback` on `auth`.

Auth a204 changes the signing-key slot from active to retired at minute 55. All instances reject otherwise valid sessions immediately after activation. Cache lookups still succeed and traffic is flat. Roll back auth; the cache flag changed later is unrelated.

Distractor: A cache diagnostics flag at minute 57 changes tracing only, after the first rejected session.

Missing root logs: none.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "auth"})` | same token accepted on a203 | support |
| 4 | `query_metric({"metric": "error_rate", "service": "auth"})` | recent(last 10m)=24.00 | support |
| 5 | `search_logs({"service": "cache"})` | hit rate unchanged | counterevidence |

## authored-v2-002: Order release overflows a cents conversion

Hard · initiating service `orders` · `bad_deploy` · onset minute 73 · repair `rollback` on `orders`.

Orders o307 narrows a 64-bit cents accumulator to 16 bits. Large baskets fail while the same database operations continue to succeed. Orders logs are absent; gateway error payloads identify the conversion and the release. Roll back orders, rather than fail over postgres.

Distractor: A postgres maintenance notice at minute 71 reports successful replication with no serving interruption.

Missing root logs: orders.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "gateway"})` | cents accumulator overflow | support |
| 4 | `get_trace({})` | orders o307 | support |
| 5 | `search_logs({"service": "postgres"})` | accepts reads and commits | counterevidence |

## authored-v2-003: Order pool reduced while database remains idle

Medium · initiating service `orders` · `config_regression` · onset minute 62 · repair `revert_config` on `orders`.

A live orders configuration reduces pool capacity from 48 to 2 at minute 62. Requests queue locally while postgres has spare connections and normal latency. A prior receipt-only deploy did not change the pool. Revert orders configuration.

Distractor: Orders o218 shipped receipt formatting six minutes earlier and passed the original 48-slot pool check.

Missing root logs: none.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "orders"})` | max_clients 48 -> 2 | support |
| 4 | `query_metric({"metric": "latency_p99", "service": "orders"})` | ratio=20.00 | support |
| 5 | `search_logs({"service": "postgres"})` | 32 of 200 | counterevidence |

## authored-v2-004: Payment deadline drops below normal commit time

Hard · initiating service `payments` · `config_regression` · onset minute 84 · repair `revert_config` on `payments`.

A payments runtime timeout refresh changes database deadline from 800ms to 8ms. Normal commits take 24ms and the listener remains healthy. A nearby postgres index maintenance event finishes before symptoms. Revert payments timeout configuration, not the database.

Distractor: Postgres index statistics refresh ended at minute 80 and neither holds locks nor slows commits.

Missing root logs: none.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "payments"})` | ledger_commit_ms=8 | support |
| 4 | `query_metric({"metric": "latency_p99", "service": "postgres"})` | ratio=1.00 | support |
| 5 | `search_logs({"service": "postgres"})` | no rejected connections | counterevidence |

## authored-v2-005: Auth audit buffers accumulate under constant load

Medium · initiating service `auth` · `resource_leak` · onset minute 48 · repair `rollback` on `auth`.

Auth a91 retains every completed audit buffer after a minute-48 release. Memory rises for an hour at stable request volume before restarts. Cache reads remain fast. Roll back the leaking auth build; increasing replicas would not repair per-request retention.

Distractor: An unrelated cache maintenance flag toggles at minute 92, long after auth memory begins growing.

Missing root logs: none.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "auth"})` | completed buffers never removed | support |
| 4 | `query_metric({"metric": "memory", "service": "auth"})` | recent(last 10m)=98.00 | support |
| 5 | `search_logs({"service": "cache"})` | no evictions | counterevidence |

## authored-v2-006: Search leaves temporary result handles open

Hard · initiating service `search` · `resource_leak` · onset minute 52 · repair `rollback` on `search`.

Search s118 leaks a temporary result handle for each query after minute 52. Demand and CPU remain flat, but after handle exhaustion new queries fail. Root logs are absent; gateway receives an explicit descriptor-exhaustion response. Roll back search.

Distractor: Gateway connection logging changes at minute 97, after handle exhaustion starts, without changing routing.

Missing root logs: search.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "gateway"})` | closed_since_boot=0 | support |
| 4 | `query_metric({"metric": "rps", "service": "search"})` | ratio=1.00 | support |
| 5 | `search_logs({"service": "gateway"})` | socket count stable | counterevidence |

## authored-v2-007: Payments listener reaches certificate expiry

Medium · initiating service `payments` · `cert_expiry` · onset minute 66 · repair `renew_cert` on `payments`.

Payments keeps healthy application workers but its serving certificate expires at minute 66. Orders sees certificate validity errors before HTTP dispatch; the payments deploy at minute 60 still passed TLS at minute 61. Renew the payments certificate.

Distractor: A payments receipt-text release precedes expiry, but the same binary served successfully while the certificate was valid.

Missing root logs: none.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "orders"})` | notAfter minute 66 | support |
| 4 | `health_check({"service": "payments"})` | tls_cert_days_left=-1 | support |
| 5 | `search_logs({"service": "payments"})` | handshake and ledger acceptance passed | counterevidence |

## authored-v2-008: Auth TLS expires after an unrelated route refresh

Hard · initiating service `auth` · `cert_expiry` · onset minute 91 · repair `renew_cert` on `auth`.

Auth application error metrics stay flat because the TLS listener rejects sessions before dispatch. Its certificate expires at minute 91. Gateway route reload at minute 87 preserves the auth endpoint. Renew auth TLS instead of reverting gateway routing.

Distractor: The newest gateway route event keeps both the auth upstream address and trust store unchanged.

Missing root logs: none.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "gateway"})` | validity ended minute 91 | support |
| 4 | `health_check({"service": "auth"})` | tls_cert_days_left=-2 | support |
| 5 | `get_event({"event_id": "e1"})` | Auth endpoint and CA trust bundle unchanged | counterevidence |

## authored-v2-009: Checkout replay multiplies orders arrivals

Medium · initiating service `orders` · `traffic_surge` · onset minute 58 · repair `scale_up` on `orders`.

A client reconnect bug replays checkout requests, lifting orders arrivals from 160 to 1920 per second at minute 58. CPU saturates and queueing follows. The orders binary and per-request work are unchanged; payments latency remains normal. Scale orders for the surge.

Distractor: Payments p43 deploys at minute 55 but remains responsive; it cannot explain upstream orders queue saturation.

Missing root logs: none.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `query_metric({"metric": "rps", "service": "orders"})` | ratio=12.00 | support |
| 4 | `search_logs({"service": "orders"})` | 1760 extra checkouts/s | support |
| 5 | `search_logs({"service": "payments"})` | complete in 90ms | counterevidence |

## authored-v2-010: Partner fan-out increases search arrivals

Hard · initiating service `search` · `traffic_surge` · onset minute 77 · repair `scale_up` on `search`.

A partner dashboard starts issuing twelve search requests for each refresh, raising total search RPS from 140 to 1680 at minute 77. Search logs are missing. Gateway access counts identify new demand; a search deploy at minute 69 served baseline load successfully. Scale search.

Distractor: Search s73 shipped before the surge and passed steady-load probes; its payload cost stayed unchanged.

Missing root logs: search.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `query_metric({"metric": "rps", "service": "search"})` | ratio=12.00 | support |
| 4 | `search_logs({"service": "gateway"})` | twelve search requests | support |
| 5 | `get_event({"event_id": "e1"})` | query plan unchanged | counterevidence |

## authored-v2-011: Ledger column rename breaks unchanged payment queries

Medium · initiating service `postgres` · `bad_migration` · onset minute 63 · repair `rollback_migration` on `postgres`.

A postgres migration renames amount_cents to amount_minor at minute 63 without a compatibility view. The unchanged payments binary still queries amount_cents. Database connections and other tables remain healthy. Roll back the migration, not payments.

Distractor: Payments p61 deploys formatting only after the database rename; its SQL fingerprint is unchanged from p60.

Missing root logs: none.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "postgres"})` | column ledger.amount_cents does not exist | support |
| 4 | `query_metric({"metric": "conn_used", "service": "postgres"})` | ratio=1.00 | support |
| 5 | `search_logs({"service": "payments"})` | identical ledger SELECT | counterevidence |

## authored-v2-012: Quantity type narrowing rejects valid large stock values

Hard · initiating service `postgres` · `bad_migration` · onset minute 82 · repair `rollback_migration` on `postgres`.

Postgres migration m311 narrows stock quantities to a signed small integer. Previously valid quantities above 32767 fail, while small updates and connections remain healthy. Inventory flag changes only formatting. Roll back the database type migration.

Distractor: Inventory output flag changes one minute later but no longer runs when the database rejects a write.

Missing root logs: none.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "postgres"})` | quantity 120 write succeeds | support |
| 4 | `get_trace({})` | smallint out of range | support |
| 5 | `search_logs({"service": "inventory"})` | never reaches formatting | counterevidence |

## authored-v2-013: Cache process stops while postgres remains available

Medium · initiating service `cache` · `dependency_outage` · onset minute 71 · repair `failover` on `cache`.

The cache process stops at minute 71 and its listener refuses connections. Auth, inventory and search fail one minute later while database operations continue normally. A search configuration change occurs after the outage. Fail over cache.

Distractor: Search increases result limits at minute 73, after independent cache callers already fail.

Missing root logs: none.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "cache"})` | listener 6379 closed | support |
| 4 | `health_check({"service": "cache"})` | status=down | support |
| 5 | `search_logs({"service": "inventory"})` | postgres stock lookup completes | counterevidence |

## authored-v2-014: Database public listener loses its serving socket

Hard · initiating service `postgres` · `dependency_outage` · onset minute 94 · repair `failover` on `postgres`.

Postgres maintenance agent closes the public serving socket at minute 94 while its local admin process remains healthy. Orders and payments see TCP refusal before SQL. A payments rollout had succeeded beforehand; migration locks cannot explain failures before connection establishment. Fail over postgres.

Distractor: Payments p83 deploys at minute 89; a pre-outage acceptance check confirms successful commits.

Missing root logs: none.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "orders"})` | ECONNREFUSED before SQL dispatch | support |
| 4 | `search_logs({"service": "postgres"})` | admin unix socket still responds | support |
| 5 | `search_logs({"service": "payments"})` | acceptance: commit acknowledged | counterevidence |

## authored-v2-015: Search explanation flag adds synchronous model work

Medium · initiating service `search` · `feature_flag` · onset minute 68 · repair `disable_flag` on `search`.

Search s205 ships an optional explanation path disabled at minute 60. A flag turns it on at minute 68; every result waits on CPU-heavy explanation work. Traffic remains flat and cache responds normally. Disable search explanations instead of rolling back the earlier code.

Distractor: The search release passes a dark-path canary eight minutes before the flag activation.

Missing root logs: none.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "search"})` | explanations_enabled=true | support |
| 4 | `query_metric({"metric": "rps", "service": "search"})` | ratio=1.00 | support |
| 5 | `search_logs({"service": "search"})` | dark-path check | counterevidence |

## authored-v2-016: Orders audit mirror becomes a blocking response gate

Hard · initiating service `orders` · `feature_flag` · onset minute 86 · repair `disable_flag` on `orders`.

Orders o402 already contains a nonblocking audit mirror. A minute-86 flag changes the mirror into a synchronous response gate. Orders logs are missing; gateway sees the named flag and traces isolate the wait to orders after healthy payments and postgres spans. Disable the orders flag.

Distractor: Payments p121 updates receipt wording at minute 84 but payments calls continue to finish in 90ms.

Missing root logs: orders.

| Call | Tool and arguments | Expected clue | Role |
|---|---|---|---|
| 1 | `get_alerts({})` | now = t=119 | discovery |
| 2 | `get_events({})` | e1 | discovery |
| 3 | `search_logs({"service": "gateway"})` | audit_mirror_blocking=true | support |
| 4 | `get_trace({"status": "timeout"})` | audit mirror acknowledgement | support |
| 5 | `search_logs({"service": "payments"})` | no audit-mirror wait | counterevidence |
