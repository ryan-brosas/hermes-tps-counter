# Tasks: her-store-delete-expire-ru7

## Task 1: Add SQL constants and delete/count/expire methods to PersistentSessionStore
**File:** store.py
**Action:**
1. Add SQL constants after existing ones:
   - `_DELETE_ONE = "DELETE FROM session_tps WHERE session_id = ?;"`
   - `_DELETE_EXPIRED = "DELETE FROM session_tps WHERE updated_at < ?;"`
   - `_COUNT = "SELECT COUNT(*) FROM session_tps;"`
2. Add `delete(self, session_id: str) -> bool` method:
   - Guard: `if self._conn is None: return False`
   - Try: execute `_DELETE_ONE`, commit, return `cur.rowcount > 0`
   - Except: log warning, return False
   - Thread-safe: use `with self._lock`
3. Add `delete_expired(self, max_age_seconds: float) -> int` method:
   - Guard: `if self._conn is None: return 0`
   - Compute cutoff: `(datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()`
   - Try: execute `_DELETE_EXPIRED` with cutoff, commit, return `cur.rowcount`
   - Except: log warning, return 0
   - Thread-safe: use `with self._lock`
   - Add `from datetime import timedelta` to imports
4. Add `count(self) -> int` method:
   - Guard: `if self._conn is None: return 0`
   - Try: execute `_COUNT`, fetchone, return `row[0]`
   - Except: log warning, return 0
   - Thread-safe: use `with self._lock`
**Verification:** `python3 -c "from store import PersistentSessionStore; s = PersistentSessionStore('/tmp/test_tps.db'); print(s.count()); s.close()"` returns 0
**Parallel:** No
**Depends on:** None

## Task 2: Wire _cleanup_session to delete from DB
**File:** __init__.py
**Action:**
1. In `_cleanup_session()`, after the existing `with _STATE_LOCK:` block, add:
   ```python
   # Also remove from persistent store
   if _STORE is not None:
       try:
           _STORE.delete(session_id)
       except Exception as exc:
           logger.debug("tps-counter: DB cleanup failed for %s: %s", session_id, exc)
   ```
2. This is best-effort — memory cleanup already happened, DB cleanup is secondary
**Verification:** Create a session via `_on_post_api_request`, call `_cleanup_session`, verify `_STORE.load(session_id)` returns None
**Parallel:** No
**Depends on:** Task 1

## Task 3: Add tests for delete, delete_expired, count, and cleanup integration
**File:** tests/test_store_delete.py (new)
**Action:**
1. Create test file with `autouse` fixture for `hermes_cli` mock (same pattern as other test files)
2. `TestDelete` class:
   - `test_delete_existing_session` — save a session, delete it, verify returns True, load returns None
   - `test_delete_nonexistent_session` — delete session that doesn't exist, verify returns False
   - `test_delete_on_closed_store` — close store, verify delete returns False without error
3. `TestDeleteExpired` class:
   - `test_delete_expired_removes_old_sessions` — save 3 sessions, manually update 2 with old `updated_at`, call delete_expired, verify count=2, remaining=1
   - `test_delete_expired_no_matches` — save sessions with recent timestamps, call delete_expired with short max_age, verify returns 0
   - `test_delete_expired_empty_db` — call on empty DB, verify returns 0
4. `TestCount` class:
   - `test_count_empty` — verify returns 0
   - `test_count_populated` — save 3 sessions, verify returns 3
   - `test_count_after_delete` — save 3, delete 1, verify returns 2
5. `TestCleanupIntegration` class:
   - `test_cleanup_deletes_from_db` — use `_on_post_api_request` to create session, call `_cleanup_session`, verify `_STORE.load()` returns None
   - `test_cleanup_nonexistent_session` — call `_cleanup_session` for unknown session, verify no error
**Verification:** `cd /home/ryan/repos/hermes-tps-counter/ && python3 -m pytest tests/test_store_delete.py -v` — all pass
**Parallel:** No
**Depends on:** Task 1, Task 2
