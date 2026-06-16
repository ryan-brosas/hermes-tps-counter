# Tasks: her-feat-prometheus-histogram-metrics-z5z

## Wave 1 — Metrics definitions and helpers

- [x] Import `Histogram` from `prometheus_client` when available.
- [x] Add `_tps_distribution` and `_api_call_latency_seconds` globals.
- [x] Register histograms in `_init_metrics()` on the custom `REGISTRY`.
- [x] Add `observe_tps(value, model)` and `observe_latency(seconds, model)` helpers.
- [x] Add bounded model label admission for histogram labels.

## Wave 2 — Hook integration

- [x] Compute per-call TPS in `_on_post_api_request()`.
- [x] Call histogram observation helpers when Prometheus is enabled.
- [x] Preserve no-op behavior when Prometheus is disabled or unavailable.

## Wave 3 — Tests and documentation

- [x] Add histogram registration tests.
- [x] Add observation/sample tests via `REGISTRY.get_sample_value()`.
- [x] Add `/metrics` output HELP/TYPE/bucket tests.
- [x] Add hook integration and cardinality cap tests.
- [x] Document histogram metrics and PromQL percentile examples in README.
