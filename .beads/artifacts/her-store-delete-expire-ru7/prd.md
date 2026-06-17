# PRD: Add delete and expire methods to PersistentSessionStore

## Problem

`PersistentSessionStore` can INSERT and SELECT but never DELETE. The SQLite database grows unboundedly — every session that ever called the LLM accumulates a row that is never removed. Even after the session lifecycle cleanup bead (`her-session-lifecycle-cleanup-ot1`) evicts sessions from memory, the DB retains stale records forever.

This creates three concrete problems:
1. **Disk bloat**: Long-running Hermes gateways accumulate thousands of stale session rows
2. **Stale data in REST API**: The `GET /api/v1/sessions` endpoint (from `her-rest-api-tps-endpoints-56b`) would return dead sessions mixed with live ones
3. **No garbage collection**: The lifecycle cleanup bead only clears in-memory dicts — there is no corresponding DB cleanup path

## Scope

**In scope:**
- `delete(session_id)` method on `PersistentSessionStore`
- `delete_expired(max_age_seconds)` method to bulk-purge old sessions
- `count()` method for diagnostics (how many rows in DB)
- Integration with `_cleanup_session()` in `__init__.py` to also delete from DB
- Tests for all new methods

**Out of scope:**
- LRU eviction logic (covered by `her-session-lifecycle-cleanup-ot1`)
- REST API endpoints (covered by `her-rest-api-tps-endpoints-56b`)
- Database migration from schema v2 to v3 (no schema change needed — we're adding operations, not columns)
- Backup/archival before deletion

## Requirements

1. `delete(session_id: str) -> bool` — removes one session row, returns True if a row was deleted
2. `delete_expired(max_age_seconds: float) -> int` — removes all sessions where `updated_at` is older than `max_age_seconds` ago; returns count of deleted rows
3. `count() -> int` — returns total number of rows in `session_tps`
4. All methods are thread-safe (use existing `_lock` pattern)
5. All methods handle `self._conn is None` gracefully (return 0/False/0, log warning)
6. `_cleanup_session()` in `__init__.py` calls `_STORE.delete(session_id)` after clearing in-memory state
7. Tests cover: delete existing, delete nonexistent, delete_expired with mixed ages, delete_expired with no matches, count empty, count populated, thread safety of delete

## Approach

1. Add three methods to `PersistentSessionStore` in `store.py`
2. Add `_DELETE_ONE`, `_DELETE_EXPIRED`, `_COUNT` SQL constants
3. Wire `_cleanup_session()` in `__init__.py` to call `_STORE.delete(session_id)`
4. Add `tests/test_store_delete.py` with comprehensive coverage
5. No schema migration needed — existing `updated_at` column supports expiration queries

## Success Criteria

- [ ] `delete(session_id)` removes a row and returns True; returns False for missing session
- [ ] `delete_expired(max_age_seconds)` removes old sessions and returns count
- [ ] `count()` returns accurate row count
- [ ] `_cleanup_session()` deletes from both memory AND DB
- [ ] All new tests pass
- [ ] All existing tests still pass (backward compatible)
- [ ] No new dependencies (stdlib only)

## Risks

- Risk: `delete()` called while another thread is reading the same session
  - Mitigation: SQLite WAL mode handles this; `_lock` serializes writes
- Risk: `_cleanup_session()` DB delete fails but memory cleanup succeeds
  - Mitigation: DB delete is best-effort (log warning, don't re-add to memory)
