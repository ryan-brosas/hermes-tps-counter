# Plan: Add delete and expire methods to PersistentSessionStore

## Wave 1: Store methods (single file, no dependencies)

### Task 1: Add SQL constants and delete/count/expire methods to store.py
- File: `store.py`
- Add `_DELETE_ONE`, `_DELETE_EXPIRED`, `_COUNT` SQL constants
- Add `delete(session_id) -> bool` method
- Add `delete_expired(max_age_seconds) -> int` method
- Add `count() -> int` method
- All follow existing patterns: `self._lock`, `self._conn is None` guard, try/except with logger.warning

## Wave 2: Wire cleanup (depends on Wave 1)

### Task 2: Wire _cleanup_session to delete from DB
- File: `__init__.py`
- In `_cleanup_session()`, after clearing in-memory state, call `_STORE.delete(session_id)`
- Best-effort: wrap in try/except, log on failure, don't re-add to memory

## Wave 3: Tests (depends on Wave 1)

### Task 3: Add tests for delete, delete_expired, count
- File: `tests/test_store_delete.py`
- Test delete existing session returns True
- Test delete nonexistent session returns False
- Test delete_expired with sessions of varying ages
- Test delete_expired returns correct count
- Test delete_expired with no matches returns 0
- Test count on empty DB returns 0
- Test count on populated DB returns correct value
- Test cleanup_session integration (memory + DB both cleared)

## Context Capsule

**Key patterns to follow:**
- SQL constants at module level (see `_UPSERT`, `_LOAD_ONE`, etc.)
- Methods use `self._lock` for thread safety
- Methods check `self._conn is None` and return early with safe default
- Methods catch `Exception`, log with `logger.warning`, return safe default
- `_state_to_row` uses `datetime.now(timezone.utc).isoformat()` for timestamps
- `updated_at` column stores ISO format strings — compare with ISO format for expiration

**Files to modify:**
- `store.py` — add 3 methods + 3 SQL constants
- `__init__.py` — modify `_cleanup_session()` to call `_STORE.delete()`
- `tests/test_store_delete.py` — new test file

**Dependencies:**
- No new packages
- No schema migration
- Depends on existing `_cleanup_session()` function and `_STORE` global
