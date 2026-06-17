# Tasks: her-session-lifecycle-cleanup-ot1

## Task 1: Add MAX_SESSIONS constant and created_at field
**File:** __init__.py
**Action:** Add `MAX_SESSIONS = 50` module-level constant. Add `created_at` to `_SessionTPS.__slots__` and `__init__`. Set `self.created_at = time.time()` in `__init__`.
**Verification:** `_SessionTPS()` has `created_at` attribute
**Parallel:** No
**Depends on:** None

## Task 2: Implement _cleanup_session and _evict_if_needed
**File:** __init__.py
**Action:** Add `_cleanup_session(session_id)`: remove from `_SESSIONS` under `_STATE_LOCK`. Add `_evict_if_needed()`: if `len(_SESSIONS) > MAX_SESSIONS`, find session with oldest `turn_start_time`, call `_cleanup_session` on it. Log eviction at debug level.
**Verification:** Functions exist and handle edge cases
**Parallel:** No
**Depends on:** Task 1

## Task 3: Wire eviction into _on_post_api_request
**File:** __init__.py
**Action:** After `state.record(...)`, call `_evict_if_needed()`.
**Verification:** Eviction triggers after record call when over limit
**Parallel:** No
**Depends on:** Task 2

## Task 4: Register on_session_end hook
**File:** __init__.py
**Action:** In `register()`, add `ctx.register_hook("on_session_end", _on_session_end)`. Implement `_on_session_end(**kwargs)`: extract `session_id` from kwargs, call `_cleanup_session(session_id)`. Log cleanup at debug level.
**Verification:** `register()` registers both hooks
**Parallel:** No
**Depends on:** Task 3

## Task 5: Add session_duration to get_tps_stats
**File:** __init__.py
**Action:** Compute `time.time() - state.created_at` and return as `session_duration`.
**Verification:** `get_tps_stats` includes `session_duration`
**Parallel:** No
**Depends on:** Task 4

## Task 6: Update plugin.yaml
**File:** plugin.yaml
**Action:** Add `on_session_end` to `provides_hooks` list.
**Verification:** plugin.yaml contains on_session_end hook
**Parallel:** Yes
**Depends on:** Task 5

## Task 7: Update README.md
**File:** README.md
**Action:** Add "Session Lifecycle" section documenting automatic cleanup on session end, LRU eviction at 50 sessions, `session_duration` field in API.
**Verification:** README documents session lifecycle features
**Parallel:** Yes
**Depends on:** Task 5

## Task 8: Manual verification
**File:** (verification only)
**Action:** Confirm `register()` registers both hooks. Confirm `_cleanup_session` removes from dict. Confirm `_evict_if_needed` triggers at MAX_SESSIONS. Confirm `get_tps_stats` includes `session_duration`. Run any existing tests (verify no import errors).
**Verification:** All checks pass, no import errors
**Parallel:** No
**Depends on:** Task 6, Task 7
