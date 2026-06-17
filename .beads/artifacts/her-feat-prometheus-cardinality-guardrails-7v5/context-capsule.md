---
purpose: Agent spawn context for a bead
updated: 2026-06-16
---

# Context Capsule: her-feat-prometheus-cardinality-guardrails-7v5

## Objective

Replace unbounded `session_id` Prometheus labels with aggregate-first metrics and bounded optional dimensions, so `/metrics` output has a fixed series count regardless of session count.

## Key Patterns

- `Optional dependency guard` — `prometheus_metrics.py` lines 19-24: `_PROMETHEUS_AVAILABLE` flag gates all metric creation. Any new metrics must follow this pattern. Reference: `prometheus_metrics.py`
- `Custom isolated registry` — `REGISTRY = CollectorRegistry()` on line 73 ensures no global prometheus_client collisions. All new metrics must use `registry=REGISTRY`. Reference: `prometheus_metrics.py`
- `Config merge precedence` — `config.py`: defaults < TOML < env < ctx. New boolean config follows same layered pattern. Reference: `config.py`
- `Health metric increment pattern` — Lines 267-325: stateless `increment_*()` functions with `_PROMETHEUS_AVAILABLE` guard. Follow this for any new standalone metric functions. Reference: `prometheus_metrics.py`
- `Test isolation via reset_metrics()` — Tests call `reset_metrics()` in autouse fixture. New tests must not break this contract. Reference: `tests/test_prometheus.py`

## Constraints

1. Do NOT add new unbounded labels to Prometheus metrics. The `session_id` label must be off by default.
2. Aggregate metrics MUST cover: last_call_tps, avg_tps, peak_tps, tokens_total (input/output), api_calls_total.
3. Model/provider labels MUST be bounded: either top-N, cap with overflow bucket, or aggregate-only.
4. `prometheus_client` remains optional — no hard import, no ImportError on missing package.
5. Existing health metrics (usage_extraction_failures, db_write_errors, etc.) are label-free and must not be modified.
6. Future histogram work (her-feat-prometheus-histogram-metrics-z5z) must follow the same bounded-label policy — do not add session_id to any new histogram.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Aggregate metrics | `prometheus_metrics.py` — add gauges/counters, update `_init_metrics`, `update_metrics`, `generate_metrics` | `__init__.py` — no changes until Task 2.1 |
| Config knob | `config.py` — add field, env mapping, TOML/ctx parsing | `prometheus_metrics.py` — no changes |
| Gate session labels | `prometheus_metrics.py` — conditional init/update; `__init__.py` — pass config | `config.py` — no changes |
| Bounded model/provider | `prometheus_metrics.py` — label cap, overflow gauges | `__init__.py` — no changes |
| Regression tests | `tests/test_prometheus.py` — new test classes | `prometheus_metrics.py` — no changes |
| README docs | `README.md` — new section only | `prometheus_metrics.py` — no changes |

## Graph Context

- **Blast radius:** 5 files (prometheus_metrics.py, __init__.py, config.py, tests/test_prometheus.py, README.md)
- **Related beads:** her-feat-prometheus-histogram-metrics-z5z (must follow same label policy)
- **File history:** No prior bead touches on these files (clean slate)
- **Blocked by:** None — fully independent, top of topological order
