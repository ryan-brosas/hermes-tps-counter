---
purpose: Task decomposition with dependency tracking
updated: 2026-06-16
---

# Tasks: her-prometheus-metrics-exporter-17t

## 1. Core Metrics Module (Wave 1)

### 1.1 Create prometheus_metrics.py

```yaml
depends_on: []
parallel: false
files: ["prometheus_metrics.py"]
estimated_minutes: 20
```

- [ ] Create `prometheus_metrics.py` with try/except import of `prometheus_client`
- [ ] Define custom `CollectorRegistry` instance (not global default)
- [ ] Define module-level `_PROMETHEUS_AVAILABLE` boolean
- [ ] Define gauge metrics with `session_id` label:
  - `tps_last_call` — last call TPS value
  - `tps_avg` — rolling average TPS
  - `tps_peak` — peak TPS
- [ ] Define counter metrics:
  - `tps_tokens_total` — labels: `session_id`, `direction` (input/output)
  - `tps_api_calls_total` — label: `session_id`
- [ ] Define per-model gauge metrics with `session_id` + `model` labels:
  - `tps_model_avg` — per-model average TPS
  - `tps_model_peak` — per-model peak TPS
- [ ] Define per-provider gauge metrics with `session_id` + `provider` labels:
  - `tps_provider_avg` — per-provider average TPS
  - `tps_provider_peak` — per-provider peak TPS
- [ ] Implement `update_metrics(session_id, state, models, providers)` function:
  - Sets gauge values from state dict
  - Increments counters for new tokens/calls
  - Updates per-model and per-provider gauges
  - Thread-safe (prometheus_client gauges are thread-safe internally)
  - No-op if `_PROMETHEUS_AVAILABLE` is False
- [ ] Implement `generate_metrics()` function returning bytes from registry
- [ ] Implement `metrics_available()` function returning `_PROMETHEUS_AVAILABLE`
- [ ] Add `# HELP` and `# TYPE` comments via prometheus_client auto-generation

**Verification:** `python -c "from prometheus_metrics import REGISTRY, update_metrics, generate_metrics; print('OK')"` succeeds even without prometheus_client installed (returns empty bytes).

## 2. Hook Integration (Wave 2)

### 2.1 Wire metrics into _on_post_api_request

```yaml
depends_on: ["1.1"]
parallel: true
files: ["__init__.py"]
estimated_minutes: 15
```

- [ ] Import `update_metrics` from `prometheus_metrics` at top of `__init__.py`
- [ ] Inside `_on_post_api_request`, after `_persist_state()` call, add:
  ```python
  try:
      from prometheus_metrics import update_metrics
      session_models = _MODELS.get(session_id, {})
      session_providers = _PROVIDERS.get(session_id, {})
      update_metrics(session_id, state, session_models, session_providers)
  except Exception:
      pass
  ```
- [ ] Ensure this is inside the existing `_STATE_LOCK` block (after model/provider recording)
- [ ] Guard with `_prometheus_enabled` module-level flag (set in register())

**Verification:** `pytest tests/test_prometheus.py::TestHookIntegration -v` passes.

### 2.2 Add /metrics endpoint to FastAPI app

```yaml
depends_on: ["1.1"]
parallel: true
files: ["api.py"]
estimated_minutes: 10
```

- [ ] Import `generate_metrics` and `metrics_available` from `prometheus_metrics`
- [ ] Add `GET /metrics` route to `create_app()`:
  ```python
  @app.get("/metrics")
  def metrics():
      if not metrics_available():
          raise HTTPException(503, "prometheus_client not installed")
      return Response(
          content=generate_metrics(),
          media_type="text/plain; version=0.0.4; charset=utf-8",
      )
  ```
- [ ] Import `Response` from `starlette.responses` (or `fastapi.responses`)
- [ ] Handle edge case: registry has no metrics registered yet (returns empty but valid response)

**Verification:** `pytest tests/test_prometheus.py::TestMetricsEndpoint -v` passes.

## 3. Config Integration (Wave 3)

### 3.1 Add prometheus config to register()

```yaml
depends_on: ["2.1", "2.2"]
parallel: false
files: ["__init__.py"]
estimated_minutes: 10
```

- [ ] In `register()`, read `prometheus.enabled` from plugin config (default: `False`)
- [ ] Set module-level `_prometheus_enabled` flag
- [ ] If enabled and `prometheus_client` is available, log info message
- [ ] If enabled but `prometheus_client` not available, log warning
- [ ] If disabled, skip metric registration entirely (no-op)

**Verification:** `pytest tests/test_prometheus.py::TestConfigIntegration -v` passes.

## 4. Tests (Wave 2-3, parallel with implementation)

### 4.1 Create tests/test_prometheus.py

```yaml
depends_on: ["1.1"]
parallel: true
files: ["tests/test_prometheus.py"]
estimated_minutes: 20
```

- [ ] Test metric definitions exist and have correct names/labels
- [ ] Test `update_metrics()` sets gauge values correctly
- [ ] Test `update_metrics()` increments counters correctly
- [ ] Test per-model and per-provider metrics are updated
- [ ] Test `generate_metrics()` returns bytes with HELP/TYPE lines
- [ ] Test `/metrics` endpoint returns 200 with correct content-type
- [ ] Test `/metrics` returns 503 when prometheus_client unavailable
- [ ] Test graceful degradation: plugin works when prometheus_client not installed
- [ ] Test thread-safety: concurrent `update_metrics()` calls don't corrupt state
- [ ] Test metric values after simulating 2+ hook calls
- [ ] All tests use `mock_hermes_cli` autouse fixture (from existing pattern)
- [ ] Tests clean up global state in fixtures (reset registry between tests)

**Verification:** `pytest tests/test_prometheus.py -v` — all green.

## Cross-Cutting

### 5.1 Backward Compatibility

```yaml
depends_on: ["2.1", "2.2", "3.1"]
parallel: false
files: []
estimated_minutes: 5
```

- [ ] Run full test suite: `pytest tests/ -v` — 0 failures
- [ ] Verify existing test files unchanged (test_api.py, test_persistence.py, test_provider_tps.py, test_store_delete.py, test_usage_parsing.py)
- [ ] Verify plugin loads without prometheus_client (graceful degradation)
