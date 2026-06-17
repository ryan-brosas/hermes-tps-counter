---
purpose: Task decomposition with dependency tracking
updated: 2026-06-16
---

# Tasks: her-her-cleanup-orphaned-call-events-3bs

## 1. Fix store.delete() to also remove call_events

### 1.1 Add SQL constant for call_events deletion by session_id

```yaml
depends_on: []
parallel: false
files: ["store.py"]
estimated_minutes: 5
```

- [ ] Add `_DELETE_ONE_EVENT = "DELETE FROM call_events WHERE session_id = ?;"` near line 58 in store.py

### 1.2 Call _DELETE_ONE_EVENT inside delete()

```yaml
depends_on: ["1.1"]
parallel: false
files: ["store.py"]
estimated_minutes: 5
```

- [ ] In `PersistentSessionStore.delete()`, execute `_DELETE_ONE_EVENT` for the session_id alongside `_DELETE_ONE`, within the same lock scope

## 2. Fix store.delete_expired() to clean orphaned call_events

### 2.1 Add SQL constant for orphaned call_events cleanup

```yaml
depends_on: []
parallel: false
files: ["store.py"]
estimated_minutes: 5
```

- [ ] Add `_DELETE_ORPHANED_EVENTS = "DELETE FROM call_events WHERE session_id NOT IN (SELECT session_id FROM session_tps);"` near the other SQL constants

### 2.2 Execute orphan cleanup after expired session purge

```yaml
depends_on: ["2.1"]
parallel: false
files: ["store.py"]
estimated_minutes: 5
```

- [ ] In `PersistentSessionStore.delete_expired()`, after the `_DELETE_EXPIRED` execute, also execute `_DELETE_ORPHANED_EVENTS`

## 3. Fix _evict_if_needed() to call _STORE.delete()

### 3.1 Add _STORE.delete() call for evicted session

```yaml
depends_on: ["1.2"]
parallel: false
files: ["__init__.py"]
estimated_minutes: 5
```

- [ ] In `_evict_if_needed()` (line ~625), after popping from memory dicts, call `_STORE.delete(oldest_id)` if `_STORE is not None`

## 4. Add tests

### 4.1 Test: delete() removes call_events

```yaml
depends_on: ["1.2"]
parallel: true
files: ["tests/test_store_delete.py"]
estimated_minutes: 10
```

- [ ] Add test that inserts call_events for a session, calls `store.delete(session_id)`, asserts 0 call_events remain

### 4.2 Test: delete_expired() removes orphaned call_events

```yaml
depends_on: ["2.2"]
parallel: true
files: ["tests/test_store_delete.py"]
estimated_minutes: 10
```

- [ ] Add test that creates sessions with call_events, back-dates sessions, calls `delete_expired()`, asserts orphaned call_events are gone

### 4.3 Test: _evict_if_needed() removes DB state

```yaml
depends_on: ["3.1"]
parallel: true
files: ["tests/test_store_delete.py"]
estimated_minutes: 10
```

- [ ] Add test that sets max_sessions=1, creates 2 sessions with call_events, triggers eviction, asserts evicted session's DB row and call_events are removed

## 5. Verification

### 5.1 Run full test suite

```yaml
depends_on: ["4.1", "4.2", "4.3"]
parallel: false
```

- [ ] `pytest tests/ -v` — all tests green
