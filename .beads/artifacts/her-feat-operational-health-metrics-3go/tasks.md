---
purpose: Task decomposition with dependency tracking
updated: 2026-06-16
---

# Tasks: her-feat-operational-health-metrics-3go

## Task Metadata

```yaml
id: "1.1"
depends_on: []
parallel: true
conflicts_with: []
files: ["prometheus_metrics.py"]
estimated_minutes: 15
```

## 1. Metric Definitions

### 1.1 Define health counters and gauge in prometheus_metrics.py

```yaml
depends_on: []
parallel: false
files: ["prometheus_metrics.py"]
estimated_minutes: 15
```

- [ ] Add module-level variables for new metrics: `_usage_extraction_failures`, `_db_write_errors`, `_db_read_errors`, `_ws_broadcast_failures`, `_ws_dead_clients`, `_ws_active_connections`
- [ ] In `_init_metrics()`, create Counter objects for each error counter with HELP text
- [ ] In `_init_metrics()`, create Gauge object for `ws_active_connections` with HELP text
- [ ] Add increment functions: `increment_usage_extraction_failure()`, `increment_db_write_error()`, `increment_db_read_error()`, `increment_ws_broadcast_failure()`, `increment_ws_dead_client()`
- [ ] Add `set_ws_active_connections(count: int)` function for the gauge
- [ ] All increment/set functions are no-ops when `_PROMETHEUS_AVAILABLE` is False
- [ ] Include `# TYPE` and `# HELP` metadata (handled automatically by prometheus_client)

### 1.2 Expose new functions in module public API

```yaml
depends_on: ["1.1"]
parallel: false
files: ["prometheus_metrics.py"]
estimated_minutes: 5
```

- [ ] Ensure all new increment/set functions are importable (not prefixed with `_`)
- [ ] Add new functions to any `__all__` list if present

## 2. Error Path Instrumentation

### 2.1 Instrument usage extraction failures in __init__.py

```yaml
depends_on: ["1.1"]
parallel: true
files: ["__init__.py"]
estimated_minutes: 10
```

- [ ] In `_extract_usage()`, detect when input is a non-empty dict but result is (0, 0)
- [ ] Call `increment_usage_extraction_failure()` from `prometheus_metrics` on failure
- [ ] Use lazy import to avoid circular dependency issues

### 2.2 Instrument DB errors in __init__.py

```yaml
depends_on: ["1.1"]
parallel: true
files: ["__init__.py"]
estimated_minutes: 10
```

- [ ] In `_persist_state()`, call `increment_db_write_error()` in the except block
- [ ] In `_hydrate_from_db()`, call `increment_db_read_error()` in the except block
- [ ] Use lazy import pattern consistent with existing code

### 2.3 Instrument WebSocket errors in api.py

```yaml
depends_on: ["1.1"]
parallel: true
files: ["api.py"]
estimated_minutes: 15
```

- [ ] In `ConnectionManager._safe_send()`, call `increment_ws_broadcast_failure()` on exception
- [ ] In `ConnectionManager._safe_send()`, call `increment_ws_dead_client()` when removing a dead client
- [ ] In `ConnectionManager.connect()`, call `set_ws_active_connections(self.count)` after adding client
- [ ] In `ConnectionManager.disconnect()`, call `set_ws_active_connections(self.count)` after removing client
- [ ] Use lazy import for prometheus_metrics to avoid circular import

## 3. Tests

### 3.1 Add tests for new health metrics

```yaml
depends_on: ["2.1", "2.2", "2.3"]
parallel: false
files: ["tests/test_prometheus.py"]
estimated_minutes: 15
```

- [ ] Test that all 6 new metrics are registered in REGISTRY (names in `REGISTRY.collect()`)
- [ ] Test `increment_usage_extraction_failure()` increments the counter
- [ ] Test `increment_db_write_error()` increments the counter
- [ ] Test `increment_db_read_error()` increments the counter
- [ ] Test `increment_ws_broadcast_failure()` increments the counter
- [ ] Test `increment_ws_dead_client()` increments the counter
- [ ] Test `set_ws_active_connections(n)` sets the gauge value
- [ ] Test all increment functions are no-ops when `_PROMETHEUS_AVAILABLE` is False
- [ ] Test new metrics appear in `generate_metrics()` output with HELP/TYPE lines

## 4. Verification

### 4.1 Full regression test

```yaml
depends_on: ["3.1"]
parallel: false
```

- [ ] `pytest tests/ -x` — all existing and new tests pass
- [ ] Verify no changes to existing metric names or HELP text
