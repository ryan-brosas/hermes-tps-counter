---
purpose: Product Requirements Document for a bead
updated: 2026-06-16
---

# PRD: Add Prometheus cardinality guardrails to avoid unbounded session_id time series

**Bead:** her-feat-prometheus-cardinality-guardrails-7v5 | **Type:** feature | **Priority:** P2
**Created:** 2026-06-16 | **Estimate:** 75 minutes

## Problem

WHEN the TPS plugin exports Prometheus metrics for every session/model/provider combination THEN long-running Hermes installations can accumulate unbounded time series BECAUSE `prometheus_metrics.py` currently uses `session_id` labels on gauges/counters and combines `session_id` with `model`/`provider` labels for per-dimension metrics.

**Who is affected?** Hermes operators who enable `/metrics`, Grafana/Prometheus users scraping the plugin, and maintainers who need observability without hidden resource growth.
**Why now?** The graph shows observability/prometheus/metrics labels need attention, with one remaining open Prometheus histogram bead. External Prometheus guidance explicitly warns that every unique labelset creates a time series and that high-cardinality labels such as unbounded IDs should be avoided. Addressing this now prevents new histogram/observability work from extending the same cardinality pattern.

## Scope

### In Scope
- Define a bounded Prometheus labeling strategy for TPS metrics.
- Add guardrails around `session_id`, `model`, and `provider` label cardinality.
- Preserve graceful degradation when `prometheus_client` is absent.
- Preserve useful aggregate metrics suitable for dashboards and alerting.
- Document the cardinality model and any compatibility/configuration behavior.
- Add regression coverage for bounded-cardinality behavior and `/metrics` output.

### Out of Scope
- Implementing histogram quantiles/p50/p95/p99; that is already covered by `her-feat-prometheus-histogram-metrics-z5z` and must not be duplicated here.
- Reworking REST API or WebSocket response schemas.
- Changing SQLite persistence schema unless strictly required for metrics aggregation.
- Creating dashboards, alerts, PRs, commits, or releases.

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Replace or gate unbounded `session_id` label usage in Prometheus metrics | MUST | A new implementation path avoids unbounded `session_id` time series by default; if legacy session labels remain, they are explicitly capped or configurable and documented. |
| 2 | Preserve aggregate TPS observability | MUST | `/metrics` still exposes session-independent aggregate values for last/average/peak TPS, API calls, and token totals where applicable. |
| 3 | Bound model/provider label cardinality | MUST | Per-model/provider metrics either use bounded label admission, normalization, top-N/capping, or aggregate-only alternatives; unknown/overflow cases are handled deterministically. |
| 4 | Keep optional Prometheus dependency behavior | MUST | With `prometheus_client` missing, the plugin continues to import and run without failing. |
| 5 | Document cardinality behavior | SHOULD | README explains default behavior, any compatibility knobs, and why high-cardinality labels are avoided. |
| 6 | Add focused regression coverage | SHOULD | Tests cover multiple sessions/models/providers and assert that metrics output does not grow one unbounded series per unique session by default. |

## Technical Context

Relevant code and patterns:
- `prometheus_metrics.py`: defines custom `CollectorRegistry`, optional dependency guard, gauges/counters, and `update_metrics()` that currently labels metrics by `session_id`, `model`, and `provider`.
- `__init__.py`: calls metrics update from `_on_post_api_request` and maintains per-session, per-model, and per-provider state.
- `config.py`: existing typed configuration path for environment/TOML options if a compatibility flag or cap is needed.
- `api.py`: `/metrics` endpoint delegates to `prometheus_metrics.generate_metrics()` and returns Prometheus text exposition format.
- `tests/test_prometheus.py`: likely home for focused metrics-output regression tests.

Graph/research context:
- `bv --robot-triage`: only one open actionable bead, the existing Prometheus histogram work; this new bead must not continue or duplicate it.
- `bv --robot-suggest`: Prometheus work has label suggestions around `api`, `feature`, and `persistence`, indicating metrics/API hygiene remains active.
- `bv --robot-label-attention`: `metrics` and `feature` were top attention labels; `metrics` has open Prometheus work.
- Prometheus docs: every unique key-value labelset is a time series; high-cardinality dimensions such as unbounded IDs should not be labels. Instrumentation guidance recommends keeping most metrics label-free and investigating alternatives if cardinality can grow large.

## Approach

Adopt an aggregate-first Prometheus design with bounded optional dimensions. The default `/metrics` surface should be safe for continuous scraping: aggregate gauges/counters summarize all sessions, while detailed per-session data remains available through REST/WebSocket/store APIs instead of Prometheus labels. If backward-compatible session-labeled metrics are retained, they should be explicitly opt-in or capped with deterministic overflow handling.

**Alternatives considered:**
- Add histograms only: rejected because it duplicates an existing open bead and does not solve current high-cardinality labels.
- Keep all session labels and document the risk: rejected because it knowingly preserves an operational anti-pattern.
- Move all detailed analytics to Prometheus: rejected because the plugin already has REST, WebSocket, and SQLite paths better suited for high-cardinality/session-level detail.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing users may depend on session-labeled Prometheus series | Med | Med | Provide documented compatibility mode or migration notes; keep aggregate replacements clear. |
| Over-aggressive aggregation could remove useful dashboard detail | Med | Med | Retain bounded model/provider dimensions where safe; keep session detail via REST/WebSocket. |
| Config surface becomes too complex | Low | Med | Prefer safe defaults and minimal knobs: enable legacy labels, max label values, overflow bucket. |
| Interaction with future histogram bead could conflict | Med | Med | Specify that future histograms must follow the same bounded-label policy. |

## Tasks (for epics)

Not an epic.

## Success Criteria

- [ ] Default Prometheus metrics no longer create unbounded time series per unique session ID.
    - Verify: inspect `/metrics` output after multiple synthetic sessions and confirm bounded series count.
- [ ] Aggregate TPS/token/API metrics remain available in Prometheus text exposition format.
    - Verify: inspect generated metrics text for expected aggregate metric names and values.
- [ ] Model/provider labels are bounded, normalized, or intentionally omitted.
    - Verify: test many unique model/provider names and assert deterministic cap/overflow behavior or aggregate-only output.
- [ ] `prometheus_client` remains optional.
    - Verify: import/use code path in an environment without the dependency or via existing mock pattern.
- [ ] README documents cardinality-safe metrics behavior and compatibility notes.
- [ ] No implementation, planning, commit, PR, or close is part of this producer phase.
