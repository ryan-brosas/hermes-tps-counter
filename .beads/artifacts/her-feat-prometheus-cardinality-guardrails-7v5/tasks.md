---
purpose: Task decomposition with dependency tracking
updated: 2026-06-16
---

# Tasks: her-feat-prometheus-cardinality-guardrails-7v5

## Task Metadata

```yaml
id: "1.1"
depends_on: []
parallel: true
conflicts_with: []
files: ["prometheus_metrics.py"]
estimated_minutes: 20
```

## 1. Foundation

### 1.1 Add aggregate (session-free) gauges and counters to prometheus_metrics.py

```yaml
depends_on: []
parallel: true
files: ["prometheus_metrics.py"]
```

- [ ] Define new aggregate gauge objects: `tps_last_call_aggregate`, `tps_avg_aggregate`, `tps_peak_aggregate` — no labels, singleton values representing the most-recent-session update.
- [ ] Define new aggregate counters: `tps_tokens_total_aggregate` (direction label only), `tps_api_calls_total_aggregate` — no session_id.
- [ ] Update `_init_metrics()` to create these alongside existing session-labeled metrics.
- [ ] Update `update_metrics()` to set aggregate gauges (overwrite with latest session's values) and inc aggregate counters.
- [ ] Ensure aggregate metrics appear in `generate_metrics()` output.

### 1.2 Add `prometheus_legacy_session_labels` config knob to config.py

```yaml
depends_on: []
parallel: true
files: ["config.py"]
```

- [ ] Add `prometheus_legacy_session_labels: bool = False` field to `TPSConfig`.
- [ ] Add `PROMETHEUS_LEGACY_SESSION_LABELS` to `_ENV_FIELD_MAP`.
- [ ] Add TOML parsing for `prometheus.legacy_session_labels` nested key.
- [ ] Add ctx override support for the new field.

## 2. Core Implementation

### 2.1 Gate session-labeled metrics behind the config flag

```yaml
depends_on: ["1.1", "1.2"]
parallel: true
files: ["prometheus_metrics.py", "__init__.py"]
```

- [ ] Modify `prometheus_metrics.py` `_init_metrics()` to conditionally create session-labeled gauges/counters only when legacy flag is True.
- [ ] Modify `update_metrics()` to skip session-labeled updates when legacy flag is False.
- [ ] Accept config parameter in `_init_metrics()` or add a `configure()` function to pass the legacy flag.
- [ ] Update `__init__.py` to pass config to `prometheus_metrics` at registration time.

### 2.2 Bound model/provider label cardinality

```yaml
depends_on: ["1.1"]
parallel: true
files: ["prometheus_metrics.py"]
```

- [ ] Add a bounded label set for model and provider: keep a module-level `set` of seen model/provider names, capped at a configurable max (default 50).
- [ ] When a new model/provider exceeds the cap, route to an `_overflow` aggregate instead of creating a new labelset.
- [ ] Update `update_metrics()` to check membership before `.labels()` call.
- [ ] Add `_tps_model_avg_overflow`, `_tps_model_peak_overflow` (and provider equivalents) aggregate gauges for overflow values.

## 3. Testing

### 3.1 Add regression tests for bounded cardinality

```yaml
depends_on: ["2.1", "2.2"]
parallel: true
files: ["tests/test_prometheus.py"]
```

- [ ] Test: calling `update_metrics()` with 100 distinct session_ids produces a bounded number of series (no per-session explosion).
- [ ] Test: aggregate gauges exist and reflect the latest session's values.
- [ ] Test: with `legacy_session_labels=True`, session-labeled metrics reappear.
- [ ] Test: exceeding model cap routes to overflow aggregate, not new labelset.
- [ ] Test: `prometheus_client` absence still works (no regression on graceful degradation).

## 4. Documentation

### 4.1 Document cardinality model in README.md

```yaml
depends_on: ["2.1"]
parallel: true
files: ["README.md"]
```

- [ ] Add "Prometheus Cardinality" section explaining aggregate-first design.
- [ ] Document `prometheus_legacy_session_labels` config knob (env, TOML, ctx).
- [ ] Explain why session_id is not a label by default (unbounded cardinality).
- [ ] Note that per-session detail remains available via REST/WebSocket/SQLite.

## 5. Verification

### 5.1 All tests pass

```yaml
depends_on: ["3.1"]
parallel: false
```

- [ ] `cd /home/ryan/repos/hermes-tps-counter && python -m pytest tests/test_prometheus.py -v`
