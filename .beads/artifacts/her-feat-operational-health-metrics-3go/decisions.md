---
purpose: Decision log for a bead
updated: 2026-06-16
---

# Decisions: her-feat-operational-health-metrics-3go

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Add new metrics to existing `prometheus_metrics.py` module | Keeps all metric definitions in one place; avoids import complexity | High |
| 2 | Use standalone increment functions (not update_metrics pattern) | Health counters are event-driven (fire on error), not state-synced like TPS gauges | High |
| 3 | Expose `ws_active_connections` as a Gauge updated on connect/disconnect | Direct reflection of ConnectionManager.count; no need for periodic polling | High |
| 4 | Use lazy import in `api.py` for prometheus_metrics | Avoids circular import between api.py and prometheus_metrics.py since api.py is imported by __init__.py | High |
| 5 | No labels on health counters (single-series per metric) | Error counters don't need session_id dimension — they're plugin-global health signals | Medium |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Per-session error counters with `session_id` label | Unbounded cardinality; health signals are plugin-global, not per-session | Cardinality explosion in Prometheus |
| 2 | Separate health registry | Adds complexity; existing REGISTRY isolation is sufficient | Unnecessary abstraction layer |
| 3 | Single `plugin_errors_total` counter with `type` label | Conflates different failure modes; separate counters are easier to alert on individually | Harder to set per-error-type thresholds |
| 4 | Add health detail endpoint in this bead | Out of scope; can be added in a follow-up bead | Scope creep delays delivery |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | `prometheus_client` Counter `.inc()` is thread-safe | Documented in prometheus_client docs | Would need external locking |
| 2 | Existing `_init_metrics()` can be extended without breaking tests | `_reset_prometheus` fixture calls `reset_metrics()` → `_init_metrics()` | Tests may need fixture updates |
| 3 | `api.py` can import from `prometheus_metrics` without circular dependency | Need to verify import chain: __init__.py imports api.py, api.py would import prometheus_metrics | May need lazy import pattern |
