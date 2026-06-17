---
purpose: Agent spawn context for a bead
updated: 2026-06-16
---

# Context Capsule: her-per-call-event-storage-f1v

## Objective

Add a `call_events` append-only table to the existing SQLite DB and wire it into the post_api_request hook, REST API, and test suite — enabling per-call TPS time-series analysis.

## Key Patterns

- **SQL constants as module-level strings** — All SQL (DDL, INSERT, SELECT) defined as `_CALL_EVENTS_DDL`, `_INSERT_EVENT`, `_LOAD_EVENTS`, etc. at module top. Reference: `store.py` lines 21-62
- **Thread-safe with self._lock** — Every DB write acquires `self._lock` (threading.Lock). Never touch `self._conn` without it. Reference: `store.py` lines 78, 184
- **UPSERT vs INSERT** — session_tps uses INSERT OR REPLACE (upsert). call_events uses plain INSERT (append-only, never update). Reference: `store.py` lines 39-44
- **_state_to_row / _row_to_dict** — Static methods for serialization. Follow same pattern for event rows. Reference: `store.py` lines 131-172
- **_migrate() pattern** — Schema migrations in `_migrate()` with `if current < N:` blocks and try/except for ALTER TABLE. Reference: `store.py` lines 106-129
- **Pydantic response models** — All API endpoints use Pydantic BaseModel for request/response. Reference: `api.py` lines 23-48
- **Test fixtures** — `tmp_path` + `PersistentSessionStore` + `mock_hermes_cli` autouse fixture. Reference: `tests/test_persistence.py` lines 18-24
- **Lazy expiry on write** — Every N event INSERTs, run `DELETE FROM call_events WHERE created_at < ?`. Counter-based, not time-based. Reference: PRD decisions.md

## Constraints

1. Same SQLite DB file as session_tps — no new connections, no separate DB
2. Event write must be < 1ms (sub-millisecond INSERT)
3. Schema migration handles existing DBs without call_events table (try/except)
4. Must not break any existing test (test_api, test_persistence, test_provider_tps, test_store_delete, test_usage_parsing)
5. All new code in store.py, __init__.py, api.py — never touch .pi/, README.md, HERMES.md
6. Thread-safe: all DB operations through PersistentSessionStore._lock

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Schema + store methods | `store.py` — add DDL, migration, query methods | `__init__.py` — no changes yet |
| Hook integration | `__init__.py` — add event recording after _persist_state | `store.py` — read-only |
| REST endpoints | `api.py` — add events + trends endpoints | `__init__.py` — read-only |
| Tests | `tests/test_event_storage.py` — new file | `tests/test_*.py` — no modifications to existing tests |

## Graph Context

- **Blast radius:** store.py, __init__.py, api.py, tests/test_event_storage.py (new)
- **Related beads:** All 9 closed foundational beads (no conflicts)
- **File history:** store.py touched by session-data-persistence + store-delete-expire; api.py touched by rest-api-endpoints; __init__.py touched by multiple beads
