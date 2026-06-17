# Plan: FastAPI REST API to Expose TPS Metrics

## Wave 1: API Module (parallel-safe, no existing code changes)

### Task 1: Create `api.py` with FastAPI app and endpoints
- **File:** `api.py` (new)
- Create FastAPI app with `create_app(store: PersistentSessionStore) -> FastAPI`
- Implement 4 endpoints: health, session TPS, all sessions, summary
- Add CORS middleware
- Pydantic models for response schemas
- **Verification:** Import succeeds, `create_app` returns a FastAPI instance

### Task 2: Write API tests
- **File:** `tests/test_api.py` (new)
- Use `fastapi.testclient.TestClient` for each endpoint
- Test: health returns ok, session stats match saved data, all sessions returns correct count, summary aggregates correctly
- Test: 404 for nonexistent session
- Test: empty DB returns empty list/zero summary
- **Verification:** `pytest tests/test_api.py -v` passes

## Wave 2: Integration (requires Wave 1)

### Task 3: Integrate API startup into `register()`
- **File:** `__init__.py` (modify)
- Read `api.enabled`, `api.host`, `api.port` from plugin config
- If enabled, import `create_app` from `api.py` and start uvicorn in daemon thread
- Store server reference for clean shutdown
- Add `close()` method or hook to stop the server
- **Verification:** Manual test — register with `api.enabled: true`, curl returns 200

### Task 4: Update tests for integration path
- **File:** `tests/test_api.py` (extend)
- Test register() with api config starts server thread
- Test register() without api config does NOT start server
- Test graceful degradation when fastapi not installed
- **Verification:** `pytest tests/ -v` all green

## Dependencies

- Wave 2 depends on Wave 1
- Tasks 1 and 2 are parallel within Wave 1
- Task 3 and 4 are sequential within Wave 2

## Context Capsule

- Store: `PersistentSessionStore` at `store.py` — provides `load(session_id)`, `load_all()`
- Plugin entry: `register(ctx)` in `__init__.py` — add API startup here
- Config shape: `ctx.get_config("tps_counter", {})` returns dict with `db_path`, add `api.enabled`, `api.host`, `api.port`
- Existing pattern: plugin uses daemon thread for background work (same approach for API)
- FastAPI/uvicorn are optional deps — `from api import create_app` must not crash plugin if missing
