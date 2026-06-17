---
purpose: Wave-sequenced implementation plan
updated: 2026-06-16
---

# Plan: her-feat-operational-health-metrics-3go

**Goal:** Add Prometheus counters and gauges for operational health monitoring — error counters for usage extraction, DB read/write, and WebSocket failures, plus an active connections gauge.

## Graph Context

- **Blast radius:** `prometheus_metrics.py`, `__init__.py`, `api.py`, `tests/test_prometheus.py`
- **Unblocks:** Future health detail endpoint, Grafana health dashboards
- **Blocked by:** None (standalone feature)
- **Critical path:** No
- **Forecast:** ~60 minutes

## Observable Truths

1. Operators can scrape `/metrics` and see `usage_extraction_failures_total`, `db_write_errors_total`, `db_read_errors_total`, `ws_broadcast_failures_total`, `ws_dead_clients_total`, `ws_active_connections` with HELP/TYPE metadata
2. Each error counter increments when its corresponding error condition occurs in production code
3. `ws_active_connections` gauge accurately reflects the current WebSocket connection count
4. All existing tests pass with no regressions

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Health metric definitions | Counter/Gauge objects in REGISTRY | `prometheus_metrics.py` | Need |
| Increment functions | Thread-safe counter increment helpers | `prometheus_metrics.py` | Need |
| Error path instrumentation | Counter increments on failure | `__init__.py` | Need |
| WebSocket instrumentation | Counter/gauge increments on WS events | `api.py` | Need |
| Tests | Verification of all new metrics | `tests/test_prometheus.py` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | Define metrics + increment functions in `prometheus_metrics.py` | No | None | `pytest tests/test_prometheus.py -x` |
| 2 | Instrument error paths in `__init__.py` and `api.py` | Yes (parallel files) | Wave 1 complete | `pytest tests/ -x` |
| 3 | Write tests for new metrics | No | Wave 2 complete | `pytest tests/test_prometheus.py -x` |
| 4 | Full regression test | No | Wave 3 complete | `pytest tests/ -x` |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
pytest tests/test_prometheus.py -x -v
pytest tests/ -x
```
