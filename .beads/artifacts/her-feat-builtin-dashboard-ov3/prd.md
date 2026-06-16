---
purpose: Product Requirements Document for a bead
updated: 2026-06-17
---

# PRD: Add built-in TPS dashboard HTML page served at root path for real-time monitoring without external tools

**Bead:** her-feat-builtin-dashboard-ov3 | **Type:** feature | **Priority:** P2
**Created:** 2026-06-17 | **Estimate:** 60 minutes

## Problem

WHEN the optional TPS Counter FastAPI server is enabled THEN operators can only inspect live TPS data through raw JSON endpoints, WebSocket clients, `/docs`, or external tooling BECAUSE the API currently exposes REST and WebSocket primitives but no built-in browser dashboard at the root path.

**Who is affected?** Hermes users and operators running the tps-counter API locally who want real-time monitoring without installing Grafana, Prometheus UI, curl scripts, or custom WebSocket clients.
**Why now?** The project already has a REST API, `/ws/tps` real-time stream, diagnostics, and Prometheus metrics; a lightweight built-in dashboard makes those existing capabilities immediately usable and improves observability without adding dependencies.

## Scope

### In Scope
- Serve a lightweight HTML dashboard at `GET /` from the FastAPI app created by `api.create_app` when the API is enabled.
- Use vanilla HTML, CSS, and JavaScript only; the page must not depend on CDNs, package assets, or internet access after it is loaded.
- Consume the existing `/ws/tps` WebSocket stream for real-time TPS updates.
- Consume existing REST endpoints such as `/api/v1/summary`, `/api/v1/sessions`, `/api/v1/health`, `/api/v1/health/diagnostics`, and per-session trend/event endpoints as needed for initial state and fallback behavior.
- Display at least overall TPS/status, recent/session-level stats, model/provider breakdowns where data exists, and a compact sparkline or recent-value visualization.
- Auto-reconnect the WebSocket after disconnects and clearly show connection state.
- Gracefully degrade to REST polling when WebSocket connection is unavailable.
- Preserve existing `/docs`, `/openapi.json`, `/api/v1/*`, `/metrics`, and `/ws/tps` behavior.
- Add focused tests for root dashboard response, offline/no-CDN constraints, route compatibility, and WebSocket fallback hooks where practical.
- Document the dashboard in `README.md` alongside the existing REST API section.

### Out of Scope
- Implementing authentication, user management, or access control.
- Adding React, Vue, charting libraries, bundlers, npm assets, CDN links, or any new runtime dependency.
- Replacing Prometheus/Grafana workflows or changing `/metrics` semantics.
- Creating a multi-page application, persisted user preferences, or server-side template rendering.
- Changing the shape or status codes of existing REST/WebSocket APIs except to add the root dashboard route.
- Implementing historical export/import features beyond consuming currently available endpoint data.

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Serve a built-in dashboard at the API root path. | MUST | `GET /` returns HTTP 200 with `text/html` content containing the TPS dashboard, while `GET /docs` and existing API routes remain available. |
| 2 | Keep the dashboard dependency-free and offline-capable after load. | MUST | The returned HTML contains no external `<script src>`, `<link href>` CDN, external font, or remote asset dependency; all CSS/JS needed for the dashboard is embedded or served locally by the package. |
| 3 | Use existing live data channels. | MUST | The dashboard JavaScript connects to `/ws/tps` for real-time updates and does not introduce a new streaming endpoint. |
| 4 | Provide REST fallback and initial state loading. | MUST | The dashboard can fetch existing `/api/v1/summary`, `/api/v1/sessions`, and health/diagnostics endpoints for initial render and can poll REST if WebSocket is unavailable. |
| 5 | Show useful monitoring information. | MUST | The page displays connection/API health, aggregate TPS/total call/token information, session rows or cards, recent TPS history/sparkline, and model/provider breakdowns when endpoint data provides them. |
| 6 | Reconnect automatically after WebSocket disconnect. | SHOULD | Client-side code visibly marks the connection as disconnected and retries with a bounded/backoff delay without requiring manual refresh. |
| 7 | Be responsive and accessible enough for local operations. | SHOULD | Layout is readable on mobile and desktop widths, uses semantic headings/labels, and does not rely on color alone for critical state. |
| 8 | Preserve existing API contracts. | MUST | Existing tests for health, sessions, summary, events, trends, diagnostics, metrics, and WebSocket behavior continue to pass; the dashboard route does not shadow `/api/v1/*`, `/metrics`, `/docs`, or `/ws/tps`. |
| 9 | Keep packaging simple. | SHOULD | Dashboard content is either a small `dashboard.py` module/string or a single package-local HTML asset loaded by `api.py`, with no build step. |
| 10 | Add tests and documentation for the new root dashboard. | MUST | `tests/test_dashboard.py` or equivalent covers the root HTML route and README explains how to enable and open the dashboard. |

## Technical Context

Key files:
- `api.py`: builds the FastAPI app in `create_app(store, get_diagnostics=None)`, configures CORS, registers `/api/v1/health`, `/api/v1/sessions/{session_id}/tps`, `/api/v1/sessions`, `/api/v1/summary`, `/api/v1/events/{session_id}`, `/api/v1/trends/{session_id}`, `/api/v1/health/diagnostics`, `/metrics`, and WebSocket `/ws/tps`.
- `tests/test_api.py`: verifies current REST endpoint behavior and `register()` API startup behavior.
- `tests/test_websocket.py`: verifies `ConnectionManager`, `broadcast_tps_update`, and `/ws/tps` connection behavior.
- `README.md`: documents plugin behavior, API enablement, endpoint list, and operational usage.

Existing bead context allows implementation in `api.py`, `dashboard.py`, `tests/test_dashboard.py`, and `README.md`; it forbids bead DB, local env/credential files, and planning artifacts for implementation work. This repair pass only writes create-phase artifacts under `.beads/artifacts/her-feat-builtin-dashboard-ov3/`.

Current API users enable the server via `TPS_COUNTER_API_ENABLED=1` or `[api] enabled = true` in TOML, then interact with the FastAPI server on the configured host/port. The root path is not currently documented as an endpoint, so it is available for a human-facing dashboard without disrupting versioned API routes.

## Approach

Add a root HTML route inside `api.create_app` that returns a small dependency-free dashboard page. Prefer keeping the dashboard markup/script in a separate `dashboard.py` module with a `DASHBOARD_HTML` constant or renderer so `api.py` remains focused on API wiring. The JavaScript should establish a WebSocket connection to `/ws/tps`, update visible aggregate/session values as `tps_update` messages arrive, and fetch REST endpoints for initial state plus fallback polling. Use simple inline CSS and lightweight DOM updates rather than external frameworks or a build pipeline.

Testing should instantiate the existing FastAPI app with `TestClient`, assert `GET /` returns HTML with expected dashboard markers, verify no remote asset references are present, and smoke-check that existing route tests remain compatible. Documentation should add a short "Dashboard" section explaining that when the API is enabled users can open `http://<host>:<port>/` for live monitoring.

**Alternatives considered:** A separate static frontend build was rejected because it would add npm/build dependencies and violate the offline/no-external-tools goal. Redirecting `/` to `/docs` was rejected because OpenAPI docs do not provide real-time TPS monitoring. Adding a new dashboard-specific data endpoint was rejected for the create scope because existing REST and WebSocket APIs already expose the necessary data.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Root route unintentionally shadows existing FastAPI docs or API routes. | Low | High | Register only `GET /` and test `/docs`, `/api/v1/health`, `/metrics`, and `/ws/tps` still resolve as before. |
| Inline dashboard grows large and makes `api.py` hard to maintain. | Med | Med | Keep HTML/CSS/JS in `dashboard.py` or a single local asset and keep `api.py` route wiring minimal. |
| Browser JavaScript assumes fields not always present in REST/WebSocket payloads. | Med | Med | Defensive parsing, defaults for missing data, and tests/fixtures covering empty-store responses. |
| WebSocket reconnection can create tight retry loops. | Med | Med | Use bounded/backoff retry delays and visible connection state. |
| Offline requirement is accidentally broken by a CDN/font/link. | Low | Med | Add tests that reject `http://`, `https://`, CDN script/link tags, and external font references in returned HTML. |
| Dashboard polling increases SQLite read load. | Med | Low | Keep fallback polling interval conservative and prefer WebSocket updates when connected. |

## Tasks (for epics)

| Task | Depends On | Parallel | Files |
|------|-----------|----------|-------|
| N/A — single feature bead. | N/A | N/A | N/A |

## Success Criteria

- [ ] `GET /` serves the built-in dashboard as HTML from the FastAPI app.
    - Verify: `python -m pytest tests/test_dashboard.py -k root`
- [ ] Dashboard HTML is dependency-free and contains no CDN or external asset references.
    - Verify: targeted assertions in `tests/test_dashboard.py`
- [ ] Dashboard client code uses `/ws/tps` for real-time updates and existing `/api/v1/*` REST endpoints for initial/fallback data.
    - Verify: targeted HTML/JS marker assertions in `tests/test_dashboard.py`
- [ ] Existing API, docs, metrics, and WebSocket routes are not regressed.
    - Verify: `python -m pytest tests/test_api.py tests/test_websocket.py tests/test_dashboard.py`
- [ ] README documents how to open the dashboard after enabling the API.
    - Verify: README contains a dashboard section with the root URL and API enablement context.
