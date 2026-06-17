---
purpose: Agent spawn context for a bead
updated: 2026-06-16
---

# Context Capsule: her-feat-operational-health-metrics-3go

## Objective

Add 5 Prometheus counters and 1 gauge for plugin operational health monitoring: usage extraction failures, DB read/write errors, WebSocket broadcast failures, dead client removals, and active connection count.

## Key Patterns

- `Custom REGISTRY` — All metrics registered in `_init_metrics()` via the isolated `CollectorRegistry`. New metrics MUST use `registry=REGISTRY`. Reference: `prometheus_metrics.py:49-122`
- `Graceful degradation` — All metric functions check `_PROMETHEUS_AVAILABLE` before operating. New increment functions must be no-ops when prometheus_client is absent. Reference: `prometheus_metrics.py:19-24`
- `Lazy import from api.py` — `api.py` is imported by `__init__.py`, so `api.py` must use lazy imports for `prometheus_metrics` to avoid circular dependency. Reference: `__init__.py:368` (existing lazy import pattern)
- `Thread-safe increments` — `prometheus_client` Counter `.inc()` is internally thread-safe. No external locking needed for counter increments. Reference: `prometheus_metrics.py:138`
- `reset_metrics pattern` — `_init_metrics()` recreates all metric objects. New metrics must be included. `reset_metrics()` calls `_init_metrics()`. Reference: `prometheus_metrics.py:216-218`

## Constraints

1. All new metrics use the existing custom `REGISTRY` — never the global default
2. Counter increments must be safe for concurrent hook calls (prometheus_client is internally thread-safe)
3. New increment functions are no-ops when `_PROMETHEUS_AVAILABLE` is False
4. `api.py` must use lazy import for `prometheus_metrics` to avoid circular dependency
5. No changes to `store.py` or `config.py` (forbidden by agent_context)
6. All existing tests must pass with no regressions

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Define metrics | `prometheus_metrics.py` — add counters, gauge, increment/set functions | `store.py`, `config.py` |
| Instrument errors | `__init__.py` — add increment calls in error paths | `store.py`, `config.py`, `.pi/` |
| Instrument WS | `api.py` — add increment/set calls in ConnectionManager | `store.py`, `config.py`, `.pi/` |
| Tests | `tests/test_prometheus.py` — add test classes/methods | `store.py`, `config.py` |

## Graph Context

- **Blast radius:** `prometheus_metrics.py`, `__init__.py`, `api.py`, `tests/test_prometheus.py`
- **Related beads:** None (standalone feature)
- **File history:** `prometheus_metrics.py` recently added (Prometheus metrics feature); `api.py` recently added (REST API feature)
