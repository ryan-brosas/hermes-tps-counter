---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-feat-api-rate-limiting-1p8

## Objective

Add per-IP sliding-window rate limiting middleware to FastAPI REST endpoints so burst requests get HTTP 429 before reaching SQLite-backed handlers, while preserving existing behavior for under-limit and health check requests.

## Key Patterns

- `BaseHTTPMiddleware` — Use Starlette's `BaseHTTPMiddleware` for the rate limiter. FastAPI/Starlette are already dependencies; do NOT add slowapi, redis, or any new package. Reference: `api.py` (existing CORS middleware pattern).
- `collections.deque` — Use as the sliding-window timestamp buffer per IP. Bounded, O(1) append/popleft. Reference: stdlib only.
- `prometheus_client.Counter` pattern — Follow existing `_init_metrics()` / `increment_*()` / `reset_metrics()` pattern for the new `tps_api_rate_limited_total` counter. Reference: `prometheus_metrics.py` (lines 164-188 for operational health counters, lines 343-406 for increment helpers).
- `TPSConfig` dataclass field pattern — Add new fields with defaults, extend `_ENV_FIELD_MAP`, extend TOML/ctx loaders, extend `_validate()` for clamping. Reference: `config.py` (lines 46-72 for fields, 228-238 for validate).
- `TestClient` fixture pattern — Use `fastapi.testclient.TestClient` with temp `PersistentSessionStore`. Reference: `tests/test_api.py` (lines 25-51).
- Injectable time source — Pass `time_fn` (default `time.time`) to the middleware constructor so tests can use `monkeypatch` or a controllable clock to avoid wall-clock flakiness.

## Constraints

1. Do not add external dependencies. Implementation uses only stdlib (`collections.deque`, `time`, `logging`) plus existing FastAPI/Starlette/prometheus_client.
2. `/api/v1/health` MUST be exempt from rate limiting — supervisors and liveness probes depend on it.
3. Return HTTP 429 with `Retry-After` header and JSON body `{"detail": "Rate limit exceeded", "retry_after": <seconds>}` for throttled requests.
4. Do not change successful response schemas or status codes for under-limit requests.
5. Stale per-IP entries must be pruned to prevent unbounded memory growth.
6. Log rate-limit events at DEBUG level only — no request bodies or secrets in logs.
7. Existing tests in `tests/test_api.py`, `tests/test_config.py`, `tests/test_prometheus.py` must continue to pass with no modifications unless explicitly needed for new config field coverage.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Config fields | `config.py` — add dataclass fields, env map, loader extensions, validation | `.beads/beads.db` — database |
| Prometheus counter | `prometheus_metrics.py` — add counter, increment helper, reset | `.env.local` — credentials |
| Rate limit middleware | `api.py` — add middleware class, wire into `create_app` | `plan.md`, `tasks.md`, `context-capsule.md` — planning artifacts |
| Rate limiting tests | `tests/test_rate_limiting.py` — new file for all rate limit behavioral tests | `tests/test_api.py` — only touch if regression demands it |
| Config tests | `tests/test_config.py` — add tests for new fields | `store.py` — no changes needed |

## Graph Context

- **Blast radius:** 6 files (all in allowed list). No open beads touch these files.
- **Related beads:** None (isolated root node in dependency graph).
- **File history:** `prometheus_metrics.py` has been touched by 3 closed beads (hotspot). Approach with awareness of existing metric patterns. `api.py` and `config.py` have not been modified by other open beads.
