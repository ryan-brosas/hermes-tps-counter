# Plan: Per-Model TPS Tracking

## Wave 1 — Core (sequential, single file)

### Task 1.1: Add _ModelTPS class
- **File:** `__init__.py`
- **Action:** Add `_ModelTPS` class mirroring `_SessionTPS` with: avg_tps, peak_tps, call_count, total_output_tokens, total_duration. Add `record(output_tokens, duration)` method.
- **Verification:** `python -c "from __init__ import _ModelTPS; m = _ModelTPS(); m.record(100, 1.0); print(m.avg_tps)"`
- **Parallel:** No
- **Depends on:** None

### Task 1.2: Add per-model state tracking
- **File:** `__init__.py`
- **Action:** Add `_MODELS` dict (session_id → model_name → _ModelTPS). Add `_get_model(session_id, model)` helper. Guard with `_STATE_LOCK`.
- **Verification:** Helper returns same instance for same inputs
- **Parallel:** No
- **Depends on:** Task 1.1

### Task 1.3: Hook model extraction
- **File:** `__init__.py`
- **Action:** In `_on_post_api_request`, after session record, extract model from `kwargs.get("model", "")`, update model stats. Include in `_tps_snapshot["models"]`.
- **Verification:** Hook updates model stats on API call
- **Parallel:** No
- **Depends on:** Task 1.2

### Task 1.4: Add public API
- **File:** `__init__.py`
- **Action:** Add `get_model_stats(session_id)` returning model_name → {avg_tps, peak_tps, calls, total_output_tokens, total_duration}.
- **Verification:** `get_model_stats` returns expected keys
- **Parallel:** No
- **Depends on:** Task 1.3

## Wave 2 — Cleanup & Docs (parallel)

### Task 2.1: Update cleanup hooks
- **File:** `__init__.py`
- **Action:** Clean up `_MODELS[session_id]` in `_cleanup_session`.
- **Verification:** Evicted session's model data removed
- **Parallel:** Yes
- **Depends on:** Task 1.4

### Task 2.2: Update README
- **File:** `README.md`
- **Action:** Add per-model tracking to API docs.
- **Verification:** README reflects new API
- **Parallel:** Yes
- **Depends on:** Task 1.4

## Dependencies
```
1.1 → 1.2 → 1.3 → 1.4 → 2.1 + 2.2 (parallel)
```
