# PRD: FastAPI REST API to Expose TPS Metrics

## Problem

The TPS counter plugin collects rich per-session metrics (last TPS, avg TPS, peak TPS, total tokens, call counts, durations) and persists them to SQLite — but all this data is only accessible via in-process Python calls (`get_tps_stats(session_id)`). There is no HTTP interface, despite the project stack explicitly including FastAPI and the vision being a "monitoring dashboard." Without an API, external dashboards, status pages, and tooling cannot consume TPS data.

## Scope

**In scope:**
- FastAPI application module (`api.py`) that exposes TPS metrics over HTTP
- Endpoints for single-session stats, all-sessions listing, and health check
- Integration with existing `PersistentSessionStore` (SQLite) for data source
- CORS middleware for dashboard consumption
- Configurable host/port via plugin config
- Tests for all endpoints

**Out of scope:**
- WebSocket/SSE real-time streaming (future bead)
- Authentication/rate limiting (future bead)
- Dashboard HTML/JS frontend (future bead)
- Prometheus metrics export format (future bead)

## Requirements

1. **GET /api/v1/health** — returns `{"status": "ok", "db": "connected"|"disconnected"}`
2. **GET /api/v1/sessions/{session_id}/tps** — returns TPS stats for a single session (same shape as `get_tps_stats()`)
3. **GET /api/v1/sessions** — returns all sessions with their TPS stats (uses `load_all()`)
4. **GET /api/v1/summary** — returns aggregated summary: total sessions, total calls, total tokens, average TPS across all sessions
5. Server starts as a background thread from `register()` when `api.enabled: true` in plugin config
6. Graceful shutdown when `close()` is called or plugin unloads
7. All endpoints return JSON with consistent error shapes on failure
8. CORS enabled by default (allow all origins for local dev; configurable later)

## Approach

- Single new file: `api.py` containing the FastAPI app factory and endpoint definitions
- Modify `register()` in `__init__.py` to optionally start the API server in a daemon thread
- Use `uvicorn.Server` with manual `serve()` call in a thread (avoids subprocess complexity)
- API reads directly from `PersistentSessionStore` (passed as dependency)
- Add `fastapi` and `uvicorn` as optional dependencies (graceful import failure)
- Tests use `TestClient` from `fastapi.testclient` (no real server needed)
