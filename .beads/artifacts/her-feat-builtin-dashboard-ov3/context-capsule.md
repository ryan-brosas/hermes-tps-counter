---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-feat-builtin-dashboard-ov3

## Objective

Serve a lightweight, dependency-free HTML dashboard at `GET /` from the TPS Counter FastAPI app so operators can monitor TPS in real-time via WebSocket without installing external tools.

## Key Patterns

- `ConnectionManager` — Thread-safe WebSocket manager in `api.py` (lines 31–90). Broadcasts JSON to all connected clients. Dashboard JS must connect to `/ws/tps` and handle `tps_update` messages. Reference: `api.py`
- `create_app(store, get_diagnostics=None)` — FastAPI app factory in `api.py`. All routes registered inside this function. New `GET /` route goes here. Reference: `api.py`
- `TestClient` pattern — Tests use `from fastapi.testclient import TestClient` with a mock store fixture. Follow `tests/test_api.py` conventions for `test_dashboard.py`. Reference: `tests/test_api.py`
- `DASHBOARD_HTML` constant — HTML string stored in `dashboard.py`, imported by `api.py`. Keeps api.py focused on routing. Reference: `dashboard.py` (new)
- `PersistentSessionStore` — SQLite-backed store providing session data. REST endpoints read from it. Dashboard JS fetches `/api/v1/summary` and `/api/v1/sessions` which read from this store. Reference: `store.py`

## Constraints

1. **Zero external dependencies:** Dashboard HTML must contain no `https://` URLs in `<script src>` or `<link href>` tags. All CSS/JS inline. No CDNs, no Google Fonts, no external assets. Tests enforce this.
2. **No route shadowing:** `GET /` must not intercept `/api/v1/*`, `/docs`, `/openapi.json`, `/metrics`, or `/ws/tps`. Register dashboard route AFTER all other routes in `create_app()`.
3. **Existing tests must pass:** `tests/test_api.py` and `tests/test_websocket.py` are regression gates. Do not modify their fixtures or assertions.
4. **WebSocket protocol:** Dashboard JS connects to `ws://` (or `wss://`) `/ws/tps` and receives JSON messages with `type: "tps_update"`. Use `JSON.parse` defensively.
5. **REST fallback:** When WebSocket disconnects, poll `/api/v1/summary` every 5 seconds. Show connection state indicator (connected/disconnected/reconnecting).
6. **No build step:** `dashboard.py` is a plain Python module with a string constant. No npm, no bundler, no template engine.
7. **File isolation:** Only modify `api.py`, `dashboard.py`, `tests/test_dashboard.py`, `README.md`. Do not touch `store.py`, `__init__.py`, `prometheus_metrics.py`, or any other file.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Dashboard HTML module | `dashboard.py` — create new file with `DASHBOARD_HTML` constant | `api.py` — do not embed HTML in api.py |
| API route wiring | `api.py` — add import and `GET /` route in `create_app()` | `store.py`, `__init__.py` — no changes |
| Dashboard tests | `tests/test_dashboard.py` — create new test file | `tests/test_api.py`, `tests/test_websocket.py` — read-only, do not modify |
| Documentation | `README.md` — add dashboard section | `.pi/`, `.beads/` — no changes |

## Graph Context

- **Blast radius:** Low. Isolated node (degree 0), no downstream dependents. Safe to proceed without coordination.
- **Related beads:** `her-feat-historical-tps-export-s3i` runs on a parallel track — independent, no conflicts.
- **File history:** Hotspots are `tests/test_prometheus.py`, `README.md`, `__init__.py`, `prometheus_metrics.py` (3 beads each, all closed). Dashboard bead touches only `README.md` from this set; edit is additive (new section), no conflict risk.

## Key Endpoints Referenced by Dashboard JS

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ws/tps` | WebSocket | Real-time TPS updates (JSON `tps_update` messages) |
| `/api/v1/summary` | GET | Aggregate TPS, total calls, tokens |
| `/api/v1/sessions` | GET | List of active sessions with stats |
| `/api/v1/health` | GET | API health status |
| `/api/v1/health/diagnostics` | GET | Detailed diagnostics |

## Verification Checklist

- `python -c "from dashboard import DASHBOARD_HTML; print(len(DASHBOARD_HTML))"` — importable
- `python -m pytest tests/test_dashboard.py -v` — all dashboard tests pass
- `python -m pytest tests/test_api.py tests/test_websocket.py -v` — no regressions
- `grep -c "https://" <(python -c "from dashboard import DASHBOARD_HTML; print(DASHBOARD_HTML)")` — returns 0
