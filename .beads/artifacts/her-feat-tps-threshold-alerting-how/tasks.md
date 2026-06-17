---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-feat-tps-threshold-alerting-how

## Task Metadata

```yaml
bead_id: "her-feat-tps-threshold-alerting-how"
total_tasks: 6
waves: 3
parallelizable: 2
estimated_minutes: 85
```

## 1. Core Alert Engine

### 1.1 Threshold config + rolling window + state machine + hook emission

```yaml
depends_on: []
parallel: false
files: ["__init__.py"]
estimated_minutes: 45
```

- [ ] Add `_ALERT_DEFAULTS` dict: `TPS_THRESHOLD` (None=auto), `TPS_EVAL_WINDOW` (5), `TPS_COLD_START_CALLS` (10), `TPS_COLD_START_FACTOR` (0.5)
- [ ] Extend `_SessionTPS` dataclass with fields: `alert_state` (str, default "idle"), `alert_threshold` (Optional[float]), `alert_fired_at` (Optional[float]), `alert_resolved_at` (Optional[float]), `cold_start_samples` (list[float])
- [ ] Read config from env vars `TPS_THRESHOLD` and `TPS_EVAL_WINDOW` in `register()`; store as module-level `_ALERT_CONFIG` dict
- [ ] Register `tps_alert` hook in `register()` via `ctx.register_hook("tps_alert", lambda *a: None)` (no-op default so emission doesn't error if nobody subscribes)
- [ ] Implement `_evaluate_alert(session_id, session_state)`:
  - If `alert_threshold` is None and `len(cold_start_samples) < TPS_COLD_START_CALLS`: append current TPS, return (no evaluation yet)
  - If `alert_threshold` is None and `len(cold_start_samples) >= TPS_COLD_START_CALLS`: compute baseline = mean(cold_start_samples), set `alert_threshold = baseline * TPS_COLD_START_FACTOR`, log at INFO
  - Compute `rolling_avg = mean(last TPS_EVAL_WINDOW samples)`
  - If `rolling_avg < alert_threshold` and `alert_state != "firing"`: set state="firing", record `alert_fired_at`, fire `tps_alert` hook
  - If `rolling_avg >= alert_threshold` and `alert_state == "firing"`: set state="resolved", record `alert_resolved_at`, fire `tps_alert` hook
  - Hook payload: `{"session_id": ..., "state": ..., "tps": rolling_avg, "threshold": alert_threshold, "timestamp": time.time()}`
- [ ] Call `_evaluate_alert()` at the end of `_on_post_api_request`, after TPS is recorded, inside existing `with _STATE_LOCK:` block
- [ ] Ensure `agent._tps_snapshot` dict includes `alert_state` and `alert_threshold` keys

### 1.2 Smoke test — manual verification

```yaml
depends_on: ["1.1"]
parallel: false
files: ["__init__.py"]
estimated_minutes: 5
```

- [ ] Run `python -c "import hermes_tps_counter"` to confirm no import errors
- [ ] Verify new fields exist on `_SessionTPS` by inspection

## 2. Status Bar + Tests

### 2.1 Status bar alert indicator

```yaml
depends_on: ["1.1"]
parallel: true
files: ["__init__.py"]
estimated_minutes: 10
```

- [ ] In `_build_status_snapshot()` (or wherever `_tps_snapshot` is populated), add `alert_indicator` field: `"⚠ TPS ALERT"` when `alert_state == "firing"`, else `""`
- [ ] Ensure indicator is visible in status bar output

### 2.2 Pytest tests for threshold alerting

```yaml
depends_on: ["1.1"]
parallel: true
files: ["tests/test_threshold_alerting.py"]
estimated_minutes: 20
```

- [ ] Create `tests/test_threshold_alerting.py`
- [ ] Test: `test_threshold_crossing_fires_alert` — simulate API calls with degrading TPS below threshold, assert `tps_alert` hook called with `state="firing"`
- [ ] Test: `test_tps_recovery_resolves_alert` — simulate recovery above threshold, assert hook called with `state="resolved"`
- [ ] Test: `test_cold_start_auto_threshold` — first 10 calls establish baseline, threshold = baseline * 0.5
- [ ] Test: `test_custom_threshold_env_var` — set `TPS_THRESHOLD=50`, verify it overrides auto-calculation
- [ ] Test: `test_rolling_window_size` — verify only last N calls are evaluated (not all history)
- [ ] Test: `test_no_alert_during_cold_start` — no alert fires during first 10 calls
- [ ] Test: `test_thread_safety_concurrent_sessions` — multiple sessions evaluated concurrently without corruption
- [ ] Follow patterns from `tests/test_hook.py` for fixtures and mocking

## 3. Documentation + Verification

### 3.1 README documentation

```yaml
depends_on: ["2.1", "2.2"]
parallel: false
files: ["README.md"]
estimated_minutes: 5
```

- [ ] Add "Threshold Alerting" section to README
- [ ] Document `TPS_THRESHOLD` and `TPS_EVAL_WINDOW` env vars
- [ ] Document `tps_alert` hook contract (payload shape, states)
- [ ] Document cold-start auto-threshold behavior

### 3.2 Full verification

```yaml
depends_on: ["2.1", "2.2", "3.1"]
parallel: false
estimated_minutes: 5
```

- [ ] `pytest tests/test_threshold_alerting.py -v` — all new tests pass
- [ ] `pytest tests/ -v` — no regressions in existing tests
- [ ] Verify no background threads added
- [ ] Verify `_STATE_LOCK` used for all alert state mutations
