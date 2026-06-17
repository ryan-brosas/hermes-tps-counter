---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-feat-builtin-dashboard-ov3

**Goal:** Serve a built-in, dependency-free HTML dashboard at `GET /` so operators can monitor TPS in real-time via WebSocket without external tools.

## Graph Context

- **Blast radius:** Low — isolated node with no downstream dependents. `bv --robot-impact` reports zero affected beads.
- **Unblocks:** None downstream. `her-feat-historical-tps-export-s3i` is parallel-safe on a separate track.
- **Blocked by:** None. Chain length = 0, root blocker list empty.
- **Critical path:** No. Bead has slack = 1 and is not on the critical path (all nodes have critical_path_score = 1).
- **Forecast:** 85 minutes (low confidence due to sparse velocity data). Capacity simulation: serial 85 min, parallel 85 min (single-bead scope). 2 open issues, both independent.

## Observable Truths

What must be TRUE for the goal to be achieved:

1. `GET /` returns HTTP 200 with `text/html` containing a TPS dashboard when the FastAPI app is running.
2. The returned HTML contains zero external `<script src>`, `<link href>`, CDN, or remote font references — all CSS/JS is inline or locally served.
3. Dashboard JavaScript connects to `/ws/tps` for real-time updates and fetches `/api/v1/summary`, `/api/v1/sessions`, `/api/v1/health` for initial state.
4. WebSocket auto-reconnect with bounded backoff is present; connection state is visible to the user.
5. REST polling fallback activates when WebSocket is unavailable.
6. `GET /docs`, `GET /api/v1/health`, `GET /metrics`, and `/ws/tps` continue to resolve correctly — the root route does not shadow them.
7. `tests/test_dashboard.py` passes and covers: root response, no-CDN constraint, route compatibility, and fallback markers.
8. `README.md` contains a dashboard section explaining enablement and the root URL.

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Dashboard HTML module | Self-contained HTML/CSS/JS string constant | `dashboard.py` | Need |
| API route wiring | `GET /` route in `create_app` | `api.py` (edit) | Need |
| Dashboard tests | Root route, no-CDN, route compat, fallback markers | `tests/test_dashboard.py` | Need |
| README section | Documentation of dashboard usage | `README.md` (edit) | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | Create `dashboard.py` with `DASHBOARD_HTML` constant | Yes (single task, no deps) | PRD approved | Module importable, HTML string non-empty |
| 2 | Wire `GET /` route in `api.py` | No | Wave 1 complete | `GET /` returns 200 with HTML |
| 3 | Add `tests/test_dashboard.py` | No | Wave 2 complete | `pytest tests/test_dashboard.py` passes |
| 4 | Update `README.md` with dashboard section | Yes (parallel with Wave 3) | Wave 2 complete | README contains dashboard section |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
python -m pytest tests/test_dashboard.py -v
python -m pytest tests/test_api.py tests/test_websocket.py tests/test_dashboard.py -v
grep -q "Dashboard" README.md
```
