# Plan: her-fix-missing-alert-impl-r3i

## Summary

Implement the TPS threshold alerting feature in `__init__.py` that was lost during merge of PR #28. The implementation follows the proven design from commit `acaf285` on branch `feat/her-feat-tps-threshold-alerting-how`, adapted to integrate cleanly with the current ~1150-line feature-rich `__init__.py`.

## Blast Radius

**Primary file:** `__init__.py` (~6 insertion points, ~90 lines added)
**Test verification:** `tests/test_threshold_alerting.py` (19 tests), `tests/test_api.py` (2 tests patched)
**No changes to:** `prometheus_metrics.py`, `api.py`, `store.py`, `config.py`, `dashboard.py`, `conftest.py`, other test files

## Wave Sequence

### Wave 1: Alert Infrastructure (additions only, no behavior change)

**Task 1.1:** Add `_ALERT_CONFIG` global dict
- **Where:** After line 80 (`MAX_SESSIONS = 50`) and before line 83 (`_STORE`)
- **What:** Dict with defaults: threshold=None, eval_window=5, cold_start_calls=10, cold_start_factor=0.5

**Task 1.2:** Add `_ALERT_HOOK_MANAGER` global
- **Where:** After `_ALERT_CONFIG` block
- **What:** `_ALERT_HOOK_MANAGER: Optional[Any] = None`

**Task 1.3:** Add alert slots to `_SessionTPS.__slots__`
- **Where:** In `class _SessionTPS`, after existing slots (after `"created_at"`)
- **What:** 6 new slots: alert_state, alert_threshold, alert_fired_at, alert_resolved_at, cold_start_samples, recent_tps_samples

**Task 1.4:** Add alert fields to `_SessionTPS.__init__`
- **Where:** After `self.created_at = time.time()` in `__init__`
- **What:** Initialize alert_state="idle", alert_threshold=None, alert_fired_at=None, alert_resolved_at=None, cold_start_samples=[], recent_tps_samples=[]

**Task 1.5:** Implement `_evaluate_alert()`
- **Where:** After `_get_session()` function (after line ~588), before `_get_model()`
- **What:** Cold-start auto-threshold (first N calls → baseline × factor), rolling window evaluation (last N calls), state machine (idle/firing/resolved)

**Task 1.6:** Implement `_emit_alert()`
- **Where:** After `_evaluate_alert()`
- **What:** Fire `tps_alert` hook via `_ALERT_HOOK_MANAGER.invoke_hook()` with {session_id, state, tps, threshold, timestamp}

### Wave 2: Hook Integration

**Task 2.1:** Integrate `_evaluate_alert()` into `_on_post_api_request()`
- **Where:** Inside the existing `with _STATE_LOCK:` block, after `state.record(...)` and persistence/model/provider updates
- **What:** Call `_evaluate_alert(session_id, state)` under the same lock

**Task 2.2:** Add alert fields to `agent._tps_snapshot`
- **Where:** In the status bar snapshot construction in `_on_post_api_request()`
- **What:** Add alert_state, alert_threshold, alert_indicator fields to snapshot dict

**Task 2.3:** Update `register()` for alert config and hook registration
- **Where:** At the start of `register()` (add global `_ALERT_HOOK_MANAGER`), read env vars, register `tps_alert` hook, capture manager
- **What:** Read TPS_THRESHOLD/TPS_EVAL_WINDOW env vars, register `tps_alert` no-op hook, set `_ALERT_HOOK_MANAGER = ctx._manager`

**Task 2.4:** Add alert fields to `get_tps_stats()`
- **Where:** In the return dict for existing session
- **What:** Add alert_state and alert_threshold keys

### Wave 3: Verify

**Task 3.1:** Run threshold alerting tests
```bash
python -m pytest tests/test_threshold_alerting.py -xvs
```

**Task 3.2:** Run full test suite
```bash
python -m pytest tests/ --tb=short
```

**Task 3.3:** Verify no regressions in existing features
- Status bar snapshot still works
- WebSocket broadcast still works
- Prometheus metrics still update
- Persistence still works
- Privacy redaction still works
- Model/provider tracking still works

## Implementation Strategy

The implementation follows the existing pattern:
- Thread-safe evaluation under `_STATE_LOCK`
- Private underscore-prefixed globals and functions
- Debug-level logging for non-critical operations
- Graceful degradation when optional components are unavailable
- No new imports needed (uses existing `os`, `threading`, `time`, `logging`)

## Estimated Effort

- Wave 1: 25 min
- Wave 2: 20 min
- Wave 3: 15 min
- Total: 60 min (matches `--estimate 60`)
