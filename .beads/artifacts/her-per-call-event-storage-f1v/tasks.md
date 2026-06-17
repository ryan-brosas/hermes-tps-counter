---
purpose: Task decomposition with dependency tracking
updated: 2026-06-16
---

# Tasks: her-per-call-event-storage-f1v

## Task Metadata

```yaml
bead: her-per-call-event-storage-f1v
total_tasks: 7
estimated_minutes: 90
```

## 1. Schema Migration (Wave 1)

### 1.1 Add call_events table DDL

```yaml
depends_on: []
parallel: false
files: ["store.py"]
estimated_minutes: 15
```

- [ ] Add `_CALL_EVENTS_DDL` SQL constant: `CREATE TABLE IF NOT EXISTS call_events (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, model TEXT NOT NULL DEFAULT '', provider TEXT NOT NULL DEFAULT '', input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0, duration REAL NOT NULL DEFAULT 0.0, tps REAL NOT NULL DEFAULT 0.0, created_at TEXT NOT NULL)`
- [ ] Add index: `CREATE INDEX IF NOT EXISTS idx_call_events_session_time ON call_events (session_id, created_at)`
- [ ] Bump `_SCHEMA_VERSION` from 2 to 3
- [ ] Add migration block in `_migrate()`: `if current < 3:` — executes `_CALL_EVENTS_DDL` and creates index
- [ ] Verification: create fresh DB, check `call_events` table exists, schema_version = 3

### 1.2 Add event INSERT method

```yaml
depends_on: ["1.1"]
parallel: false
files: ["store.py"]
estimated_minutes: 10
```

- [ ] Add `_INSERT_EVENT` SQL constant: `INSERT INTO call_events (session_id, model, provider, input_tokens, output_tokens, duration, tps, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
- [ ] Add `record_event(session_id, model, provider, input_tokens, output_tokens, duration, tps)` method to PersistentSessionStore
- [ ] Thread-safe: uses `self._lock` for INSERT + commit
- [ ] Verification: insert 3 events, `SELECT COUNT(*) FROM call_events` returns 3

### 1.3 Add event query methods

```yaml
depends_on: ["1.1"]
parallel: true
files: ["store.py"]
estimated_minutes: 20
```

- [ ] Add `load_events(session_id, since=None, until=None, limit=100)` — returns list of event dicts
- [ ] Add `aggregate_by_model(session_id, since=None)` — returns `{model: {calls, total_output, total_input, total_duration, avg_tps, peak_tps}}`
- [ ] Add `aggregate_by_provider(session_id, since=None)` — same shape grouped by provider
- [ ] Add `delete_expired_events(retention_seconds)` — deletes events older than retention
- [ ] Add `_expire_counter` class var, trigger expiry every 100 event writes
- [ ] Verification: insert events for 2 models, aggregate returns both with correct sums

## 2. Hook Integration (Wave 2 — parallel with 2.2)

### 2.1 Record events in _on_post_api_request

```yaml
depends_on: ["1.2"]
parallel: false
files: ["__init__.py"]
estimated_minutes: 10
```

- [ ] After the existing `_persist_state()` call in `_on_post_api_request`, add: `if _STORE is not None: _STORE.record_event(session_id, model, provider, input_tokens, output_tokens, duration, tps)`
- [ ] Must be inside `_STATE_LOCK` context (already held at that point)
- [ ] Compute `tps = output_tokens / duration` if duration > 0
- [ ] Verification: call hook 3 times, `SELECT COUNT(*) FROM call_events` returns 3

## 3. REST API Endpoints (Wave 2 — parallel with 2.1)

### 3.1 Add /api/v1/events/{session_id} endpoint

```yaml
depends_on: ["1.3"]
parallel: true
files: ["api.py"]
estimated_minutes: 15
```

- [ ] Add Pydantic models: `EventResponse` (id, session_id, model, provider, input_tokens, output_tokens, duration, tps, created_at), `EventListResponse` (events: List[EventResponse])
- [ ] Add `GET /api/v1/events/{session_id}` endpoint
- [ ] Query params: `since` (optional ISO timestamp), `until` (optional ISO timestamp), `limit` (default 100)
- [ ] Returns 503 if store is None, 404 if no events found
- [ ] Verification: insert events, GET returns correct count

### 3.2 Add /api/v1/trends/{session_id} endpoint

```yaml
depends_on: ["1.3"]
parallel: true
files: ["api.py"]
estimated_minutes: 15
```

- [ ] Add Pydantic model: `TrendResponse` (session_id, models: dict, providers: dict)
- [ ] Add `GET /api/v1/trends/{session_id}` endpoint
- [ ] Query param: `since` (optional ISO timestamp)
- [ ] Calls `store.aggregate_by_model()` and `store.aggregate_by_provider()`
- [ ] Returns 503 if store is None, 404 if no events
- [ ] Verification: insert events for 2 models, GET returns both in response

## 4. Test Suite (Wave 3)

### 4.1 Write test_event_storage.py

```yaml
depends_on: ["2.1", "3.1", "3.2"]
parallel: false
files: ["tests/test_event_storage.py"]
estimated_minutes: 20
```

- [ ] Test schema migration: fresh DB has call_events table, schema_version = 3
- [ ] Test record_event: insert + count
- [ ] Test load_events with since/until filters
- [ ] Test aggregate_by_model: 2 models, correct grouping
- [ ] Test aggregate_by_provider: 2 providers, correct grouping
- [ ] Test delete_expired_events: insert old event, trigger, verify gone
- [ ] Test concurrent writes: 4 threads × 20 writes, no corruption
- [ ] Test REST /api/v1/events: insert events, GET returns correct count
- [ ] Test REST /api/v1/trends: insert events, GET returns model/provider breakdowns
- [ ] Test backward compatibility: all existing tests still pass
- [ ] Verification: `pytest tests/test_event_storage.py -v` — all green

## 5. Full Regression (Wave 4)

### 5.1 Run full test suite

```yaml
depends_on: ["4.1"]
parallel: false
files: ["tests/"]
estimated_minutes: 5
```

- [ ] `pytest tests/ -v` — 0 failures
- [ ] Verify no import errors, no schema conflicts
- [ ] Verification: all tests green, no warnings
