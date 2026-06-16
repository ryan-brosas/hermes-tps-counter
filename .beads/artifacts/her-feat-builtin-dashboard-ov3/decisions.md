---
purpose: Decision log for a bead
updated: 2026-06-17
---

# Decisions: her-feat-builtin-dashboard-ov3

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Serve the dashboard at `GET /` from the existing FastAPI app. | Matches the bead title and gives operators an obvious browser entry point without changing versioned API paths. | High |
| 2 | Build the dashboard with vanilla HTML/CSS/JavaScript and no external assets. | The bead requires real-time monitoring without external tools and offline operation after load; avoiding dependencies also preserves simple plugin packaging. | High |
| 3 | Use `/ws/tps` for live updates and existing `/api/v1/*` endpoints for initial state/fallback. | Existing code already provides WebSocket broadcast support plus REST endpoints for health, sessions, summary, events, trends, and diagnostics; reusing them avoids duplicating backend data paths. | High |
| 4 | Prefer isolating dashboard markup/script in `dashboard.py` or a single package-local asset. | Keeps `api.py` maintainable while satisfying the constraint that HTML may be embedded as a Python string or single package file. | Med |
| 5 | Treat route compatibility and no-CDN checks as first-class test requirements. | The highest-risk regressions are accidentally shadowing existing FastAPI routes or violating the offline/no-dependency constraint. | High |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Add React/Vue/charting libraries or an npm build step. | Violates zero external dependencies and no-build simplicity for a local plugin dashboard. | Increases install complexity and may break offline operation. |
| 2 | Redirect `/` to `/docs`. | OpenAPI docs are useful for developers but do not provide purpose-built real-time TPS monitoring. | Users still need external/manual tooling to understand live TPS. |
| 3 | Require Prometheus/Grafana for dashboard visualization. | The bead explicitly targets monitoring without external tools. | Makes the feature unavailable to users who only enable the plugin API. |
| 4 | Add new dashboard-specific backend data endpoints before proving need. | Existing REST and WebSocket routes appear sufficient for initial dashboard behavior. | Expands API surface unnecessarily and increases maintenance/testing burden. |
| 5 | Serve dashboard assets from a CDN. | Breaks offline-after-load and dependency-free constraints. | Dashboard can fail in local/offline environments and introduces supply-chain exposure. |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | The root path `/` is currently unused by the API and can host the dashboard. | Validated by reading `api.py`; existing routes are under `/api/v1/*`, `/metrics`, `/ws/tps`, and FastAPI docs paths. | If another root route exists later, implementation must choose a non-conflicting path or merge behavior. |
| 2 | Existing REST endpoints provide enough data for initial dashboard state and fallback polling. | Validated by reading `api.py` and README endpoint list for summary, sessions, health, diagnostics, events, and trends. | Additional endpoint work may be needed if the dashboard requires data not exposed today. |
| 3 | WebSocket messages use the existing `tps_update` envelope emitted by `broadcast_tps_update`. | Validated by `tests/test_websocket.py` expectations around `broadcast_tps_update`. | Dashboard parsing must adapt if the broadcast envelope changes. |
| 4 | API enablement remains controlled by existing config (`TPS_COUNTER_API_ENABLED` or `[api] enabled = true`). | Validated by README and API integration tests. | Documentation and setup instructions must change if API startup config changes. |
| 5 | This create-phase repair should not implement code or generate plan/tasks artifacts. | Validated by the repair instructions for this pass. | Implementation, planning, and task decomposition must be handled by later workflow phases. |
