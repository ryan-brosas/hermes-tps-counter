---
purpose: Product Requirements Document for a bead
updated: 2026-06-16
---

# PRD: Add Prometheus Histogram metrics for TPS and API latency distribution tracking (p50/p95/p99)

**Bead:** her-feat-prometheus-histogram-metrics-z5z | **Type:** feature | **Priority:** P2
**Created:** 2026-06-16 | **Estimate:** 90 minutes

## Problem

WHEN operators monitor TPS throughput in Grafana THEN they can only see instantaneous gauges (last, avg, peak) BECAUSE the plugin lacks histogram metrics that would reveal distribution percentiles (p50/p95/p99).

**Who is affected?** Operators and developers using Grafana dashboards to monitor LLM API performance. Without histograms, they cannot detect tail latency issues or TPS degradation trends — only spot-check instantaneous values.

**Why now?** The Prometheus infrastructure is complete (custom REGISTRY, aggregate/legacy metrics, cardinality guardrails). Histograms are the last standard metric type missing. Adding them completes the observability story and enables SLO-style monitoring (e.g., "p99 latency stays under 5s").

## Scope

### In Scope
- Two new Histogram metrics: `tps_distribution` and `api_call_latency_seconds`
- Per-model label on both histograms (bounded by existing cardinality cap)
- Helper functions for observation recording
- Integration into `_on_post_api_request` hook
- Tests for registration, observation, and /metrics output
- README documentation

### Out of Scope
- Per-session histogram labels (too high cardinality)
- Per-provider histogram labels (can be added later)
- Alerting rules or Grafana dashboard JSON
- Changes to existing gauge/counter metrics
- Changes to store.py, config.py, or api.py

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Add Histogram `tps_distribution` with buckets [1, 5, 10, 25, 50, 100, 250, 500, 1000] and label `model` | MUST | Metric registered in REGISTRY, appears in /metrics output |
| 2 | Add Histogram `api_call_latency_seconds` with buckets [0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60] and label `model` | MUST | Metric registered in REGISTRY, appears in /metrics output |
| 3 | Both histograms use existing custom REGISTRY | MUST | `REGISTRY.get_sample_value()` returns histogram data |
| 4 | Record observations from `_on_post_api_request` in `__init__.py` | MUST | After hook call, histogram buckets are non-zero |
| 5 | Graceful degradation when `prometheus_client` absent | MUST | No import errors, no runtime errors when prometheus_client not installed |
| 6 | Helper functions `observe_tps(value, model)` and `observe_latency(seconds, model)` | SHOULD | Functions exist in prometheus_metrics.py, callable from __init__.py |
| 7 | Include HELP and TYPE metadata | SHOULD | `/metrics` output includes `# HELP` and `# TYPE` lines for both histograms |
| 8 | Backward compatible with existing tests | MUST | All existing tests pass without modification |
| 9 | Tests for histogram registration, observation, and output | MUST | Tests cover: metric creation, observation recording, /metrics output format |

## Technical Context

**Key files:**
- `prometheus_metrics.py` — Metric definitions, `update_metrics()`, `generate_metrics()`. Add histogram objects and helpers here.
- `__init__.py` — Plugin hook `_on_post_api_request()`. Call histogram helpers with TPS value and latency from here.
- `tests/test_prometheus.py` — Existing Prometheus tests. Add histogram test cases.

**Existing patterns:**
- All metrics use `REGISTRY = CollectorRegistry()` (isolated from global default)
- Gauges/counters defined as module globals, initialized in `_init_metrics()`
- `update_metrics()` called after each hook — histograms should follow same pattern
- `_PROMETHEUS_AVAILABLE` flag guards all prometheus_client code
- Cardinality cap via `_admit_label()` for model/provider labels — histograms should reuse this

**Constraints:**
- Thread-safe: `Histogram.observe()` in prometheus_client is internally thread-safe
- Model label must be bounded by `_label_cardinality_cap` (reuse `_admit_label()`)
- Don't modify existing metric names or behavior

## Approach

Add two `Histogram` objects to `prometheus_metrics.py` alongside existing gauges/counters. Create `observe_tps()` and `observe_latency()` helper functions that check `_PROMETHEUS_AVAILABLE` and cardinality cap before recording. Call these helpers from `_on_post_api_request()` in `__init__.py` after computing TPS and duration.

**Alternatives considered:**
1. **Summary instead of Histogram** — Rejected: Summary calculates quantiles client-side, can't be aggregated across instances. Histogram + Prometheus server-side `histogram_quantile()` is the standard pattern.
2. **Separate registry for histograms** — Rejected: Adds complexity, no benefit. Custom REGISTRY already isolates metrics.
3. **No model label on histograms** — Rejected: Per-model distribution is the primary use case (compare latency across models).

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| High-cardinality explosion from model label | Low | High | Reuse existing `_admit_label()` cap; overflow observations discarded silently |
| Bucket boundaries don't match real-world TPS/latency | Low | Low | Buckets chosen from typical LLM ranges; can adjust later without breaking changes |
| Performance impact of histogram observe() | Low | Low | prometheus_client observe() is O(log n) on bucket count, sub-microsecond |

## Acceptance Criteria

- `tps_distribution` histogram registered in REGISTRY with correct buckets and model label
- `api_call_latency_seconds` histogram registered in REGISTRY with correct buckets and model label
- Helper functions `observe_tps()` and `observe_latency()` exist and are called from hook
- All existing tests pass (240+ tests, zero regressions)
- New histogram-specific tests pass (registration, observation, output format)
- Graceful degradation confirmed (no errors when prometheus_client absent)
- Model label bounded by cardinality cap

## Success Criteria

- [ ] `tps_distribution` histogram appears in `/metrics` output with correct buckets and HELP/TYPE
  - Verify: `curl localhost:PORT/metrics | grep tps_distribution`
- [ ] `api_call_latency_seconds` histogram appears in `/metrics` output with correct buckets and HELP/TYPE
  - Verify: `curl localhost:PORT/metrics | grep api_call_latency_seconds`
- [ ] Observations recorded correctly after API hook calls
  - Verify: `prometheus_client.REGISTRY.get_sample_value('tps_distribution_count') > 0`
- [ ] Model label works and is bounded by cardinality cap
  - Verify: Add 51 distinct models, 51st goes to overflow
- [ ] All existing tests pass (240+ tests)
  - Verify: `pytest tests/ -x`
- [ ] New histogram tests pass
  - Verify: `pytest tests/test_prometheus.py -k histogram -v`
- [ ] No regressions when prometheus_client absent
  - Verify: `pytest tests/` with prometheus_client uninstalled
