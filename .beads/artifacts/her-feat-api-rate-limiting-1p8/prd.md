---
purpose: Product Requirements Document for a bead
updated: 2026-06-17
---

# PRD: Add per-IP rate limiting middleware to REST API endpoints to protect SQLite backend from burst requests

**Bead:** her-feat-api-rate-limiting-1p8 | **Type:** feature | **Priority:** P2
**Created:** 2026-06-17 | **Estimate:** 75 minutes

## Problem

WHEN the optional FastAPI REST API is enabled and clients send burst requests to session, summary, event, trend, diagnostics, or metrics endpoints THEN each request can trigger SQLite reads and health probes without backpressure BECAUSE the current API app has no per-client throttling layer before endpoint handlers access the SQLite-backed store.

**Who is affected?** Operators running the tps-counter API locally or on a reachable interface, dashboard users depending on responsive REST metrics, and the SQLite backend shared by monitoring endpoints.
**Why now?** The API now exposes multiple read-heavy endpoints and Prometheus diagnostics; burst traffic can degrade monitoring reliability unless the API rejects excess requests early with a predictable HTTP contract.

## Scope

### In Scope
- Add in-process per-IP rate limiting middleware for REST/HTTP endpoints created by `api.create_app`.
- Make default request rate and burst size configurable through `TPSConfig`, including TOML, environment, and Hermes context override paths.
- Return HTTP 429 with a `Retry-After` header and JSON error detail when a client exceeds the configured limit.
- Exempt `/api/v1/health` from rate limiting so basic liveness checks continue during bursts.
- Track rate-limited requests with a Prometheus counter named `tps_api_rate_limited_total` when Prometheus is available.
- Bound memory growth by cleaning up stale per-IP request state.
- Add focused tests for allowed requests, throttled requests, health exemption, config loading/validation, stale cleanup behavior, and Prometheus metric exposure.

### Out of Scope
- Distributed rate limiting across processes or hosts.
- Redis, database-backed throttling, slowapi, or any new external dependency.
- Authentication, API keys, user-level quotas, or endpoint-specific policy tiers.
- Rate limiting WebSocket message flow on `/ws/tps` unless it is naturally covered by the HTTP handshake middleware.
- Changing successful response schemas or status codes for requests that are not rate-limited.

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Apply per-IP rate limiting before REST endpoint handlers perform SQLite-backed work. | MUST | Repeated requests from one client beyond the configured allowance receive 429 without invoking the protected handler/store path. |
| 2 | Preserve existing behavior for requests under the limit. | MUST | Existing API tests for health, session TPS, sessions list, summary, events, trends, diagnostics, metrics, and store-unavailable cases continue to pass except where new tests explicitly exercise throttling. |
| 3 | Return standards-friendly throttle responses. | MUST | A throttled request returns HTTP 429, includes `Retry-After`, and returns a JSON body with a clear rate-limit detail. |
| 4 | Make limits configurable via `TPSConfig`. | MUST | `requests_per_minute` and `burst_size` defaults are present, load from flat/TOML and nested API config where appropriate, load from `TPS_COUNTER_*` env vars, load from Hermes context config, and validate/clamp invalid values. |
| 5 | Avoid external dependencies. | MUST | Implementation uses stdlib data structures such as `collections.deque` plus existing FastAPI/Starlette middleware hooks; no Redis, slowapi, or package dependency is added. |
| 6 | Exempt the health endpoint. | SHOULD | `/api/v1/health` continues returning liveness information even when the same client is otherwise over limit. |
| 7 | Prevent unbounded per-IP state growth. | MUST | Stale client entries are pruned after their request windows expire, with tests covering cleanup. |
| 8 | Observe throttling in Prometheus. | MUST | `prometheus_metrics.py` exposes an increment helper and `/metrics` includes `tps_api_rate_limited_total` after throttled requests when Prometheus is available. |
| 9 | Log rate-limit events without noisy production logs. | SHOULD | Throttled requests are logged at DEBUG with client identity and retry timing, without logging request bodies or secrets. |

## Technical Context

Key files:
- `api.py`: builds the FastAPI app in `create_app(store, get_diagnostics=None)`, installs CORS middleware, creates REST endpoints under `/api/v1/*`, exposes `/metrics`, and reads SQLite-backed data through the provided store.
- `config.py`: defines `TPSConfig`, `_ENV_FIELD_MAP`, TOML loading, environment loading, context override loading, and validation for API-related configuration.
- `prometheus_metrics.py`: owns a custom Prometheus registry plus counters, gauges, histograms, and small increment/set helpers for operational events.
- `tests/test_api.py`: covers current REST endpoint contracts with `fastapi.testclient.TestClient` and temporary `PersistentSessionStore` instances.
- `tests/test_config.py`: covers default config, environment overrides, TOML loading, context overrides, merge precedence, singleton behavior, and validation.

Current REST endpoints include `/api/v1/health`, `/api/v1/sessions/{session_id}/tps`, `/api/v1/sessions`, `/api/v1/summary`, `/api/v1/events/{session_id}`, `/api/v1/trends/{session_id}`, `/api/v1/health/diagnostics`, `/metrics`, and WebSocket `/ws/tps`.

The bead's existing agent context restricts implementation to `api.py`, `config.py`, `prometheus_metrics.py`, `tests/test_api.py`, `tests/test_config.py`, and `tests/test_rate_limiting.py`; it also forbids changing bead DB, local env files, credentials, and planning artifacts in this repair pass.

## Approach

Implement a small in-process sliding-window limiter as FastAPI/Starlette middleware created inside or near `create_app`. Resolve the client key from request client host, maintain a bounded deque of timestamps per IP, prune timestamps outside the configured window, and reject when the current window plus burst policy is exhausted. Put the limiter before endpoint logic so SQLite calls are avoided for over-limit clients, and exempt `/api/v1/health` from the check.

Extend `TPSConfig` with `requests_per_minute` and `burst_size` fields plus loading from env/TOML/context. Add validation to clamp non-positive values to safe defaults or minimums. Extend `prometheus_metrics.py` with `tps_api_rate_limited_total` and a helper used by the middleware. Tests should use small config values and monkeypatchable time/client identity where needed to deterministically prove allow, deny, retry, cleanup, and metric behavior.

**Alternatives considered:** external libraries such as slowapi or Redis-backed distributed rate limits were rejected because this plugin should remain local, lightweight, and dependency-free. Endpoint-by-endpoint decorators were rejected because middleware gives consistent coverage and avoids duplicated SQLite-protection logic.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Middleware accidentally throttles health probes needed by supervisors. | Med | Med | Explicitly exempt `/api/v1/health` and test the exemption while other endpoints are throttled. |
| Client IP detection is ambiguous behind proxies. | Med | Low | Use `request.client.host` for local/default behavior and document that proxy-aware forwarding is out of scope. |
| In-memory limiter state grows with many spoofed or short-lived IPs. | Med | Med | Prune stale deques and remove empty per-IP entries on each request or scheduled cleanup opportunity. |
| Tests become flaky if based on wall-clock sleep. | Med | Med | Isolate limiter time source so tests can advance time deterministically. |
| Prometheus optional dependency is absent in some environments. | Low | Low | Follow existing graceful no-op pattern for metrics helpers when Prometheus is unavailable. |

## Tasks (for epics)

| Task | Depends On | Parallel | Files |
|------|-----------|----------|-------|
| N/A — single feature bead. | N/A | N/A | N/A |

## Success Criteria

- [ ] Burst requests from one IP to protected REST endpoints eventually receive HTTP 429 before hitting SQLite-backed handler logic.
    - Verify: `python -m pytest tests/test_rate_limiting.py`
- [ ] Throttled responses include `Retry-After` and clear JSON detail, while under-limit requests preserve existing response contracts.
    - Verify: `python -m pytest tests/test_api.py tests/test_rate_limiting.py`
- [ ] `TPSConfig` supports `requests_per_minute` and `burst_size` from defaults, TOML, environment, and context override paths with validation.
    - Verify: `python -m pytest tests/test_config.py`
- [ ] `/api/v1/health` remains exempt from throttling.
    - Verify: targeted health exemption test in `tests/test_rate_limiting.py`
- [ ] Prometheus exposes `tps_api_rate_limited_total` when rate-limited requests occur and Prometheus is available.
    - Verify: targeted metrics test in `tests/test_rate_limiting.py` or `tests/test_prometheus.py`
- [ ] All affected tests pass and no external dependencies are introduced.
    - Verify: `python -m pytest tests/test_api.py tests/test_config.py tests/test_rate_limiting.py tests/test_prometheus.py`
