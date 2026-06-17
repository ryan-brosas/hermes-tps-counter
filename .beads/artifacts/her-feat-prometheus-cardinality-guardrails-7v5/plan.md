---
purpose: Wave-sequenced implementation plan
updated: 2026-06-16
---

# Plan: her-feat-prometheus-cardinality-guardrails-7v5

**Goal:** Replace unbounded `session_id` Prometheus labels with aggregate-first metrics and bounded optional dimensions, eliminating time-series cardinality growth per session.

## Graph Context

- **Blast radius:** `prometheus_metrics.py`, `__init__.py`, `config.py`, `tests/test_prometheus.py`, `README.md`
- **Unblocks:** her-feat-prometheus-histogram-metrics-z5z (histogram bead must follow same bounded-label policy)
- **Blocked by:** None
- **Critical path:** No (slack=1, independent track)
- **Forecast:** 85 minutes estimated (confidence 0.35)

## Observable Truths

1. `/metrics` output after N synthetic sessions contains a FIXED number of time series (not N×per-session series) — aggregate gauges/counters exist without `session_id` labels.
2. Per-model and per-provider metrics either omit `session_id` or use bounded label admission with deterministic overflow handling.
3. With `prometheus_client` absent, the plugin imports and runs without error — no new hard dependency introduced.
4. Tests assert bounded series count: calling `update_metrics()` with 100 distinct session IDs does not produce 100× the series.
5. README documents cardinality-safe behavior and the `legacy_session_labels` compatibility knob.

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Aggregate gauges | Session-independent TPS observability | `prometheus_metrics.py` | Need |
| Bounded model/provider labels | Controlled cardinality dimensions | `prometheus_metrics.py` | Need |
| Config knob | `prometheus_legacy_session_labels` opt-in | `config.py` | Need |
| Callers updated | `__init__.py` passes aggregate state | `__init__.py` | Need |
| Regression tests | Bounded-cardinality assertions | `tests/test_prometheus.py` | Need |
| README section | Cardinality model documentation | `README.md` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | T1 (aggregate metrics), T2 (config knob) | Yes | None — both touch different files | `python -m pytest tests/test_prometheus.py -x` |
| 2 | T3 (update callers), T4 (bounded model/provider) | Yes | Wave 1 complete — aggregate metrics and config exist | `python -m pytest tests/test_prometheus.py -x` |
| 3 | T5 (regression tests), T6 (README docs) | Yes | Wave 2 complete — implementation stable | `python -m pytest tests/test_prometheus.py -x` |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
python -m pytest tests/test_prometheus.py -v
# Verify bounded series: run a test with 50 distinct sessions, confirm series count is constant
python -c "
from prometheus_metrics import reset_metrics, update_metrics, generate_metrics
reset_metrics()
class S:
    last_call_tps=1; avg_tps=1; peak_tps=1; call_count=1; last_call_output_tokens=10; last_call_input_tokens=5
for i in range(50):
    update_metrics(f'sess_{i}', S())
out = generate_metrics().decode()
lines = [l for l in out.split('\n') if l and not l.startswith('#')]
print(f'Total metric lines: {len(lines)}')
# Should be ~constant, not 50× session count
"
```
