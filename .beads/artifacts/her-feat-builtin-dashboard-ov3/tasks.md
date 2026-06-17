---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-feat-builtin-dashboard-ov3

## Task Metadata

```yaml
id: "1.1"
depends_on: []
parallel: true
conflicts_with: []
files: ["dashboard.py"]
estimated_minutes: 25
```

## 1. Dashboard HTML Module

### 1.1 Create `dashboard.py` with embedded HTML/CSS/JS

```yaml
depends_on: []
parallel: false
files: ["dashboard.py"]
estimated_minutes: 25
```

- [ ] Create `dashboard.py` at repo root with a `DASHBOARD_HTML` string constant.
- [ ] Embed all CSS inline (no external `<link>` or CDN fonts). Use a clean, responsive layout with semantic headings.
- [ ] Embed all JavaScript inline (no external `<script src>`).
- [ ] JS connects to `/ws/tps` via WebSocket for real-time `tps_update` messages.
- [ ] JS fetches `/api/v1/summary` and `/api/v1/sessions` on load for initial state.
- [ ] JS fetches `/api/v1/health/diagnostics` for connection/API health display.
- [ ] Implement auto-reconnect with exponential backoff (1s, 2s, 4s, max 30s) on WebSocket disconnect; show connection state indicator.
- [ ] Implement REST polling fallback (every 5s) when WebSocket is unavailable.
- [ ] Display: connection status badge, aggregate TPS/token/call counts, session rows with per-session TPS, sparkline of recent TPS values (last 30 data points, canvas-based), model/provider breakdown table.
- [ ] Defensive parsing: use optional chaining / defaults for missing fields in REST and WebSocket payloads.
- [ ] Responsive layout: readable on 320px–1920px viewport widths.
- [ ] Verify: `python -c "from dashboard import DASHBOARD_HTML; assert len(DASHBOARD_HTML) > 1000; assert 'http://' not in DASHBOARD_HTML and 'https://' not in DASHBOARD_HTML.split('ws://')[0]"`

## 2. API Route Wiring

### 2.1 Add `GET /` route in `api.py`

```yaml
depends_on: ["1.1"]
parallel: false
files: ["api.py"]
estimated_minutes: 10
```

- [ ] Import `DASHBOARD_HTML` from `dashboard` module in `api.py`.
- [ ] Add `GET /` route inside `create_app()` that returns `HTMLResponse(DASHBOARD_HTML)`.
- [ ] Use `from fastapi.responses import HTMLResponse` (already imported `Response`; add `HTMLResponse`).
- [ ] Ensure the route is registered AFTER all `/api/v1/*`, `/docs`, `/metrics`, and `/ws/tps` routes to avoid shadowing.
- [ ] Verify: existing tests still pass: `python -m pytest tests/test_api.py tests/test_websocket.py -x`

## 3. Dashboard Tests

### 3.1 Add `tests/test_dashboard.py`

```yaml
depends_on: ["2.1"]
parallel: false
files: ["tests/test_dashboard.py"]
estimated_minutes: 20
```

- [ ] Create `tests/test_dashboard.py` using the existing `TestClient` pattern from `tests/test_api.py`.
- [ ] Test: `GET /` returns HTTP 200 with `Content-Type: text/html`.
- [ ] Test: response body contains dashboard markers (`TPS Dashboard`, `/ws/tps`, `/api/v1/summary`).
- [ ] Test: response body contains NO external CDN references — assert no `https://` in `<script src` or `<link href` tags, no `cdn.`, no `fonts.googleapis.com`.
- [ ] Test: `GET /docs` still returns 200 (route not shadowed).
- [ ] Test: `GET /api/v1/health` still returns 200 (route not shadowed).
- [ ] Test: `GET /api/v1/summary` still returns 200 (route not shadowed).
- [ ] Test: response body contains WebSocket reconnect logic markers (e.g., `reconnect`, `backoff`, `setInterval` or `setTimeout`).
- [ ] Test: response body contains REST fallback markers (e.g., `fetch.*summary` or `polling`).
- [ ] Verify: `python -m pytest tests/test_dashboard.py -v`

## 4. Documentation

### 4.1 Update `README.md` with dashboard section

```yaml
depends_on: ["2.1"]
parallel: true
files: ["README.md"]
estimated_minutes: 5
```

- [ ] Add a "Dashboard" subsection under the existing API/REST section in README.
- [ ] Explain: when API is enabled (`TPS_COUNTER_API_ENABLED=1` or `[api] enabled = true`), open `http://<host>:<port>/` in a browser for live TPS monitoring.
- [ ] Note: dashboard uses WebSocket for real-time updates, falls back to REST polling if WebSocket unavailable.
- [ ] Note: zero external dependencies — works offline after page load.
- [ ] Verify: `grep -q "Dashboard" README.md && grep -q "GET /" README.md`

## 5. Final Verification

### 5.1 All tests pass, no regressions

```yaml
depends_on: ["3.1", "4.1"]
parallel: false
files: []
estimated_minutes: 5
```

- [ ] `python -m pytest tests/test_api.py tests/test_websocket.py tests/test_dashboard.py -v` — all pass.
- [ ] `python -m pytest tests/ -v` — full suite passes with no regressions.
