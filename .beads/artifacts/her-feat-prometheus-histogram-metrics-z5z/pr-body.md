## Summary

Adds Prometheus histogram metrics for TPS throughput and API latency so operators can analyze p50/p95/p99 distributions in Grafana/Prometheus instead of relying only on instantaneous gauge values.

## What Changed

- Added `tps_distribution` histogram with model labels and TPS buckets `[1, 5, 10, 25, 50, 100, 250, 500, 1000]`.
- Added `api_call_latency_seconds` histogram with model labels and latency buckets `[0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60]`.
- Added `observe_tps()` and `observe_latency()` helpers with graceful no-op behavior when Prometheus is unavailable.
- Wired histogram observations into `_on_post_api_request()`.
- Added bounded histogram model label admission to protect Prometheus cardinality.
- Added histogram tests and README documentation with PromQL percentile examples.

## Acceptance Criteria

- [x] `tps_distribution` histogram registered with correct buckets and `model` label — verified by `TestMetricDefinitions::test_histograms_registered` and histogram smoke script.
- [x] `api_call_latency_seconds` histogram registered with correct buckets and `model` label — verified by `TestMetricDefinitions::test_histograms_registered` and histogram smoke script.
- [x] Histograms use custom `REGISTRY` — verified via `REGISTRY.get_sample_value()` assertions.
- [x] Hook records observations — verified by `TestHistogramMetrics::test_hook_records_histogram_observations`.
- [x] Graceful degradation — verified by `TestGracefulDegradation::test_no_prometheus_module_still_works`.
- [x] Helper functions exist and are callable — exercised by tests and smoke script.
- [x] HELP/TYPE metadata appears in output — verified by `TestHistogramMetrics::test_histogram_output_contains_help_type_and_buckets`.
- [x] Backward compatibility — `pytest tests/ -x` passed with 294 tests.

## Review

**Verdict:** APPROVE  
**Findings:** 0 critical, 0 high, 0 medium, 0 low

## Changed Files

This PR is on a stacked feature branch; `git diff origin/main...HEAD --stat` reports 111 files changed across the current branch stack. The bead-scoped code/docs changes are:

| File | Purpose |
|---|---|
| `prometheus_metrics.py` | Histogram metrics, helper functions, cardinality cap |
| `__init__.py` | Hook integration for histogram observations |
| `tests/test_prometheus.py` | Histogram registration, observation, output, hook, degradation tests |
| `README.md` | Histogram documentation and PromQL examples |
| `.beads/artifacts/her-feat-prometheus-histogram-metrics-z5z/*` | Bead artifacts, evidence, review |
| `.beads/issues.jsonl` | Bead claim/close state |

## Verification

- `pytest tests/test_prometheus.py -k histogram -v` → 5 passed
- `pytest tests/test_prometheus.py -v` → 42 passed
- `pytest tests/ -x` → 294 passed
- Histogram smoke script → `All histogram checks passed`
- `git diff --check` → clean

## Artifacts

- PRD: `.beads/artifacts/her-feat-prometheus-histogram-metrics-z5z/prd.md`
- Plan: `.beads/artifacts/her-feat-prometheus-histogram-metrics-z5z/plan.md`
- Evidence: `.beads/artifacts/her-feat-prometheus-histogram-metrics-z5z/completion-evidence.json`
- Review: `.beads/artifacts/her-feat-prometheus-histogram-metrics-z5z/review-report.md`

## Br Bead

- Bead: `her-feat-prometheus-histogram-metrics-z5z`
- Status: closed
- Priority: 2
