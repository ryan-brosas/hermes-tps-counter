---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-feat-historical-tps-export-s3i

## Objective

Add a bounded, read-only `GET /api/v1/export/history` endpoint to the FastAPI app that exports persisted session TPS and per-call event data as JSON (with optional CSV) for offline analysis and dashboard import, with enforced query bounds preventing unbounded SQLite reads.

## Key Patterns

- **Bounded SQL queries** — All export queries must use explicit `LIMIT` and `WHERE` clauses. Never call `load_all()` for event exports. Reference: `store.py` lines 362-388 (`load_events` pattern)
- **Pydantic response models** — Follow existing `HealthResponse`, `SessionTPSResponse`, `EventListResponse` pattern for typed responses. Reference: `api.py` lines 314-434
- **503 for store unavailability** — All endpoints that need the store return 503 when `store is None`. Reference: `api.py` lines 184-210 (`test_session_tps_503_when_store_none`)
- **Error consistency** — Follow existing error response shape and status codes. Reference: `api.py` existing error handlers
- **SQL constant pattern** — Define SQL as module-level string constants (e.g., `_LOAD_EVENTS`, `_AGGREGATE_BY_MODEL`). Reference: `store.py` lines 62-120
- **Test fixture pattern** — Use `tmp_path` for SQLite DB, `PersistentSessionStore(db_path)` for store, `TestClient(create_app(store))` for API tests. Reference: `tests/test_api.py` lines 60-90, `tests/test_event_storage.py` lines 45-90

## Constraints

1. **No existing endpoint changes** — All existing `/api/v1/health`, `/api/v1/sessions`, `/api/v1/sessions/{id}/tps`, `/api/v1/summary`, `/api/v1/events/{id}`, `/api/v1/trends/{id}`, `/api/v1/health/diagnostics`, `/metrics`, `/ws/tps` must retain current behavior and status codes.
2. **Bounded queries only** — Every export query must enforce `LIMIT`. Default limit = 100, max limit = 1000. Requests without sufficient bounds must be rejected (400/422), not silently scan all data.
3. **No new dependencies** — CSV support (if implemented) must use Python stdlib `csv` module only. No new pip packages, build steps, or background jobs.
4. **Local-only API preservation** — Do not change CORS, host binding, or authentication defaults. The export endpoint is for local offline analysis, not remote exposure.
5. **SQLite thread safety** — Use existing `self._lock` pattern for all DB access in new store methods.
6. **Files allowed:** `api.py`, `store.py`, `README.md`, `tests/test_api.py`, `tests/test_event_storage.py`
7. **Files forbidden:** `.beads/beads.db`, `.env.local`, credentials, `plan.md`, `tasks.md`, `context-capsule.md`

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Store helper | `store.py` — add export methods + SQL constants; `tests/test_event_storage.py` — add export tests | `api.py` — no changes in this task |
| API endpoint | `api.py` — add endpoint + response models; `tests/test_api.py` — add export tests | `store.py` — only read, do not modify |
| README docs | `README.md` — add export section | All source code files |
| Verification | Read-only test execution | All file modifications |

## Graph Context

- **Blast radius:** `store.py`, `api.py`, `tests/test_event_storage.py`, `tests/test_api.py`, `README.md` (5 files)
- **Related beads:** `her-feat-batch-session-stats-ojy` (sibling on track-A, touches same files but different features)
- **File history:** `store.py` and `api.py` are the hottest files in the repo — touched by most feature beads
- **No blockers:** Bead is fully unblocked, no upstream dependencies
- **Track:** B (parallel with track-A batch session stats)

## Existing Store Methods Available

- `load_events(session_id, since=None, until=None, limit=100)` — session-scoped only, cannot export cross-session
- `load_all()` — returns all session_tps as dict, no time/limit bounds — DO NOT USE for event export
- `load(session_id)` — single session lookup
- `count()` — session_tps row count
- `event_count()` — call_events row count
- `record_event(session_id, model, provider, input_tokens, output_tokens, duration, tps)` — write path

## New Store Methods Needed

- `export_events(since=None, until=None, limit=100, max_limit=1000)` — cross-session bounded event export
- `export_sessions(session_ids=None, since=None, until=None, limit=100, max_limit=1000)` — bounded session export

## Existing DB Schema (relevant tables)

```sql
-- session_tps: session-level TPS state
CREATE TABLE IF NOT EXISTS session_tps (
    session_id TEXT PRIMARY KEY,
    last_tps REAL, avg_tps REAL, peak_tps REAL,
    total_output_tokens INTEGER, total_input_tokens INTEGER,
    created_at TEXT, updated_at TEXT
);

-- call_events: per-call event records
CREATE TABLE IF NOT EXISTS call_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    model TEXT, provider TEXT,
    input_tokens INTEGER, output_tokens INTEGER,
    duration REAL, tps REAL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_call_events_session_time
    ON call_events (session_id, created_at);
```
