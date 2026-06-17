---
purpose: Wave-sequenced implementation plan
updated: 2026-06-16
---

# Plan: her-per-call-event-storage-f1v

**Goal:** Add per-call TPS event storage with time-series queries to enable trend analysis, degradation detection, and dashboard visualization.

## Graph Context

- **Blast radius:** store.py, __init__.py, api.py, tests/test_event_storage.py (new)
- **Unblocks:** Health monitoring dashboard, degradation detection, notification system
- **Blocked by:** None (all 9 foundational beads are closed)
- **Critical path:** Yes — this is the data layer for all future analytics phases
- **Forecast:** ~85 minutes estimated, single-agent execution

## Observable Truths

1. A `call_events` table exists in the SQLite DB with schema_version = 3
2. Each `_on_post_api_request` hook call inserts one row into `call_events`
3. `store.load_events(session_id, since, until)` returns time-filtered events
4. `store.aggregate_by_model(session_id, since)` and `store.aggregate_by_provider(session_id, since)` return grouped stats
5. GET `/api/v1/events/{session_id}` returns event list with optional since/until params
6. GET `/api/v1/trends/{session_id}` returns per-model and per-provider aggregated trends
7. Events older than retention_days are auto-expired on write
8. All existing tests pass, new tests achieve >90% coverage of new code

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| call_events table | Per-call event storage | `store.py` | Need |
| Event recording hook | Auto-record each API call | `__init__.py` | Need |
| Query methods | Time-range, model, provider aggregations | `store.py` | Need |
| REST endpoints | Event history and trend data | `api.py` | Need |
| Test suite | Verification of all new code | `tests/test_event_storage.py` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | Schema + store methods | No | None | `pytest tests/test_persistence.py -v` (existing tests still pass) |
| 2 | Hook integration + API endpoints | Yes (parallel) | Wave 1 complete | `pytest tests/test_api.py -v` (existing tests still pass) |
| 3 | New test suite | No | Wave 2 complete | `pytest tests/test_event_storage.py -v` — all green |
| 4 | Full regression | No | Wave 3 complete | `pytest tests/ -v` — 0 failures |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
# Verify schema migration
python3 -c "from store import PersistentSessionStore; import tempfile, os; fd, p = tempfile.mkstemp(suffix='.db'); os.close(fd); s = PersistentSessionStore(p); import sqlite3; conn = sqlite3.connect(p); v = conn.execute('SELECT version FROM schema_version').fetchone()[0]; conn.close(); s.close(); assert v == 3, f'Schema version {v} != 3'; print('Schema version: OK')"

# Verify call_events table exists
python3 -c "from store import PersistentSessionStore; import tempfile, os; fd, p = tempfile.mkstemp(suffix='.db'); os.close(fd); s = PersistentSessionStore(p); import sqlite3; conn = sqlite3.connect(p); tables = {r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()}; conn.close(); s.close(); assert 'call_events' in tables, f'Missing call_events, have: {tables}'; print('call_events table: OK')"

# Run all tests
pytest tests/ -v
```
