---
purpose: Task decomposition with dependency tracking
updated: 2026-06-16
---

# Tasks: her-feat-health-diagnostics-endpoint-o3m

## Task Metadata

```yaml
total_tasks: 5
waves: 3
parallel_in_wave_1: 2
parallel_in_wave_2: 2
estimated_total_minutes: 45
```

## 1. Endpoint Implementation

### 1.1 Add diagnostics endpoint to api.py

```yaml
depends_on: []
parallel: true
files: ["api.py"]
estimated_minutes: 20
```

- [ ] Add `get_diagnostics=None` parameter to `create_app(store, get_diagnostics=None)` signature
- [ ] Implement `_collect_memory_status(get_diagnostics)` — calls the callback, returns `{status, sessions, max_sessions, models, providers}`; returns `unavailable` if callback is None or raises
- [ ] Implement `_collect_sqlite_status(store)` — calls `store.count()` for session count, queries event count, returns `{status, connected, session_count, event_count, retention_days}`; returns `unavailable` on exception
- [ ] Implement `_collect_prometheus_status()` — calls `prometheus_metrics.metrics_available()`, checks `REGISTRY`, returns `{status, enabled, available, registered_collectors}`; returns `unavailable` on exception
- [ ] Implement `_collect_websocket_status(app)` — reads `app.state.ws_manager` for connection count, returns `{status, enabled, active_connections}`; returns `degraded` if no manager
- [ ] Implement `_collect_health_counters()` — calls `prometheus_metrics.get_*_count()` for each counter, returns `{status, usage_extraction_failures, db_write_errors, db_read_errors, ws_broadcast_failures, ws_dead_clients}`; returns `unavailable` on exception
- [ ] Register `GET /api/v1/health/diagnostics` route that calls all 5 collectors, assembles `{status, components: {memory, sqlite, prometheus, websocket, health_counters}, timestamp}`, returns 200
- [ ] Overall status: `ok` if all components ok, `degraded` if any degraded, `unavailable` if majority unavailable
- [ ] Thread-safe: wrap memory reads in try/except; SQLite uses store's internal locking; Prometheus registry is thread-safe

### 1.2 Document endpoint in README.md

```yaml
depends_on: []
parallel: true
files: ["README.md"]
estimated_minutes: 5
```

- [ ] Add "Health Diagnostics" section under API endpoints
- [ ] Document `GET /api/v1/health/diagnostics` with method, path, description
- [ ] Include example JSON response (all 5 components with ok status)
- [ ] Document status values: `ok`, `degraded`, `unavailable`
- [ ] Note backward compatibility: existing `/api/v1/health` unchanged

## 2. Integration Wiring

### 2.1 Wire get_diagnostics callback in __init__.py

```yaml
depends_on: ["1.1"]
parallel: true
files: ["__init__.py"]
estimated_minutes: 5
```

- [ ] Define `_get_diagnostics_snapshot()` function that reads `_SESSIONS`, `_MODELS`, `_PROVIDERS` under `_STATE_LOCK` and returns a dict
- [ ] Pass `_get_diagnostics_snapshot` as `get_diagnostics` argument when calling `create_app(store, get_diagnostics=_get_diagnostics_snapshot)`
- [ ] Verify: no circular import — `api.py` does NOT import `__init__.py`; callback flows the other direction

## 3. Testing

### 3.1 Write diagnostics endpoint tests

```yaml
depends_on: ["1.1"]
parallel: true
files: ["tests/test_api.py"]
estimated_minutes: 15
```

- [ ] Test: `GET /api/v1/health/diagnostics` returns 200 with all 5 component sections
- [ ] Test: each component has `status` field in {ok, degraded, unavailable}
- [ ] Test: memory component reports session count, max_sessions, models, providers
- [ ] Test: sqlite component reports connected, session_count, event_count
- [ ] Test: prometheus component reports enabled/available status
- [ ] Test: websocket component reports active_connections count
- [ ] Test: health_counters component reports all 5 counter values
- [ ] Test: graceful degradation — broken store returns sqlite.status="unavailable", overall 200
- [ ] Test: graceful degradation — no get_diagnostics callback returns memory.status="unavailable", overall 200
- [ ] Test: existing `/api/v1/health` endpoint unchanged (regression guard)
- [ ] Test: overall status is "ok" when all components ok
- [ ] Test: overall status is "degraded" when any component is degraded

## 4. Verification

### 4.1 Full regression suite

```yaml
depends_on: ["2.1", "3.1"]
parallel: false
```

- [ ] `pytest tests/ -x` — all tests pass, zero regressions
- [ ] `pytest tests/test_api.py -k diagnostics -v` — all diagnostic tests pass
- [ ] Existing `/api/v1/health` endpoint returns identical format (manual spot check)
