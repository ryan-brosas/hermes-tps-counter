---
purpose: Product Requirements Document for a bead
updated: 2026-06-16
---

# PRD: Add comprehensive health diagnostics endpoint for plugin runtime state visibility

**Bead:** her-feat-health-diagnostics-endpoint-o3m | **Type:** feature | **Priority:** P2
**Created:** 2026-06-16 | **Estimate:** 45 minutes

## Problem

WHEN operators need to diagnose tps-counter plugin runtime state THEN they must scrape Prometheus metrics, connect to WebSocket, query REST endpoints, and check logs separately BECAUSE the existing `/api/v1/health` endpoint only reports DB connectivity with no component-level detail.

**Who is affected?** Operators and developers debugging tps-counter in production. When TPS data looks wrong or the plugin misbehaves, they have no single endpoint to check overall plugin health — they must piece together state from multiple sources.

**Why now?** The operational health metrics bead (`her-feat-operational-health-metrics-3go`) explicitly deferred this work: "New API endpoints for health detail (SHOULD — deferred)". The operational health counters are now implemented, providing the data sources. This bead wires them into a diagnostic endpoint. Without it, the counters exist in Prometheus but there's no human-readable diagnostic view accessible via the REST API.

## Scope

### In Scope
- New `GET /api/v1/health/diagnostics` endpoint returning JSON with component status breakdown
- Component sections: `memory`, `sqlite`, `prometheus`, `websocket`, `health_counters`
- Each component has `status` (ok/degraded/unavailable) and `detail` fields
- Backward compatible: existing `GET /api/v1/health` endpoint unchanged
- Thread-safe reads from all state sources
- Graceful degradation: failing components report `degraded` status, don't crash the endpoint
- Tests for all component states and the combined response
- README documentation

### Out of Scope
- Changes to `store.py`, `config.py`, `prometheus_metrics.py`, or `__init__.py`
- Grafana dashboard provisioning
- Alerting rules
- Authentication or authorization on the endpoint
- Per-session diagnostic detail (use existing endpoints for that)

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | New endpoint `GET /api/v1/health/diagnostics` | MUST | Returns 200 with JSON body containing component statuses |
| 2 | `memory` component: session count, max sessions, model count, provider count | MUST | `memory.status` = "ok", `memory.sessions` = count, `memory.max_sessions` = config value |
| 3 | `sqlite` component: connected status, session count, event count, retention days | MUST | `sqlite.status` = "ok" or "unavailable" based on store state |
| 4 | `prometheus` component: enabled status, metrics available, registry status | MUST | `prometheus.enabled` = bool, `prometheus.available` = bool |
| 5 | `websocket` component: active connections, enabled status | MUST | `websocket.active_connections` = count |
| 6 | `health_counters` component: all operational counter values | MUST | Reports usage_extraction_failures, db_write_errors, db_read_errors, ws_broadcast_failures, ws_dead_clients |
| 7 | Each component has `status` field (ok/degraded/unavailable) | MUST | Component failure returns degraded, not 500 |
| 8 | Backward compatible: existing `/api/v1/health` unchanged | MUST | Existing tests pass, endpoint behavior identical |
| 9 | Thread-safe reads | MUST | No race conditions when reading from _SESSIONS, _STORE, etc. |
| 10 | Tests for all component states | MUST | Each component has tests for ok, degraded, and unavailable states |
| 11 | README section documenting the new endpoint | SHOULD | Endpoint documented with example response |

## Technical Context

**Key files:**
- `api.py` — App factory `create_app()`. Add new endpoint here. Needs access to `store` (already passed to `create_app`), plus in-memory state from `__init__.py`.
- `tests/test_api.py` — Existing API tests. Add diagnostic endpoint tests.
- `README.md` — Document new endpoint.

**Existing patterns:**
- `create_app(store)` receives the `PersistentSessionStore` instance — use it for SQLite stats
- In-memory state (`_SESSIONS`, `_MODELS`, `_PROVIDERS`) lives in `__init__.py` — need a getter function or import
- `prometheus_metrics.py` has `metrics_available()` and `REGISTRY` — use for Prometheus status
- `ConnectionManager` is stored on `app.state.ws_manager` — use for WebSocket stats
- Operational health counters have `get_*_count()` functions in `prometheus_metrics.py`

**Constraints:**
- `api.py` should NOT import `__init__.py` (circular dependency risk) — need a clean interface
- Option 1: Pass a diagnostic callable to `create_app(store, diagnostics_fn=None)`
- Option 2: Add a module-level function in `__init__.py` that api.py calls lazily
- Option 3: Store diagnostic state on `app.state` during app creation
- Thread-safe: `_STATE_LOCK` protects `_SESSIONS`/`_MODELS`/`_PROVIDERS` reads
- Graceful degradation: if any component fails to report, return `degraded` status for that component

**Data sources:**
- Memory: `_SESSIONS`, `_MODELS`, `_PROVIDERS` from `__init__.py` (via `_STATE_LOCK`)
- SQLite: `store.count()`, `store.load_events()` for event count
- Prometheus: `prometheus_metrics.metrics_available()`, `prometheus_metrics.REGISTRY`
- WebSocket: `app.state.ws_manager.count`
- Health counters: `prometheus_metrics.get_*_count()` functions

## Approach

Add a new `GET /api/v1/health/diagnostics` endpoint in `api.py::create_app()`. The endpoint reads from multiple sources and assembles a JSON response with component-level status. Use a callback pattern: `create_app(store, get_diagnostics=None)` where `get_diagnostics` is a callable provided by `__init__.py` that returns in-memory state snapshot. This avoids circular imports while keeping the interface clean.

**Alternatives considered:**
1. **Import __init__.py directly from api.py** — Rejected: circular import risk (api.py is imported by __init__.py)
2. **Store all state on app.state** — Rejected: state changes after app creation wouldn't be reflected
3. **Separate diagnostics microservice** — Rejected: massive overkill for a plugin health check
4. **Extend existing /api/v1/health** — Rejected: breaking change for existing consumers; new endpoint is additive

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Circular import between api.py and __init__.py | Medium | High | Use callback pattern: get_diagnostics passed at app creation |
| Performance impact of reading multiple state sources | Low | Low | All reads are in-memory or single SQLite queries; sub-millisecond |
| Thread safety on concurrent reads | Low | Medium | Use existing _STATE_LOCK for memory reads; SQLite reads use store's internal lock |
| Breaking existing /api/v1/health consumers | Low | Low | New endpoint is additive; existing endpoint unchanged |

## Success Criteria

- [ ] `GET /api/v1/health/diagnostics` returns 200 with JSON containing all 5 component sections
    - Verify: `curl localhost:9127/api/v1/health/diagnostics | jq .`
- [ ] Each component has `status` field (ok/degraded/unavailable)
    - Verify: Response JSON has `.memory.status`, `.sqlite.status`, etc.
- [ ] Health counters are reported accurately
    - Verify: Counter values in response match Prometheus `/metrics` output
- [ ] Existing `/api/v1/health` endpoint unchanged
    - Verify: `curl localhost:9127/api/v1/health` returns same format as before
- [ ] All existing tests pass (no regressions)
    - Verify: `pytest tests/ -x`
- [ ] New diagnostic endpoint tests pass
    - Verify: `pytest tests/test_api.py -k diagnostics -v`
- [ ] Graceful degradation: component failure doesn't crash endpoint
    - Verify: Test with broken store returns sqlite.status = "unavailable", overall 200
