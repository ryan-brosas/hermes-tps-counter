---
purpose: Decision log for a bead
updated: 2026-06-16
---

# Decisions: her-feat-prometheus-histogram-metrics-z5z

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Use Histogram (not Summary) | Histogram quantiles are computed server-side via Prometheus `histogram_quantile()`, enabling cross-instance aggregation. Summary quantiles are client-side and non-aggregatable. | High |
| 2 | Reuse existing custom REGISTRY | Already proven pattern in this codebase. Avoids global registry collisions. No benefit to a separate registry. | High |
| 3 | Bounded model label via `_admit_label()` | Reuses existing cardinality cap infrastructure. Prevents unbounded series. Overflow observations silently discarded. | High |
| 4 | Two separate histograms (not combined) | TPS (tok/s) and latency (seconds) have fundamentally different units and bucket ranges. Combining would lose semantic clarity. | High |
| 5 | Helper functions `observe_tps()` / `observe_latency()` | Encapsulates availability check + cardinality check. Keeps __init__.py hook code clean. Follows existing pattern (increment_* functions). | Medium |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Prometheus Summary metrics | Client-side quantiles, can't aggregate across instances. Not the Prometheus best practice. | Broken aggregation in multi-instance setups |
| 2 | Separate REGISTRY for histograms | Adds complexity, no benefit. Custom REGISTRY already isolates from global. | Unnecessary indirection, confusing maintenance |
| 3 | No model label on histograms | Per-model distribution is the primary use case. Without it, you can only see aggregate distribution across all models mixed together. | Loss of primary use case |
| 4 | Per-session histogram labels | Unbounded cardinality (session IDs). Would overwhelm Prometheus. Aggregate + per-model is sufficient. | Cardinality explosion |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | `prometheus_client.Histogram.observe()` is thread-safe | Validated — documented as thread-safe in prometheus_client source | Would need external locking (increases complexity) |
| 2 | Bucket boundaries cover real-world TPS/latency ranges | Unknown — based on typical LLM inference ranges (1-1000 tok/s, 0.1-60s) | Would need bucket adjustment (non-breaking metric change) |
| 3 | Cardinality cap on model labels is sufficient | Validated — same cap already works for gauges | Would need per-metric cap config |
| 4 | Existing tests won't break from new metric objects | Validated — new metrics don't modify existing ones | Would need test fixture updates |
