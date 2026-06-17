---
purpose: Decision log for a bead
updated: 2026-06-17
---

# Decisions: her-6od

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Create a new P2 feature bead for configurable call-event sampling. | This addresses a remaining operational scaling risk not covered by existing persistence, export, dashboard, health, privacy, Prometheus, rate-limiting, or batch-stats beads. | High |
| 2 | Scope sampling to historical `call_events` persistence only. | Core TPS aggregates are the plugin's primary value and must remain lossless even when historical rows are sampled. | High |
| 3 | Require default compatibility with complete event persistence. | Existing consumers and tests should not observe sampling unless it is explicitly configured. | High |
| 4 | Prefer deterministic/O(1) sampling decisions. | Determinism improves testability and avoids adding hook-path SQLite reads or hard-to-debug randomness. | Med |
| 5 | Require metadata that marks sampled history as potentially incomplete. | Dashboards and exports must not silently treat sampled event rows as a complete time series. | High |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Continue relying only on retention cleanup. | Retention controls storage age but does not reduce write amplification during bursts. | SQLite writes can still become a bottleneck in high-volume sessions. |
| 2 | Sample all stats, including session aggregates. | This would make `last_tps`, `avg_tps`, totals, and status-bar values inaccurate. | Core plugin correctness would be compromised. |
| 3 | Introduce an external queue, worker, or storage service. | The project convention favors stdlib/minimal dependencies and local plugin operation. | Operational complexity and dependency burden increase. |
| 4 | Implement sampling without metadata. | Consumers would misinterpret incomplete event history as complete. | Bad downstream analytics and hidden data quality issues. |
| 5 | Reopen/extend existing closed persistence or export beads. | Absolute rule says not to continue closed beads; this is a distinct operational feature. | Workflow violation and muddled bead ownership. |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | `call_events` persistence can be skipped independently from aggregate TPS updates. | Unknown until implementation inspects current hook/store wiring. | Plan may need a small seam/refactor before sampling can be inserted safely. |
| 2 | Existing config module can accept new sampling fields without architectural churn. | Unknown; closed config bead indicates typed defaults/env/TOML support exists. | Plan must account for config migration or naming constraints. |
| 3 | Export/API/contract surfaces already have a place for metadata. | Unknown; closed observability/export beads imply metadata surfaces exist. | Plan may need additive response fields with compatibility guidance. |
| 4 | Sampling should be opt-in. | Validated by backward-compatibility requirement. | If Ryan wants default sampling, priority and migration docs must change. |
