---
purpose: Agent spawn context for a bead
updated: 2026-06-16
---

# Context Capsule: her-feat-health-diagnostics-endpoint-o3m

## Objective

Add `GET /api/v1/health/diagnostics` endpoint in `api.py` that returns JSON with component-level status for memory, SQLite, Prometheus, WebSocket, and health counters — wired via a callback pattern to avoid circular imports.

## Key Patterns

- `create_app(store)` — Existing app factory in `api.py`. Add `get_diagnostics=None` parameter. Reference: `api.py`
- `get_diagnostics callback` — Callable passed from `__init__.py` to `api.py` at app creation. Returns `{sessions: list, models: dict, providers: dict, max_sessions: int}`. Avoids circular import (api.py never imports __init__.py). Reference: `api.py`, `__init__.py`
- `_STATE_LOCK` — Threading lock protecting `_SESSIONS`, `_MODELS`, `_PROVIDERS` in `__init__.py`. The callback must acquire this lock. Reference: `__init__.py`
- `metrics_available()` — Boolean check in `prometheus_metrics.py`. Use for Prometheus component status. Reference: `prometheus_metrics.py`
- `get_*_count()` — Counter accessor functions in `prometheus_metrics.py`. Call for health_counters component. Reference: `prometheus_metrics.py`
- `app.state.ws_manager` — `ConnectionManager` instance stored on app state. Use `.count` or equivalent for active connections. Reference: `api.py`
- `store.count()` — Returns session count from SQLite. Reference: `store.py` (read-only)
- Existing `/api/v1/health` route — MUST NOT be modified. New endpoint is additive. Reference: `api.py`

## Constraints

1. **No circular imports:** `api.py` MUST NOT import `__init__.py`. Use callback pattern only.
2. **No changes to out-of-scope files:** `store.py`, `config.py`, `prometheus_metrics.py` are read-only consumers. Only `api.py`, `__init__.py` (minimal wiring), `tests/test_api.py`, and `README.md` may be modified.
3. **Backward compatible:** Existing `GET /api/v1/health` endpoint behavior and response format must be identical. All existing tests must pass.
4. **Graceful degradation:** Each component collector is wrapped in try/except. A failing component returns `degraded` or `unavailable` status — the endpoint NEVER returns 500 due to a component failure.
5. **Thread-safe:** Memory reads use `_STATE_LOCK`. SQLite reads use store's internal locking. No shared mutable state created.
6. **Component status values:** Only `ok`, `degraded`, `unavailable` — no other strings.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Endpoint implementation | `api.py` — add route, callback param, collector functions | `store.py`, `config.py`, `prometheus_metrics.py` — read-only imports only |
| Callback wiring | `__init__.py` — add `_get_diagnostics_snapshot()` function, pass to `create_app()` | `__init__.py` — do NOT refactor existing state management |
| Tests | `tests/test_api.py` — add diagnostic endpoint test cases | `tests/` — do NOT modify existing test cases |
| Documentation | `README.md` — add diagnostics section | `README.md` — do NOT restructure existing content |

## Graph Context

- **Blast radius:** Low (risk_score=0). No other beads touch these files.
- **Related beads:** `her-feat-operational-health-metrics-3go` (upstream — provides the health counters this endpoint exposes). `her-feat-prometheus-histogram-metrics-z5z` (parallel track — no conflicts).
- **File history:** Fresh files — no prior bead history on `api.py` diagnostics code.
- **Dependencies:** None blocking. No upstream blockers, no downstream dependents.
