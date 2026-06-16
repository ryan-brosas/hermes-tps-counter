---
purpose: Wave-sequenced implementation plan
updated: 2026-06-16
---

# Plan: her-feat-prometheus-histogram-metrics-z5z

**Goal:** Add two Prometheus Histogram metrics (TPS distribution and API call latency) with model labels to enable p50/p95/p99 percentile analysis via `histogram_quantile()`.

## Graph Context

- **Blast radius:** `prometheus_metrics.py` (metric definitions + helpers), `__init__.py` (observation recording), `tests/test_prometheus.py` (new test class), `README.md` (documentation)
- **Unblocks:** Future Grafana dashboard work, percentile-based SLO alerting, provider-labeled histogram follow-up
- **Blocked by:** None (operational health metrics bead is already shipped)
- **Critical path:** No — additive feature, no existing functionality depends on it
- **Forecast:** ~90 minutes (3 waves, 6 tasks)

## Observable Truths

What must be TRUE for the goal to be achieved:

1. `curl localhost:PORT/metrics | grep tps_distribution` returns histogram metric lines with bucket boundaries [1, 5, 10, 25, 50, 100, 250, 500, 1000]
2. `curl localhost:PORT/metrics | grep api_call_latency_seconds` returns histogram metric lines with bucket boundaries [0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60]
3. After 2+ simulated hook calls, histogram `_count` values are ≥ 2 and `_bucket` values show distribution
4. `pytest tests/test_prometheus.py` — all existing tests pass alongside new histogram tests
5. With `_PROMETHEUS_AVAILABLE = False`, `observe_tps()` and `observe_latency()` are silent no-ops

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Histogram metric objects | `_tps_distribution`, `_api_call_latency_seconds` globals | `prometheus_metrics.py` | Need |
| Helper functions | `observe_tps()`, `observe_latency()` | `prometheus_metrics.py` | Need |
| Hook integration | Observation calls in `_on_post_api_request` | `__init__.py` | Need |
| Histogram tests | Test class for registration, observation, output | `tests/test_prometheus.py` | Need |
| README docs | Metric documentation | `README.md` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | Add Histogram imports, globals, `_init_metrics()` creation, helper functions | no | None — pure `prometheus_metrics.py` changes | `python -c "from prometheus_metrics import observe_tps, observe_latency"` |
| 2 | Wire observations into `_on_post_api_request` | no | Wave 1 complete — helpers exist | `pytest tests/test_prometheus.py -k histogram -v` |
| 3 | Add histogram tests + README docs | yes (parallel) | Wave 2 complete — integration works | `pytest tests/test_prometheus.py -v` (all tests) |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
# Run all Prometheus tests (existing + new)
pytest tests/test_prometheus.py -v
# Verify histogram metrics appear in output
python -c "
from prometheus_metrics import observe_tps, observe_latency, generate_metrics, reset_metrics
reset_metrics()
observe_tps(50.0, 'openai/gpt-4o')
observe_tps(150.0, 'openai/gpt-4o')
observe_latency(1.5, 'openai/gpt-4o')
observe_latency(0.3, 'anthropic/claude-3')
output = generate_metrics().decode()
assert 'tps_distribution' in output, 'tps_distribution missing'
assert 'api_call_latency_seconds' in output, 'api_call_latency_seconds missing'
assert 'model=' in output, 'model label missing'
print('All histogram checks passed')
"
```
