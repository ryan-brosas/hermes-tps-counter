# Plan: Session Lifecycle Cleanup and LRU Eviction

## Wave 1 — Core Implementation (sequential, single file)
All changes are in `__init__.py`. Must be done in order since they build on each other.

### Task 1: Add MAX_SESSIONS constant and created_at field
- Add `MAX_SESSIONS = 50` module-level constant
- Add `created_at` to `_SessionTPS.__slots__` and `__init__`
- Set `self.created_at = time.time()` in `__init__`
- **Files:** `__init__.py`
- **Estimate:** 5 min

### Task 2: Implement _cleanup_session and _evict_if_needed
- `_cleanup_session(session_id)`: remove from `_SESSIONS` under `_STATE_LOCK`
- `_evict_if_needed()`: if `len(_SESSIONS) > MAX_SESSIONS`, find session with oldest `turn_start_time`, call `_cleanup_session` on it
- Log eviction at debug level
- **Files:** `__init__.py`
- **Estimate:** 10 min

### Task 3: Wire eviction into _on_post_api_request
- After `state.record(...)`, call `_evict_if_needed()`
- **Files:** `__init__.py`
- **Estimate:** 3 min

### Task 4: Register on_session_end hook
- In `register()`, add `ctx.register_hook("on_session_end", _on_session_end)`
- `_on_session_end(**kwargs)`: extract `session_id` from kwargs, call `_cleanup_session(session_id)`
- Log cleanup at debug level
- **Files:** `__init__.py`
- **Estimate:** 5 min

### Task 5: Add session_duration to get_tps_stats
- Compute `time.time() - state.created_at` and return as `session_duration`
- **Files:** `__init__.py`
- **Estimate:** 3 min

## Wave 2 — Documentation and Manifest

### Task 6: Update plugin.yaml
- Add `on_session_end` to `provides_hooks` list
- **Files:** `plugin.yaml`
- **Estimate:** 2 min

### Task 7: Update README.md
- Add "Session Lifecycle" section documenting:
  - Automatic cleanup on session end
  - LRU eviction at 50 sessions
  - `session_duration` field in API
- **Files:** `README.md`
- **Estimate:** 5 min

## Wave 3 — Verification

### Task 8: Manual verification
- Confirm `register()` registers both hooks
- Confirm `_cleanup_session` removes from dict
- Confirm `_evict_if_needed` triggers at MAX_SESSIONS
- Confirm `get_tps_stats` includes `session_duration`
- Run any existing tests (blocked by her-test-suite-l0o, but verify no import errors)
- **Estimate:** 10 min

## Dependencies
- Tasks 1-5 are sequential (Wave 1)
- Tasks 6-7 can be parallel (Wave 2), after Wave 1
- Task 8 after Wave 2

## Total Estimate: ~43 min

## Blast Radius
- `__init__.py` — primary file, all changes here
- `plugin.yaml` — manifest update (1 line)
- `README.md` — documentation update
- No other files affected
- No new dependencies
- Fully backward compatible (additive only)
