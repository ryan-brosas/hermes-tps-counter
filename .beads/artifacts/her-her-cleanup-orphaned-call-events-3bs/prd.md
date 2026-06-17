---
purpose: Product Requirements Document for a bead
updated: 2026-06-16
---

# PRD: Session cleanup should also delete orphaned call_events

**Bead:** her-her-cleanup-orphaned-call-events-3bs | **Type:** bug | **Priority:** P2
**Created:** 2026-06-16 | **Estimate:** 45

## Problem

WHEN a session ends or is evicted THEN `store.delete(session_id)` only removes the row from `session_tps` but leaves all corresponding `call_events` rows untouched BECAUSE the `delete()` SQL only targets `session_tps` and has no cascade or secondary DELETE for `call_events`.

**Who is affected?** Any deployment with persistence enabled — orphaned `call_events` rows accumulate indefinitely, growing the SQLite database without bound even after sessions are cleaned up.

**Why now?** The `call_events` table was added later (schema v3) but the delete path was never updated to include it. Every session lifecycle (end, eviction, expiry) leaks rows. Over time this causes disk bloat and slower queries on `call_events`.

## Scope

### In Scope
- `PersistentSessionStore.delete()` must also delete from `call_events` for the given session_id
- `PersistentSessionStore.delete_expired()` must also delete orphaned `call_events` whose session_id no longer exists in `session_tps`
- `_evict_if_needed()` in `__init__.py` must call `_STORE.delete()` so evicted sessions are also purged from the DB
- Tests verifying call_events cleanup on delete, delete_expired, and eviction

### Out of Scope
- Schema migration (no DDL changes needed — the table and index already exist)
- API changes
- Prometheus metric changes
- Retention-based event expiry (already handled by `delete_expired_events`)

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | `store.delete(session_id)` removes rows from both `session_tps` and `call_events` | MUST | After `delete("s1")`, `SELECT COUNT(*) FROM call_events WHERE session_id = 's1'` returns 0 |
| 2 | `store.delete_expired(max_age)` removes orphaned `call_events` whose session_id is absent from `session_tps` | MUST | After deleting old sessions, no `call_events` rows reference non-existent sessions |
| 3 | `_evict_if_needed()` calls `_STORE.delete()` for the evicted session | MUST | LRU eviction removes both memory and DB state |
| 4 | All existing tests pass | MUST | `pytest` green |
| 5 | New tests cover call_events cleanup paths | MUST | Tests for delete, delete_expired, and eviction with call_events data |

## Steps to Reproduce

1. Start Hermes with persistence enabled (default config)
2. Create a session and make several API calls (generates call_events rows)
3. End the session or wait for LRU eviction
4. Query the database: `SELECT COUNT(*) FROM call_events WHERE session_id = '<ended-session-id>'`
5. Observe: the count is > 0 — orphaned rows remain

## Acceptance Criteria

1. `store.delete("s1")` removes all `call_events` for session `s1` — `SELECT COUNT(*) FROM call_events WHERE session_id = 's1'` returns 0
2. `store.delete_expired()` leaves no orphaned `call_events` — query for call_events with session_id not in session_tps returns 0
3. `_evict_if_needed()` removes evicted session from DB — `store.load(evicted_id)` returns None and call_events count is 0
4. All existing + new tests pass — `pytest tests/ -v` green

## Technical Context

**Key files:**
- `store.py` — `PersistentSessionStore` with `delete()`, `delete_expired()`, SQL constants `_DELETE_ONE`, `_DELETE_EXPIRED`
- `__init__.py` — `_cleanup_session()`, `_evict_if_needed()` (lines 610–640)
- `tests/test_store_delete.py` — existing delete/cleanup tests

**SQL constants involved:**
- `_DELETE_ONE = "DELETE FROM session_tps WHERE session_id = ?;"` — needs a companion for call_events
- `_DELETE_EXPIRED = "DELETE FROM session_tps WHERE updated_at < ?;"` — needs orphan cleanup

**No FK constraint** exists between `call_events.session_id` and `session_tps.session_id`, so there is no automatic cascade.

## Approach

Add a `_DELETE_ONE_EVENT` SQL constant (`DELETE FROM call_events WHERE session_id = ?`) and execute it inside `delete()` before or after the `session_tps` delete, within the same lock scope. For `delete_expired()`, delete `call_events` rows whose `session_id` is not in `session_tps` after the expired-session purge. Fix `_evict_if_needed()` to call `_STORE.delete()`.

**Alternatives considered:**
- Adding a FOREIGN KEY with CASCADE — rejected: requires schema migration and rebuild of existing tables
- Cleaning up via periodic background task — rejected: adds complexity; cleanup-on-delete is simpler and immediate

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Slightly longer delete latency (two DELETE statements) | Low | Low | Both execute under same lock in a single transaction |
| Orphaned events from sessions deleted before this fix | Low | Low | One-time manual cleanup or first `delete_expired` run handles it |

## Success Criteria

- [ ] `store.delete("s1")` removes all `call_events` for session `s1`
    - Verify: `SELECT COUNT(*) FROM call_events WHERE session_id = 's1'` returns 0
- [ ] `store.delete_expired()` leaves no orphaned `call_events`
    - Verify: query for `call_events` with session_id not in `session_tps` returns 0
- [ ] `_evict_if_needed()` removes evicted session from DB
    - Verify: after eviction, `store.load(evicted_id)` returns None and `call_events` count is 0
- [ ] All existing + new tests pass
    - Verify: `pytest tests/test_store_delete.py -v`
