# Tasks: her-rest-api-tps-endpoints-56b

## Task 1: Create api.py with FastAPI app and endpoints
**File:** api.py (new)
**Action:** Create `api.py` with: (1) Pydantic response models for health, session stats, session list, summary. (2) `create_app(store)` factory that returns a configured FastAPI instance with CORS middleware. (3) Four endpoints: `GET /api/v1/health`, `GET /api/v1/sessions/{session_id}/tps`, `GET /api/v1/sessions`, `GET /api/v1/summary`. All endpoints read from the injected `PersistentSessionStore`.
**Verification:** `python3 -c "from api import create_app; print('OK')"` succeeds. Unit tests from Task 2 pass.
**Parallel:** Yes (with Task 2)
**Depends on:** None

## Task 2: Write API tests in tests/test_api.py
**File:** tests/test_api.py (new)
**Action:** Write tests using `fastapi.testclient.TestClient`: test health endpoint returns `{"status": "ok"}`, test session TPS returns correct data after saving to store, test all-sessions returns full list, test summary aggregates correctly, test 404 for missing session, test empty DB returns empty/zero.
**Verification:** `pytest tests/test_api.py -v` — all tests pass.
**Parallel:** Yes (with Task 1)
**Depends on:** None

## Task 3: Integrate API startup into register()
**File:** __init__.py (modify)
**Action:** In `register(ctx)`: (1) Read `api.enabled`, `api.host` (default `127.0.0.1`), `api.port` (default `9127`) from config. (2) If enabled, `import uvicorn` and `from api import create_app`, start `uvicorn.Server` in a daemon thread. (3) Store server reference in module-level `_API_SERVER` for shutdown. (4) In a new `close()` or existing teardown path, signal server shutdown.
**Verification:** Register with `api.enabled: true`, `curl http://127.0.0.1:9127/api/v1/health` returns 200 with `{"status": "ok"}`.
**Parallel:** No
**Depends on:** Task 1

## Task 4: Update tests for integration path
**File:** tests/test_api.py (extend)
**Action:** Add tests: (1) register() with `api.enabled: true` starts server thread (mock uvicorn). (2) register() without api config does NOT start server. (3) Import failure of fastapi/uvicorn is handled gracefully (plugin still works). (4) Existing tests still pass.
**Verification:** `pytest tests/ -v` — all tests pass including new and existing.
**Parallel:** No
**Depends on:** Task 2, Task 3
