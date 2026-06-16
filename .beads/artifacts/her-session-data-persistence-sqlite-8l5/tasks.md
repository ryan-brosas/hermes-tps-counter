# Tasks: her-session-data-persistence-sqlite-8l5

## Task 1: Create store.py with SQLite schema and PersistentSessionStore class

**File:** `store.py` (new file at plugin root)
**Action:**
1. Create `store.py` with `PersistentSessionStore` class
2. Define `session_tps` table schema: session_id TEXT PRIMARY KEY, call_count INT, total_output_tokens INT, total_duration REAL, peak_tps REAL, last_call_tps REAL, avg_tps REAL, updated_at TEXT
3. Add `schema_version` table (version INT)
4. Implement: `__init__(db_path)`, `save(session_id, state)`, `load(session_id)`, `load_all()`, `close()`
5. Use `PRAGMA journal_mode=WAL` on connection init
6. All writes in transactions with `INSERT OR REPLACE`

**Verification:** `python -c "from store import PersistentSessionStore; print('import ok')"` from plugin root
**Parallel:** No
**Depends on:** None

## Task 2: Add configurable DB path to plugin config

**File:** `__init__.py`
**Action:**
1. In `register(ctx)`, read DB path from config: `ctx.get_config("tps_counter", {}).get("db_path", default_path)` with fallback to `ctx.config.get("tps_counter", {})` if get_config doesn't exist
2. Default path: `~/.hermes/plugins/tps-counter/tps.db`
3. Create parent dirs with `os.makedirs(..., exist_ok=True)`
4. Instantiate `PersistentSessionStore(db_path)` as module-level `_STORE`
5. Add `import os` and `from store import PersistentSessionStore` at top

**Verification:** Read register() function — verify config reading and store instantiation present
**Parallel:** Yes (with Task 1)
**Depends on:** None

## Task 3: Integrate persistence into existing session management

**File:** `__init__.py`
**Action:**
1. Modify `_get_session(session_id)`: check `_SESSIONS` first, then `_STORE.load(session_id)`, populate `_SESSIONS` from DB hit, else create new
2. Modify `_SessionTPS.record()`: after in-memory update, call `_STORE.save(session_id, self)` (or do it in `_on_post_api_request` after `state.record()` to keep the class pure)
3. All DB access wrapped in `if _STORE is not None:` guard
4. Keep `_STATE_LOCK` held during combined memory+DB writes

**Verification:** Create session, record data, verify DB has the row via direct sqlite3 query
**Parallel:** No
**Depends on:** Task 1, Task 2

## Task 4: Add graceful degradation when DB unavailable

**File:** `__init__.py`, `store.py`
**Action:**
1. Wrap all `_STORE` calls in try/except in `_get_session` and `_on_post_api_request`
2. On DB exception: `logger.warning("tps-counter: DB unavailable, falling back to in-memory: %s", exc)` and set `_STORE = None`
3. Verify plugin behavior is identical to current when `_STORE is None`

**Verification:** Set DB path to `/nonexistent/path/db.db`, run plugin, verify it still records TPS in-memory
**Parallel:** No
**Depends on:** Task 3

## Task 5: Write persistence-specific tests

**File:** `tests/test_persistence.py` (new file)
**Action:**
1. Create `tests/test_persistence.py`
2. Test save-load roundtrip: save state, close store, reopen, load — verify all fields match
3. Test sync: in-memory `_SESSIONS` and DB have same data after record()
4. Test degradation: invalid DB path → plugin still works (in-memory fallback)
5. Test concurrent writes: use threading to write from 4 threads, verify no corruption
6. Test schema creation: fresh DB gets correct tables
7. Use `tmp_path` pytest fixture for isolated DB per test

**Verification:** `python -m pytest tests/test_persistence.py -v` — all pass
**Parallel:** Yes (with Task 4)
**Depends on:** Task 3

## Task 6: Run full test suite and verify no regressions

**File:** Repo root
**Action:**
1. `cd /home/ryan/repos/hermes-tps-counter && python -m pytest tests/ -v`
2. Verify all tests pass (test_api.py, test_hook.py, test_session_tps.py, test_persistence.py)
3. Check for import errors: `python -c "import __init__"`
4. Write completion evidence to `.beads/artifacts/her-session-data-persistence-sqlite-8l5/completion-evidence.json`

**Verification:** Full pytest output shows 0 failures
**Parallel:** No
**Depends on:** Task 4, Task 5
