---
purpose: Product Requirements Document for a bead
updated: 2026-06-16
---

# PRD: Add operational health metrics for plugin self-monitoring

**Bead:** her-feat-operational-health-metrics-3go | **Type:** feature | **Priority:** P2
**Created:** 2026-06-16 | **Estimate:** 60

## Problem

WHEN the tps-counter plugin encounters extraction failures, DB errors, or WebSocket broadcast issues THEN operators have no visibility into these failures BECAUSE the plugin only exposes TPS throughput metrics, not operational health signals.

**Who is affected?** Operators monitoring Hermes plugin reliability via Prometheus/Grafana dashboards. Secondary: developers debugging production issues in tps-counter.

**Why now?** The plugin silently swallows errors (logged at debug/warning level) with no metric surface. Without counters, operators can't set alerts on error rates or diagnose degradation. The cost of inaction is blind spots in production monitoring.

## Scope

### In Scope
- Add Prometheus counters for operational failures: usage extraction failures, DB read/write errors, WebSocket broadcast failures, dead client removals
- Add Prometheus gauge for active WebSocket connections
- Increment counters from existing error paths in `__init__.py` and `api.py`
- All new metrics use the existing custom `REGISTRY` in `prometheus_metrics.py`
- Tests for all new metrics
- Backward compatible with existing tests and Prometheus output

### Out of Scope
- New API endpoints for health detail (SHOULD — deferred)
- Grafana dashboard provisioning
- Alerting rules or recording rules
- Changes to `store.py` or `config.py`

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Add counter `usage_extraction_failures_total` | MUST | Counter increments when `_extract_usage` returns (0,0) for non-empty input; visible in `/metrics` output |
| 2 | Add counter `db_write_errors_total` | MUST | Counter increments when `_persist_state` catches an exception; visible in `/metrics` output |
| 3 | Add counter `db_read_errors_total` | MUST | Counter increments when `_hydrate_from_db` catches an exception; visible in `/metrics` output |
| 4 | Add counter `ws_broadcast_failures_total` | MUST | Counter increments per failed client in `ConnectionManager._safe_send`; visible in `/metrics` output |
| 5 | Add counter `ws_dead_clients_total` | MUST | Counter increments when a dead client is removed in `ConnectionManager._safe_send`; visible in `/metrics` output |
| 6 | Add gauge `ws_active_connections` | MUST | Gauge reflects `ConnectionManager.count`; visible in `/metrics` output |
| 7 | All new metrics use the existing custom REGISTRY | MUST | New metrics registered in `_init_metrics()` alongside existing metrics |
| 8 | Thread-safe counter increments | MUST | Counter `.inc()` calls are safe for concurrent hook calls (prometheus_client is internally thread-safe) |
| 9 | Tests for all new metrics | MUST | Each new metric has at least one test verifying increment/set behavior |
| 10 | Backward compatible | MUST | Existing tests pass; existing `/metrics` output unchanged |

## Technical Context

**Key files:**
- `prometheus_metrics.py` — Metric definitions, `_init_metrics()`, `update_metrics()`, `generate_metrics()`. New counters/gauges go here.
- `__init__.py` — Hook callbacks `_on_post_api_request`, `_persist_state`, `_hydrate_from_db`. Error paths to instrument.
- `api.py` — `ConnectionManager` with `broadcast()`, `_safe_send()`. WebSocket error paths to instrument.
- `tests/test_prometheus.py` — Existing test patterns for metric verification.

**Constraints:**
- `prometheus_client` is optional — all new metrics must degrade gracefully when unavailable
- Existing `REGISTRY` is a custom `CollectorRegistry` (not global default)
- `prometheus_client` Counter `.inc()` and Gauge `.set()` are internally thread-safe
- New metrics should follow existing naming convention: `tps_` prefix for TPS metrics, new health metrics use descriptive names without prefix

**Existing error paths to instrument:**
- `_extract_usage()` returns `(0, 0)` when usage dict is malformed — this is a silent failure
- `_persist_state()` catches exceptions, logs warning, disables store
- `_hydrate_from_db()` catches exceptions, logs warning, returns None
- `ConnectionManager._safe_send()` catches WebSocketDisconnect/ConnectionError/RuntimeError, disconnects client

## Approach

Add new Counter and Gauge metric objects in `prometheus_metrics.py::_init_metrics()`. Expose increment functions (`increment_usage_extraction_failure`, `increment_db_write_error`, etc.) that are no-ops when prometheus_client is unavailable. Call these increment functions from the existing error paths in `__init__.py` and `api.py`. The `ws_active_connections` gauge is updated on connect/disconnect in `ConnectionManager`.

**Alternatives considered:**
- Using labels on existing counters (rejected: conflates throughput metrics with health signals)
- Separate health registry (rejected: adds complexity, existing REGISTRY isolation is sufficient)
- Logging-only approach (rejected: defeats the purpose — need machine-readable signals)

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Import cycle between `api.py` and `prometheus_metrics.py` | Low | High | Use lazy import or pass increment functions via app state |
| Performance impact on hot path | Low | Low | Counter `.inc()` is O(1) and lock-free in prometheus_client |
| Breaking existing test isolation | Medium | Medium | New `_reset_prometheus` fixture already resets REGISTRY; ensure new metrics are included |

## Acceptance Criteria

- [ ] All 6 new metrics (`usage_extraction_failures_total`, `db_write_errors_total`, `db_read_errors_total`, `ws_broadcast_failures_total`, `ws_dead_clients_total`, `ws_active_connections`) registered in custom REGISTRY
- [ ] Each error counter increments when its error condition is triggered (verified by tests)
- [ ] `ws_active_connections` gauge reflects live WebSocket connection count (verified by tests)
- [ ] All increment/set functions are no-ops when `prometheus_client` is unavailable
- [ ] All existing tests pass with no regressions
- [ ] New metrics include HELP and TYPE metadata in `/metrics` output

## Success Criteria

- [ ] All 6 new metrics visible in `/metrics` output with HELP and TYPE metadata
    - Verify: `curl localhost:PORT/metrics | grep -E '(usage_extraction_failures|db_write_errors|db_read_errors|ws_broadcast_failures|ws_dead_clients|ws_active_connections)'`
- [ ] Error counters increment when error conditions occur
    - Verify: Tests simulate error conditions and assert counter values > 0
- [ ] `ws_active_connections` gauge tracks connection count
    - Verify: Test connects/disconnects WebSocket and checks gauge value
- [ ] All existing tests pass
    - Verify: `pytest tests/ -x`
- [ ] No regressions in existing Prometheus output
    - Verify: Existing metric names and HELP/TYPE lines unchanged
