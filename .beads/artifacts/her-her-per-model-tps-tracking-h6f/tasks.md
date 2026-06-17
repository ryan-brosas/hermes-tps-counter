# Tasks: her-her-per-model-tps-tracking-h6f

## Task 1: Add _ModelTPS class
**File:** `__init__.py`
**Action:** Add `_ModelTPS` class with avg_tps, peak_tps, call_count, total_output_tokens, total_duration. Add `record(output_tokens, duration)` method and computed properties.
**Verification:** `python -c "from __init__ import _ModelTPS; m = _ModelTPS(); m.record(100, 1.0); print(m.avg_tps)"`
**Parallel:** No
**Depends on:** None

## Task 2: Add per-model state tracking
**File:** `__init__.py`
**Action:** Add `_MODELS` dict (session_id → model_name → _ModelTPS). Add `_get_model(session_id, model)` helper. Guard with `_STATE_LOCK`.
**Verification:** Helper returns same instance for same inputs
**Parallel:** No
**Depends on:** Task 1

## Task 3: Hook model extraction
**File:** `__init__.py`
**Action:** In `_on_post_api_request`, extract model from `kwargs.get("model", "")`, update model stats. Include in `_tps_snapshot["models"]`.
**Verification:** Hook updates model stats on API call
**Parallel:** No
**Depends on:** Task 2

## Task 4: Add public API
**File:** `__init__.py`
**Action:** Add `get_model_stats(session_id)` returning model_name → {avg_tps, peak_tps, calls, total_output_tokens, total_duration}.
**Verification:** `get_model_stats` returns expected keys
**Parallel:** No
**Depends on:** Task 3

## Task 5: Update cleanup hooks
**File:** `__init__.py`
**Action:** Clean up `_MODELS[session_id]` in `_cleanup_session`.
**Verification:** Evicted session's model data removed
**Parallel:** Yes
**Depends on:** Task 4

## Task 6: Update README
**File:** `README.md`
**Action:** Add per-model tracking to API docs.
**Verification:** README reflects new API
**Parallel:** Yes
**Depends on:** Task 4
