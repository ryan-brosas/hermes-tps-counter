---
purpose: Product Requirements Document for a bead
updated: 2026-06-16
---

# PRD: Per-call TPS Event Storage with Time-Series Queries

**Bead:** her-per-call-event-storage-f1v | **Type:** feature | **Priority:** P2
**Created:** 2026-06-16 | **Estimate:** 90 minutes

## Problem

WHEN a user wants to analyze TPS trends over time or detect performance degradation THEN they cannot because BECAUSE the current SQLite store only keeps one cumulative row per session — no per-call event history exists. The `session_tps` table records totals but loses the individual call-by-call measurements that would reveal patterns like gradual TPS decline, provider-specific slowdowns, or time-of-day performance variation.

**Who is affected?** Anyone using the tps-counter plugin who wants historical insights beyond "current session totals." This blocks the entire dashboard and health monitoring roadmap.

**Why now?** All 9 foundational beads are closed (tracking, persistence, API, tests). The next three roadmap phases (health monitoring, dashboard, notifications) all depend on per-call time-series data. Without this, there is nothing to visualize, alert on, or detect degradation from.

## Scope

### In Scope
- `call_events` table in existing SQLite DB (append-only, timestamped)
- Per-call recording: session_id, model, provider, input_tokens, output_tokens, duration, tps, timestamp
- Index on (session_id, timestamp) for fast range queries
- Query methods: time-range filter, per-model aggregation, per-provider aggregation, rolling averages
- REST API endpoints for event history and trend data
- Configurable retention period with auto-expiry (default 7 days)
- Thread-safe writes following existing _STATE_LOCK + store pattern
- Tests for all new code

### Out of Scope
- Frontend dashboard (Phase 4 — separate bead)
- Health degradation detection logic (Phase 3 — separate bead, depends on this)
- Notification/alerting system (Phase 5 — separate bead)
- WebSocket real-time streaming (future work)
- P99 ITL, C/S/R rates, capability flags (Phase 6)

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | `call_events` table with per-call TPS data | MUST | Table exists with columns: id, session_id, model, provider, input_tokens, output_tokens, duration, tps, created_at. Verify: `SELECT * FROM call_events LIMIT 1` |
| 2 | Auto-record each API call as an event | MUST | `_on_post_api_request` writes a row to call_events in addition to session_tps UPSERT. Verify: call hook twice, `SELECT COUNT(*) FROM call_events` returns 2 |
| 3 | Time-range query method | MUST | `store.load_events(session_id, since, until)` returns events in range. Verify: insert events at different timestamps, query with since filter |
| 4 | Aggregation query methods | MUST | `store.aggregate_by_model(session_id, since)` and `store.aggregate_by_provider(session_id, since)` return grouped stats. Verify: insert events for 2 models, aggregate returns both |
| 5 | REST API: GET /api/v1/events/{session_id} | MUST | Returns list of events with optional `?since=` and `?until=` query params. Verify: HTTP 200 with correct event count |
| 6 | REST API: GET /api/v1/trends/{session_id} | MUST | Returns per-model and per-provider aggregated trends. Verify: HTTP 200 with model/provider breakdowns |
| 7 | Auto-expiry of old events | MUST | Events older than retention period are deleted on write. Verify: insert old event, trigger write, old event gone |
| 8 | Configurable retention period | SHOULD | `retention_days` in plugin config, defaults to 7. Verify: set to 1 day, events older than 24h are purged |
| 9 | Thread-safe concurrent writes | MUST | Multiple threads writing events simultaneously don't corrupt data. Verify: concurrent test with 4 threads × 20 writes |
| 10 | Backward compatible with existing tests | MUST | All existing tests still pass. Verify: `pytest tests/ -v` all green |

## Technical Context

**Key files:**
- `store.py` — PersistentSessionStore (add call_events table, new query methods)
- `__init__.py` — `_on_post_api_request` hook (add event recording after session UPSERT)
- `api.py` — FastAPI app (add /api/v1/events and /api/v1/trends endpoints)
- `tests/` — new test file for event storage + time-series queries

**Existing patterns:**
- `_STATE_LOCK` threading.Lock for all state mutations
- `PersistentSessionStore._lock` for DB-level thread safety
- UPSERT pattern in `save()` — but events are INSERT (append-only, never update)
- `_UPSERT`, `_LOAD_ONE`, `_LOAD_ALL` SQL constants defined as module-level strings
- `_state_to_row` / `_row_to_dict` static methods for serialization
- FastAPI endpoints use Pydantic response models
- Tests use `tmp_path` fixture + `PersistentSessionStore` + `mock_hermes_cli` autouse fixture

**Constraints:**
- Same SQLite DB file as session_tps (no new connections)
- Must not slow down the hot path (event write should be < 1ms)
- Schema migration must handle existing DBs without call_events table

## Approach

**Chosen: Append-only event log with periodic expiry**

Add a `call_events` table to the existing SQLite schema. Each `_on_post_api_request` call INSERTs a row after the existing session_tps UPSERT. Add indexed queries for time-range, model, and provider aggregations. Run expiry as a lazy check on write (every N writes, delete old events).

**Why this approach:**
- Simple — one table, one INSERT per call, standard SQL queries
- Compatible — uses existing DB connection and lock patterns
- Efficient — INSERT is fast, indexed range queries are fast
- Foundation — provides the data layer that all future phases need

**Alternatives considered:**

1. **Separate time-series DB (e.g., separate SQLite file or DuckDB)** — Rejected: adds complexity, new connection management, and deployment burden for marginal query performance gain at this scale.

2. **Aggregate-only (hourly/daily rollup tables)** — Rejected: loses per-call granularity needed for degradation detection. Can add rollup tables later as an optimization.

3. **In-memory ring buffer + periodic flush** — Rejected: data loss risk on crash, added complexity. The hot path is already fast enough with direct SQLite INSERT.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Event table grows unbounded if expiry fails | Low | Medium | Dual safety: expiry on write + configurable retention. DB count check in health endpoint. |
| INSERT on hot path slows API responses | Low | Low | SQLite INSERT is sub-millisecond. Index on timestamp only, not full-text. |
| Schema migration fails on existing DBs | Low | Medium | ALTER TABLE in try/except (same pattern as v1→v2 migration in store.py). |
| Thread contention on DB writes | Low | Low | Same lock pattern as existing save(). WAL mode supports concurrent reads. |

## Success Criteria

- [ ] `call_events` table exists and schema version is 3
    - Verify: `SELECT version FROM schema_version` returns 3
- [ ] Each hook call records an event row
    - Verify: `SELECT COUNT(*) FROM call_events` after 3 hook calls returns 3
- [ ] Time-range query returns correct subset
    - Verify: insert events at t=1, t=2, t=3; query since=t=2 returns 2 events
- [ ] Model/provider aggregation returns grouped stats
    - Verify: insert events for 2 models, aggregate returns both with correct sums
- [ ] REST API endpoints return correct data
    - Verify: `GET /api/v1/events/test-sess` returns event list
- [ ] Old events are auto-expired
    - Verify: insert event with old timestamp, trigger new write, old event deleted
- [ ] All existing tests pass
    - Verify: `pytest tests/ -v` — 0 failures
- [ ] New tests achieve >90% coverage of new code
    - Verify: `pytest tests/test_event_storage.py -v` — all green

## Acceptance Criteria

- [ ] call_events table exists with correct schema and schema_version = 3
- [ ] Each API call hook invocation INSERTs one row into call_events
- [ ] load_events(session_id, since, until) returns correct time-filtered results
- [ ] aggregate_by_model() and aggregate_by_provider() return grouped stats
- [ ] GET /api/v1/events/{session_id} returns event list with 200 status
- [ ] GET /api/v1/trends/{session_id} returns model/provider breakdowns with 200 status
- [ ] Events older than retention_days are auto-expired on write
- [ ] Concurrent 4-thread × 20-write test passes without corruption
- [ ] All existing tests (test_api, test_persistence, test_provider_tps, test_store_delete, test_usage_parsing) still pass
- [ ] New test_event_storage.py has >90% coverage of new code
