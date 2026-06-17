---
purpose: Product Requirements Document for a bead
updated: 2026-06-16
---

# PRD: Prometheus Metrics Exporter Endpoint for TPS Data

**Bead:** her-prometheus-metrics-exporter-17t | **Type:** feature | **Priority:** P2
**Created:** 2026-06-16 | **Estimate:** 60 minutes

## Problem

WHEN a user wants to integrate TPS metrics into their existing monitoring infrastructure (Grafana, Prometheus, Datadog) THEN they cannot because BECAUSE the plugin only exposes metrics via a custom JSON REST API (`/api/v1/*`). There is no standard metrics endpoint that monitoring scrapers can consume. Users must build custom adapters or polling scripts to bridge the gap, which is fragile and non-standard.

**Who is affected?** Anyone running Hermes in production who already has Prometheus/Grafana infrastructure and wants TPS dashboards alongside their other metrics. Also affects anyone who wants to set up alerting on TPS degradation.

**Why now?** The plugin has a working REST API (bead `her-rest-api-tps-endpoints-56b`), per-model and per-provider tracking (beads `her-her-per-model-tps-tracking-h6f`, `her-provider-tps-aggregation-nkj`), and persistence (bead `her-session-data-persistence-sqlite-8l5`). The data layer is complete — this bead adds the standard export format. It's a low-effort, high-leverage integration that makes the plugin production-ready for monitoring workflows.

## Scope

### In Scope
- `/metrics` endpoint in Prometheus text exposition format
- Gauge metrics: `tps_last_call`, `tps_avg`, `tps_peak` per session
- Counter metrics: `tps_tokens_total` (labels: session_id, direction), `tps_api_calls_total` (label: session_id)
- Gauge metrics: per-model `tps_model_avg`, `tps_model_peak` (labels: session_id, model)
- Gauge metrics: per-provider `tps_provider_avg`, `tps_provider_peak` (labels: session_id, provider)
- HELP and TYPE metadata for each metric
- Optional: enabled via plugin config (`api.prometheus.enabled`)
- Thread-safe metric updates using existing `_STATE_LOCK` pattern
- Tests for all new code
- Backward compatible with existing tests

### Out of Scope
- Prometheus pushgateway support (pull/scrape model only)
- Custom Grafana dashboards (user creates their own)
- Alerting rules (Prometheus Alertmanager handles this)
- Histogram buckets for TPS distribution (future optimization)
- Per-call event metrics (depends on event storage bead `her-per-call-event-storage-f1v`)

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | `/metrics` endpoint returns Prometheus text format | MUST | `GET /metrics` returns 200 with `Content-Type: text/plain; version=0.0.4; charset=utf-8`. Verify: response contains `# HELP` and `# TYPE` lines |
| 2 | Gauge metrics for session TPS | MUST | `tps_last_call`, `tps_avg`, `tps_peak` gauges with `session_id` label. Verify: after recording 2 calls, metrics contain correct values |
| 3 | Counter metrics for tokens and calls | MUST | `tps_tokens_total` counter with `direction` label (input/output), `tps_api_calls_total` counter. Verify: values match session totals |
| 4 | Per-model gauge metrics | MUST | `tps_model_avg`, `tps_model_peak` with `session_id` and `model` labels. Verify: metrics reflect per-model data |
| 5 | Per-provider gauge metrics | MUST | `tps_provider_avg`, `tps_provider_peak` with `session_id` and `provider` labels. Verify: metrics reflect per-provider data |
| 6 | Thread-safe metric updates | MUST | Concurrent hook calls update metrics without race conditions. Verify: 4-thread concurrent test passes |
| 7 | Configurable enable/disable | SHOULD | `prometheus.enabled` in plugin config, defaults to false. Verify: disabled by default, enabled when configured |
| 8 | Mount on existing FastAPI app | SHOULD | If API server is enabled, `/metrics` is added to the same app. Verify: `/api/v1/health` and `/metrics` on same port |
| 9 | Backward compatible | MUST | All existing tests pass. Verify: `pytest tests/ -v` — 0 failures |
| 10 | New tests | MUST | `tests/test_prometheus.py` with coverage of all metrics. Verify: all tests green |

## Technical Context

**Key files:**
- `__init__.py` — Plugin hook `_on_post_api_request` (update Prometheus metrics after each call)
- `api.py` — FastAPI app factory `create_app()` (mount `/metrics` endpoint)
- `tests/test_prometheus.py` — New test file

**Existing patterns:**
- `_STATE_LOCK` threading.Lock for all state mutations
- `_MODELS` and `_PROVIDERS` dicts for per-model/provider tracking
- FastAPI endpoints use Pydantic response models
- Tests use `tmp_path` fixture + `PersistentSessionStore` + `mock_hermes_cli` autouse fixture
- Plugin config read via `ctx.get_config("tps_counter", {})`

**Dependencies:**
- `prometheus_client` library (Python) — standard Prometheus client
- Must be an optional dependency (import with try/except, graceful degradation)

**Constraints:**
- `prometheus_client` may not be installed — plugin must work without it
- Metric updates must not slow down the hot path (< 1ms overhead)
- Must not conflict with other `prometheus_client` registrations (use a custom Registry)

## Approach

**Chosen: prometheus_client with custom Registry**

Use the `prometheus_client` Python library with a custom `CollectorRegistry` to avoid global state conflicts. The registry is passed to a custom Starlette/ASGI middleware or a dedicated route handler mounted on the existing FastAPI app. Metrics are updated inside `_on_post_api_request` alongside existing state updates.

**Why this approach:**
- Standard — `prometheus_client` is the canonical Python Prometheus library
- Isolated — custom Registry prevents conflicts with other plugins or applications
- Simple — update gauges/counters in the existing hook, no new threads or background work
- Compatible — mounts on existing FastAPI app when API is enabled

**Alternatives considered:**

1. **Custom text format (no library)** — Rejected: reinventing the wheel, error-prone format details, no Histogram support if needed later.

2. **Standalone HTTP server** — Rejected: another port, another thread, more config surface. Better to mount on existing FastAPI app.

3. **Prometheus pushgateway** — Rejected: push model requires a running pushgateway, more infrastructure. Pull/scrape is the standard pattern.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `prometheus_client` not installed | Medium | Low | Graceful degradation: import with try/except, `/metrics` returns 503 if unavailable |
| Metric name collisions with other plugins | Low | Medium | Use custom Registry, not the global default |
| Gauge updates on hot path slow down API calls | Low | Low | `prometheus_client` gauge set is sub-microsecond |
| Memory growth from per-session label cardinality | Medium | Medium | Cap label count or auto-remove stale session labels after eviction |

## Success Criteria

- [ ] `GET /metrics` returns Prometheus text format with HELP/TYPE metadata
    - Verify: response contains `# HELP tps_last_call` and `# TYPE tps_last_call gauge`
- [ ] Session TPS gauges reflect current state
    - Verify: record 2 calls, `tps_last_call` and `tps_avg` have correct values
- [ ] Token counters increment correctly
    - Verify: `tps_tokens_total{direction="output"}` matches session total_output_tokens
- [ ] Per-model metrics appear with correct labels
    - Verify: record call with model="openai/gpt-4o", metric has `model="openai/gpt-4o"` label
- [ ] Per-provider metrics appear with correct labels
    - Verify: record call with model="openai/gpt-4o", metric has `provider="openai"` label
- [ ] Plugin works when `prometheus_client` is not installed
    - Verify: import fails gracefully, `/metrics` returns 503 or is not mounted
- [ ] All existing tests pass
    - Verify: `pytest tests/ -v` — 0 failures
- [ ] New tests achieve full coverage of new code
    - Verify: `pytest tests/test_prometheus.py -v` — all green

## Acceptance Criteria

- [ ] `/metrics` endpoint returns 200 with `Content-Type: text/plain; version=0.0.4; charset=utf-8`
- [ ] Response contains `# HELP` and `# TYPE` lines for each metric
- [ ] `tps_last_call`, `tps_avg`, `tps_peak` gauges have `session_id` label
- [ ] `tps_tokens_total` counter has `session_id` and `direction` labels
- [ ] `tps_api_calls_total` counter has `session_id` label
- [ ] `tps_model_avg`, `tps_model_peak` have `session_id` and `model` labels
- [ ] `tps_provider_avg`, `tps_provider_peak` have `session_id` and `provider` labels
- [ ] Plugin degrades gracefully when `prometheus_client` is not installed
- [ ] All existing tests (test_api, test_persistence, test_provider_tps, test_store_delete, test_usage_parsing) still pass
- [ ] New test_prometheus.py has full coverage of new code
