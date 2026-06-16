# Plan: SQLite persistence for TPS session data

## Wave Sequence

```
Wave 1 (foundation)     Wave 2 (integration)     Wave 3 (testing)
┌──────────────────┐    ┌──────────────────┐     ┌──────────────────┐
│ T1: DB schema +  │    │ T3: Integrate    │     │ T5: Persistence  │
│ store class      │───▶│ into __init__.py │────▶│ tests            │
│                  │    │                  │     │                  │
│ T2: Config/      │    │ T4: Graceful     │     │ T6: Verify all   │
│ DB path setup    │───▶│ degradation      │     │ existing tests   │
└──────────────────┘    └──────────────────┘     └──────────────────┘
```

## Tasks

### T1: Create `store.py` with SQLite schema and PersistentSessionStore class

**Goal**: Self-contained persistence layer in a new file.

**Steps**:
1. Create `store.py` at plugin root
2. Define schema: `session_tps` table (session_id TEXT PK, call_count INT, total_output_tokens INT, total_duration REAL, peak_tps REAL, last_call_tps REAL, avg_tps REAL, updated_at TEXT)
3. Add `schema_version` table for migration support
4. Implement `PersistentSessionStore` class:
   - `__init__(db_path)` — open connection, run migrations
   - `save(session_id, state: _SessionTPS)` — UPSERT current state
   - `load(session_id) -> Optional[dict]` — read state from DB
   - `load_all() -> Dict[str, dict]` — bulk load for startup
   - `close()` — clean shutdown
5. Use WAL journal mode for read concurrency
6. All writes wrapped in transactions

### T2: Add configurable DB path to plugin config

**Goal**: DB path comes from plugin config, not hardcoded.

**Steps**:
1. Update `register(ctx)` to read config: `ctx.get_config("tps_counter", {}).get("db_path", default_path)`
2. Default path: `~/.hermes/plugins/tps-counter/tps.db` (create parent dirs)
3. Create `store.py`'s `PersistentSessionStore` instance during `register()`
4. Store the instance in a module-level `_STORE` variable
5. Pass store reference through to `_get_session` and `_on_post_api_request`

### T3: Integrate persistence into existing session management

**Goal**: Wire store into read/write paths.

**Steps**:
1. Modify `_get_session(session_id)`:
   - Check `_SESSIONS` dict first (fast path)
   - If missing, check `_STORE.load(session_id)`
   - If found in DB, populate `_SESSIONS[session_id]` and return
   - If not found anywhere, create new `_SessionTPS()` as before
2. Modify `_SessionTPS.record()`:
   - After updating in-memory state, call `_STORE.save(session_id, self)`
   - Keep the state lock held during both writes for consistency
3. Add `_on_session_end` hook integration (optional) for final flush

### T4: Add graceful degradation when DB unavailable

**Goal**: Plugin works identically to current behavior if SQLite fails.

**Steps**:
1. Wrap all `_STORE` operations in try/except
2. On any DB error, log warning and set `_STORE = None`
3. All code paths check `_STORE is not None` before DB operations
4. Verify: kill the DB file permissions → plugin still works in-memory
5. Add a `_STORE_AVAILABLE` flag for explicit tracking

### T5: Write persistence-specific tests

**Goal**: Verify data survives simulated restarts.

**Steps**:
1. Create `tests/test_persistence.py`
2. Test: save → close → reopen → load returns correct data
3. Test: in-memory state and DB state stay in sync
4. Test: graceful degradation when DB path is invalid
5. Test: concurrent writes don't corrupt data
6. Test: schema migration from version 0 to current
7. Use tmpdir fixture for isolated DB per test

### T6: Run full test suite and verify no regressions

**Goal**: All existing + new tests pass.

**Steps**:
1. `cd /home/ryan/repos/hermes-tps-counter && python -m pytest tests/ -v`
2. Verify: test_api.py, test_hook.py, test_session_tps.py still pass
3. Verify: test_persistence.py passes
4. Check no import errors or circular dependencies
5. Write completion evidence

## Context Capsule

**For the implementer**:
- Plugin entry: `register(ctx)` in `__init__.py`
- Session state: `_SessionTPS` class at line 23
- Hook: `_on_post_api_request` at line 108
- Session lookup: `_get_session` at line 101
- Thread lock: `_STATE_LOCK` at line 19
- Global dict: `_SESSIONS` at line 20
- Her gotcha: hermes_cli module is mocked in tests — don't break that pattern
- Plugin config access: `ctx.get_config("tps_counter", {})` — check if this API exists in Hermes, fallback to `ctx.config.get("tps_counter", {})`
- DB default path: create `~/.hermes/plugins/tps-counter/` directory if needed
