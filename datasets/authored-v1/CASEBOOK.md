# Authored casebook

Evaluator material: these explanations and probe expectations must not be supplied to an agent. These are AI-authored synthetic causal narratives, reviewed by the same author; external review remains pending.

## authored-v1-001 — Successful deploy, rejected issuer

**Designed difficulty:** medium. **Initiating service:** `auth`. **Fault:** `config_regression`. **Expected recovery:** `revert_config` on `auth`.

The auth deployment at minute 58 remains compatible, as its issuer acceptance check confirms. At minute 64 an issuer allowlist reload removes the partner issuer. Requests from that issuer are rejected while token verification and cache operations remain healthy. This raises caller errors without CPU or latency saturation. Revert the auth configuration, rather than the successful earlier deployment.

Distractors and checks:

- The gateway release at minute 65 occurs after auth rejects tokens and its routing checksum is unchanged.
- Support: `search_logs({"limit": 20, "service": "auth"})` must include `issuer authorization rejects`.
- Support: `get_events({"service": "auth"})` must include `issuer allowlist reload`.
- Counterevidence: `search_logs({"limit": 20, "service": "gateway"})` must include `routing checksum unchanged`.

## authored-v1-002 — Quiet client, growing descriptor count

**Designed difficulty:** hard. **Initiating service:** `payments`. **Fault:** `resource_leak`. **Expected recovery:** `rollback` on `payments`.

A payments client wrapper shipped at minute 52 creates a new socket for each request and fails to close it. Open descriptors climb under steady request volume; connection creation eventually fails. The database connection ratio and query latency stay at baseline, ruling against database pool exhaustion. Roll back the payments wrapper release.

Distractors and checks:

- A postgres pool resize at minute 65 is tempting but database latency and utilization remain normal.
- Support: `search_logs({"limit": 20, "service": "payments"})` must include `handles never released`.
- Support: `search_logs({"limit": 20, "service": "payments"})` must include `file descriptor limit reached`.
- Counterevidence: `search_logs({"limit": 20, "service": "postgres"})` must include `without waits`.

## authored-v1-003 — A warm cache behind expired inventory TLS

**Designed difficulty:** medium. **Initiating service:** `inventory`. **Fault:** `cert_expiry`. **Expected recovery:** `renew_cert` on `inventory`.

The inventory listener certificate expires at minute 73. Orders cannot finish the TLS handshake to inventory; the request never reaches its application or cache client. Cache hit rate and successful search-to-cache traces remain normal despite a nearby cache maintenance event. Renew the inventory listener certificate.

Distractors and checks:

- Cache maintenance precedes the incident, but independent cache callers and cache telemetry remain healthy.
- Support: `search_logs({"limit": 20, "service": "orders"})` must include `before request dispatch`.
- Support: `health_check({"service": "inventory"})` must include `tls_cert_days_left=-1`.
- Counterevidence: `search_logs({"limit": 20, "service": "search"})` must include `successfully in 7ms`.

Missing service logs: `inventory`.

## authored-v1-004 — A deployment-shaped flag incident

**Designed difficulty:** hard. **Initiating service:** `payments`. **Fault:** `feature_flag`. **Expected recovery:** `disable_flag` on `payments`.

The payments application release at minute 64 passed a dark-path canary. At minute 68 a remotely controlled risk-inline flag begins waiting synchronously for the risk adapter. Waiting time rises without CPU, memory, or database load changes. A trace explicitly identifies risk-inline wait in payments. Disable that flag; a coincident unrelated orders release is not the initiating change.

Distractors and checks:

- The orders release at minute 67 changes receipts only; no payment-route configuration changes.
- Support: `search_logs({"limit": 20, "service": "payments"})` must include `risk-inline=true`.
- Support: `get_trace({"status": "timeout"})` must include `risk-inline wait`.
- Counterevidence: `search_logs({"limit": 20, "service": "orders"})` must include `payment routing unchanged`.

## authored-v1-005 — Serialized quantities after inventory release

**Designed difficulty:** medium. **Initiating service:** `inventory`. **Fault:** `bad_deploy`. **Expected recovery:** `rollback` on `inventory`.

Inventory release i52 changes available_units from an integer to a formatted string on its response path. Its validation fails for every stock request immediately after rollout, while database/cache dependencies answer normally. A nearby cache flag change affects a different caller. Roll back inventory to i51.

Distractors and checks:

- The search cache flag changes at minute 62, but inventory stock failures began at minute 61 and its own cache calls pass.
- Support: `search_logs({"limit": 20, "service": "inventory"})` must include `received formatted string`.
- Support: `get_events({"service": "inventory"})` must include `i51 to i52`.
- Counterevidence: `search_logs({"limit": 20, "service": "inventory"})` must include `database=ok cache=ok`.

## authored-v1-006 — Locked relation after a schema rewrite

**Designed difficulty:** hard. **Initiating service:** `postgres`. **Fault:** `bad_migration`. **Expected recovery:** `rollback_migration` on `postgres`.

An ALTER COLUMN rewrite starts at minute 76 and retains an exclusive lock on stock_reservations. Calls from both orders and inventory block on that relation. The postgres telemetry collector has no log records for the incident, so the investigation must combine change history, lock waits, and distinct caller symptoms. Roll back the migration to release the blocking rewrite.

Distractors and checks:

- Orders release o33 occurs at minute 77 after both database callers begin waiting; inventory was not deployed.
- Support: `get_events({"service": "postgres"})` must include `type rewrite started`.
- Support: `query_metric({"metric": "lock_wait_ms", "service": "postgres"})` must include `first sustained deviation: t=`.
- Support: `search_logs({"limit": 20, "service": "inventory"})` must include `schema owner transaction`.
- Counterevidence: `search_logs({"limit": 20, "service": "orders"})` must include `database client unchanged`.

Missing service logs: `postgres`.

## authored-v1-007 — A retry storm originating at auth

**Designed difficulty:** medium. **Initiating service:** `auth`. **Fault:** `traffic_surge`. **Expected recovery:** `scale_up` on `auth`.

A synchronized client refresh wave sends auth request volume from 200/s to 1800/s. Auth CPU and queueing increase with arrival rate before cache latency degrades slightly. An unrelated auth configuration reload occurs afterward and leaves request quotas unchanged. Scale auth capacity for the refresh wave.

Distractors and checks:

- The auth config reload at minute 61 happens after the arrival-rate jump and preserves quotas.
- Support: `query_metric({"metric": "rps", "service": "auth"})` must include `first sustained deviation: t=`.
- Support: `search_logs({"limit": 20, "service": "auth"})` must include `service capacity 650`.
- Counterevidence: `search_logs({"limit": 20, "service": "auth"})` must include `worker configuration unchanged`.

## authored-v1-008 — Database endpoint fenced after promotion

**Designed difficulty:** hard. **Initiating service:** `postgres`. **Fault:** `dependency_outage`. **Expected recovery:** `failover` on `postgres`.

A database promotion at minute 81 fences the old writer endpoint. Orders and payments both reach that endpoint but receive write-service unavailable responses. Postgres remains responsive to process health checks, so liveness alone is misleading. A payments deployment at minute 80 is unrelated because orders fails independently and both see the same writer fence. Fail over database connections to the available writer endpoint.

Distractors and checks:

- The payments release is temporally close, but orders has no new release and receives the same writer-fenced error.
- Support: `search_logs({"limit": 20, "service": "postgres"})` must include `alternate writer endpoint is accepting writes`.
- Support: `search_logs({"limit": 20, "service": "orders"})` must include `writer fenced`.
- Counterevidence: `search_logs({"limit": 20, "service": "payments"})` must include `ledger insert not admitted`.

## authored-v1-009 — The ranking codec canary missed packed results

**Designed difficulty:** hard. **Initiating service:** `search`. **Fault:** `bad_deploy`. **Expected recovery:** `rollback` on `search`.

Search release s70 enables a packed-result decoder incompatible with the existing index format. Small canary queries passed, but normal packed results fail immediately on rollout. Search application logs are absent during collection; the release notes and trace decoder failure must be combined with normal cache behavior. Roll back search to s69.

Distractors and checks:

- A cache sizing change at minute 63 is close, but search traces show the decoder fails after cache lookup succeeds.
- Support: `get_events({"service": "search"})` must include `s69 to s70`.
- Support: `get_trace({"status": "error"})` must include `packed result codec incompatible`.
- Counterevidence: `search_logs({"limit": 20, "service": "cache"})` must include `delivered payload successfully`.

Missing service logs: `search`.

## authored-v1-010 — Slow search with unchanged request volume

**Designed difficulty:** medium. **Initiating service:** `inventory`. **Fault:** `feature_flag`. **Expected recovery:** `disable_flag` on `inventory`.

An eager-stock-expansion flag in inventory adds 40 cache reads per stock request. Inventory traffic remains 150/s while inventory latency and cache request volume rise at minute 72. Search becomes slow as collateral load reaches its shared cache, despite its recent deployment. Disable inventory eager expansion.

Distractors and checks:

- Search release s12 precedes the event, but search arrivals are unchanged and inventory records the new cache fanout.
- Support: `search_logs({"limit": 20, "service": "inventory"})` must include `40 cache reads`.
- Support: `get_events({"service": "inventory"})` must include `eager-stock-expansion switched on`.
- Counterevidence: `search_logs({"limit": 20, "service": "search"})` must include `request shape unchanged`.

## authored-v1-011 — Healthy application, expired search listener

**Designed difficulty:** hard. **Initiating service:** `search`. **Fault:** `cert_expiry`. **Expected recovery:** `renew_cert` on `search`.

Search listener certificate expires at minute 88. Gateway TLS requests fail before search handles them, although the local search application health check remains responsive. A search release at minute 87 changed only query highlighting. Renew the listener certificate; restarting the healthy application or rolling back highlighting cannot extend its validity.

Distractors and checks:

- The minute-87 search deployment is closer than the maintenance history, but its local acceptance check passes and the failed handshake identifies the expired listener credential.
- Support: `search_logs({"limit": 20, "service": "gateway"})` must include `validity ended at minute 88`.
- Support: `health_check({"service": "search"})` must include `tls_cert_days_left=-2`.
- Counterevidence: `search_logs({"limit": 20, "service": "search"})` must include `local query checks`.

## authored-v1-012 — Requests rejected at the gateway boundary

**Designed difficulty:** hard. **Initiating service:** `gateway`. **Fault:** `config_regression`. **Expected recovery:** `revert_config` on `gateway`.

A gateway configuration sync lowers maximum request body size from 2MB to 2KB at minute 59. Normal checkout requests are rejected at ingress and do not reach orders, whose inbound traffic falls. Inventory latency has a brief unrelated pre-incident spike and returns to normal. Revert the gateway body-size configuration.

Distractors and checks:

- A short inventory batch at minute 50 produced a latency spike that ended before checkout rejection began.
- Support: `search_logs({"limit": 20, "service": "gateway"})` must include `configured limit 2048 bytes`.
- Support: `search_logs({"limit": 20, "service": "gateway"})` must include `2097152 bytes before`.
- Counterevidence: `search_logs({"limit": 20, "service": "orders"})` must include `finish normally`.

## authored-v1-013 — Index removal mistaken for demand growth

**Designed difficulty:** medium. **Initiating service:** `postgres`. **Fault:** `bad_migration`. **Expected recovery:** `rollback_migration` on `postgres`.

The postgres migration at minute 67 removes the index used by order lookup. The query plan changes to sequential scans, increasing database CPU and latency under unchanged arrival rate. Lock waits remain at baseline, distinguishing this from a blocking rewrite. A gateway rollout at minute 68 follows the degradation. Roll back the migration and restore the index.

Distractors and checks:

- The gateway release occurs after database scans rise; ingress request volume is unchanged.
- Support: `search_logs({"limit": 20, "service": "postgres"})` must include `sequential scan after index removal`.
- Support: `get_events({"service": "postgres"})` must include `orders_customer_idx removed`.
- Counterevidence: `search_logs({"limit": 20, "service": "postgres"})` must include `lock waits remain 4ms`.

## authored-v1-014 — Search arrivals overwhelm an unchanged deployment

**Designed difficulty:** hard. **Initiating service:** `search`. **Fault:** `traffic_surge`. **Expected recovery:** `scale_up` on `search`.

An external catalogue crawler sends search traffic from 140/s to 2400/s at minute 79. Query CPU and queue delay rise before downstream cache response time changes. Search logs are missing; the request-rate and CPU metric changes plus gateway traffic attribution and trace queue time distinguish demand growth from the unrelated earlier search release. Scale search capacity.

Distractors and checks:

- Search release s90 occurred at minute 70 with stable error rates until the crawler wave nine minutes later.
- Support: `query_metric({"metric": "rps", "service": "search"})` must include `first sustained deviation: t=`.
- Support: `get_trace({"status": "timeout"})` must include `search queue residence 2300ms`.
- Counterevidence: `search_logs({"limit": 20, "service": "cache"})` must include `no connectivity failures`.

Missing service logs: `search`.

## authored-v1-015 — A cache address that cannot be reached

**Designed difficulty:** medium. **Initiating service:** `cache`. **Fault:** `dependency_outage`. **Expected recovery:** `failover` on `cache`.

A cache node network route disappears at minute 62. Multiple independent callers receive connection failures to the same cache address while their own processes and postgres calls remain healthy. A search flag change is coincident but cannot explain auth and inventory connection failures. Fail over the cache dependency.

Distractors and checks:

- The search query flag is unrelated: auth and inventory do not run search code but fail to reach the same cache address.
- Support: `search_logs({"limit": 20, "service": "auth"})` must include `network route absent`.
- Support: `search_logs({"limit": 20, "service": "inventory"})` must include `stock database read succeeds`.
- Counterevidence: `search_logs({"limit": 20, "service": "search"})` must include `before query flag branch`.

## authored-v1-016 — Orders memory grows despite steady traffic

**Designed difficulty:** medium. **Initiating service:** `orders`. **Fault:** `resource_leak`. **Expected recovery:** `rollback` on `orders`.

Orders release o81 adds subscription callbacks that remain retained after checkout completes. Under flat arrivals, memory grows from 42% to 95% and major pauses appear; the process restarts twice and callers become slow. A payments rollout at minute 75 is a distractor because callback retention and memory growth started earlier. Roll back orders to o80.

Distractors and checks:

- Payments release p82 at minute 75 occurs after retained subscriptions and memory growth begin; payment processing latency stays at baseline.
- Support: `search_logs({"limit": 20, "service": "orders"})` must include `completed request objects still referenced`.
- Support: `query_metric({"metric": "memory", "service": "orders"})` must include `first sustained deviation: t=`.
- Counterevidence: `search_logs({"limit": 20, "service": "payments"})` must include `latency steady at 90ms`.
