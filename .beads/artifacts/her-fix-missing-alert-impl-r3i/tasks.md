---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-fix-missing-alert-impl-r3i

## Task Metadata

```yaml
id: "1.1"
depends_on: []
parallel: false
conflicts_with: []
files: ["__init__.py"]
estimated_minutes: 5
```

## 1. Core Alert Infrastructure (Wave 1)

### 1.1 Add `_ALERT_CONFIG` and `_ALERT_HOOK_MANAGER` globals

```yaml
depends_on: []
parallel: false
files: ["__init__.py"]
```

- [ ] Add `_ALERT_CONFIG: Dict[str, Any]` dict after existing globals (~line 95)
  - `threshold`: None (None means auto-calculate from cold-start baseline)
  - `eval_window`: 5 (last N calls evaluated for alert)
  - `cold_start_calls`: 10 (first N calls establish baseline)
  - `cold_start_factor`: 0.5 (threshold = baseline_mean × factor)
- [ ] Add `_ALERT_HOOK_MANAGER: Optional[Any] = None` global

### 1.2 Extend `_SessionTPS.__slots__` and `__init__` with alert fields

```yaml
depends_on: ["1.1"]
parallel: false
files: ["__init__.py"]
```

- [ ] Add 6 fields to `_SessionTPS.__slots__` tuple:
  - `alert_state` (str: idle/firing/resolved)
  - `alert_threshold` (float: TPS threshold for alerting)
  - `alert_fired_at` (float/None: timestamp when alert fired)
  - `alert_resolved_at` (float/None: timestamp when alert resolved)
  - `cold_start_samples` (list[float]: TPS values during cold start)
  - `recent_tps_samples` (list[float]: last N TPS values for rolling window)
- [ ] Initialize each in `__init__`:
  - `alert_state = "idle"`
  - `alert_threshold = 0.0`
  - `alert_fired_at = None`
  - `alert_resolved_at = None`
  - `cold_start_samples = []`
  - `recent_tps_samples = []`

### 1.3 Implement `_evaluate_alert(state: _SessionTPS, tps: float) -> None`

```yaml
depends_on: ["1.2"]
parallel: false
files: ["__init__.py"]
```

- [ ] Implement cold-start phase:
  - If `_ALERT_CONFIG["threshold"]` is None AND `len(state.cold_start_samples) < _ALERT_CONFIG["cold_start_calls"]`:
    - Append `tps` to `state.cold_start_samples`
    - If cold start complete (reached N samples), calculate auto-threshold:
      `mean(cold_start_samples) * cold_start_factor`
    - Return (no evaluation during cold start)
- [ ] Implement fixed-threshold path:
  - If `_ALERT_CONFIG["threshold"]` is not None, set `state.alert_threshold = _ALERT_CONFIG["threshold"]`
- [ ] Implement rolling window evaluation:
  - Append `tps` to `state.recent_tps_samples`
  - Trim to last `_ALERT_CONFIG["eval_window"]` entries
  - If threshold is set and window is full, compute rolling mean
- [ ] Implement state machine:
  - **idle → firing**: rolling mean < threshold AND previous state was idle
  - **firing**: rolling mean stays below threshold (no change)
  - **firing → resolved**: rolling mean >= threshold AND previous state was firing
  - **resolved**: rolling mean stays above threshold (no change)
  - **resolved → idle**: after some stabilization period (simplification: resolved → idle on next call, or keep resolved)
  - Set `alert_fired_at` / `alert_resolved_at` timestamps on transitions
  - Call `_emit_alert(state, session_id, tps)` on state transitions (firing, resolved)

### 1.4 Implement `_emit_alert(state: _SessionTPS, session_id: str, tps: float) -> None`

```yaml
depends_on: ["1.3"]
parallel: false
files: ["__init__.py"]
```

- [ ] Check `_ALERT_HOOK_MANAGER is not None`
- [ ] Build payload dict: `{session_id, state: alert_state, tps, threshold: alert_threshold, timestamp: time.time()}`
- [ ] Call `_ALERT_HOOK_MANAGER.invoke_hook("tps_alert", **payload)`
- [ ] Wrap in try/except with debug-level logging

## 2. Integration Points (Wave 2)

### 2.1 Integrate alert evaluation into `_on_post_api_request()`

```yaml
depends_on: ["1.4"]
parallel: false
files: ["__init__.py"]
```

- [ ] Inside `_STATE_LOCK` block, after `state.record(output_tokens, duration, input_tokens)`:
  - Calculate `tps = output_tokens / duration`
  - Call `_evaluate_alert(state, tps)` (pass session_id if needed for emit)
  - This must happen INSIDE the lock to maintain consistency with tests
- [ ] The session_id is already available as local variable `session_id`

### 2.2 Add alert fields to `agent._tps_snapshot`

```yaml
depends_on: ["1.4"]
parallel: false
files: ["__init__.py"]
```

- [ ] In the snapshot dict (~line 686), add:
  - `"alert_state": state.alert_state`
  - `"alert_threshold": state.alert_threshold`
  - `"alert_indicator": "⚠ TPS ALERT" if state.alert_state == "firing" else ""`
- [ ] These go INSIDE the existing `_STATE_LOCK` block that reads model/provider state

### 2.3 Add alert fields to `get_tps_stats()`

```yaml
depends_on: ["1.4"]
parallel: false
files: ["__init__.py"]
```

- [ ] In `get_tps_stats()` return dict, add:
  - `"alert_state": state.alert_state`
  - `"alert_threshold": state.alert_threshold`
- [ ] These fields are already inside the `_STATE_LOCK` block
- [ ] Also add to the "no session" fallback dict: `"alert_state": "idle", "alert_threshold": 0.0`

## 3. Plugin Registration (Wave 3)

### 3.1 Update `register()` for env vars and tps_alert hook

```yaml
depends_on: ["1.1"]
parallel: false
files: ["__init__.py"]
```

- [ ] At top of `register()`, read env vars:
  - `TPS_THRESHOLD` → parse as float, set `_ALERT_CONFIG["threshold"]`
  - `TPS_EVAL_WINDOW` → parse as int, set `_ALERT_CONFIG["eval_window"]`
- [ ] Register `tps_alert` hook: `ctx.register_hook("tps_alert", _on_tps_alert)` (stub — actual handler is the hook manager, but the hook name must be registered)
- [ ] Capture plugin manager reference: set `globals()["_ALERT_HOOK_MANAGER"]` from whatever ctx provides for hook invocation
- [ ] Note: `ctx` may have a `.plugin_manager` or similar attribute. Check existing patterns for how hooks are invoked. The test uses `manager.invoke_hook("tps_alert", **payload)` pattern — the manager is the mock plugged in via patching `_ALERT_HOOK_MANAGER`.
- [ ] Set `_ALERT_HOOK_MANAGER` from `getattr(ctx, 'plugin_manager', None)` or the ctx object itself if it acts as the hook manager

### 3.2 Verify `test_api.py::TestRegister::test_register_calls_ctx_register_hook` passes

```yaml
depends_on: ["3.1"]
parallel: false
files: ["tests/test_api.py"]
```

- [ ] Run `python -m pytest tests/test_api.py::TestRegister -v`
- [ ] If the register test expects `tps_alert` in hook_names, registration must add it
- [ ] The test currently expects: `assert "tps_alert" in hook_names` where hook_names are from `ctx.register_hook.call_args_list`

## 4. Verification (Wave 4)

### 4.1 All 19 threshold alerting tests pass

```yaml
depends_on: ["2.1", "2.2", "2.3", "3.1"]
parallel: false
```

- [ ] `python -m pytest tests/test_threshold_alerting.py -v`
- [ ] Expected: 19 passed, 0 failed, 0 errors

### 4.2 No regressions in other tests

```yaml
depends_on: ["4.1"]
parallel: false
```

- [ ] `python -m pytest tests/ -q --tb=short`
- [ ] Count pass/fail before and after. No new failures introduced.
- [ ] At minimum: check `test_api.py`, `test_prometheus.py`, and any other test files
- [ ] If pre-existing failures exist, document them separately from regressions
