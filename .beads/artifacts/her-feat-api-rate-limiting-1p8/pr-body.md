## Summary

Adds lightweight in-process per-IP rate limiting to the optional FastAPI REST API so burst requests are rejected before SQLite-backed handlers perform work. This protects local dashboard/metrics usage and the shared SQLite backend from read-heavy request bursts while preserving health/liveness behavior.

## What Changed

- Added `RateLimitMiddleware` using stdlib `deque` timestamp windows keyed by `request.client.host`.
- Wired middleware into `create_app` with `/api/v1/health` exempted.
- Added `TPSConfig.requests_per_minute` and `TPSConfig.burst_size` with defaults, env, TOML, context, and validation support.
- Added Prometheus counter helper for `tps_api_rate_limited_total`.
- Added focused tests for allowed/throttled requests, store short-circuiting, health exemption, stale cleanup, config loading, and Prometheus exposure.

## Acceptance Criteria

- [x] Burst requests from one IP to protected REST endpoints receive HTTP 429 with Retry-After before handler/store work — `tests/test_rate_limiting.py` verifies throttling and store short-circuiting.
- [x] Under-limit requests preserve existing REST response contracts — `tests/test_api.py` and under-limit rate-limit tests passed.
- [x] TPSConfig supports `requests_per_minute` and `burst_size` via defaults, TOML, env, context, and validation — `tests/test_config.py` passed.
- [x] `/api/v1/health` remains exempt from throttling — dedicated health exemption test passed.
- [x] Prometheus exposes `tps_api_rate_limited_total` after throttled requests when available — dedicated metrics test passed.
- [x] No external dependencies introduced and affected tests pass — implementation uses stdlib plus existing FastAPI/Starlette/Prometheus patterns.

## Review

**Verdict:** APPROVE
**Findings:** Critical 0, High 0, Medium 0, Low 0

## Verification

- `br lint her-feat-api-rate-limiting-1p8 --json` — PASS
- `python -m pytest tests/test_api.py tests/test_config.py tests/test_rate_limiting.py tests/test_prometheus.py -x -q` — PASS, 119 passed
- `git diff --check` — PASS

## Changed Files

Bead-scoped implementation/test files:

- `api.py`
- `config.py`
- `prometheus_metrics.py`
- `tests/test_config.py`
- `tests/test_rate_limiting.py`
- `.beads/issues.jsonl`
- `.beads/artifacts/her-feat-api-rate-limiting-1p8/*`

## Artifacts

- PRD: `.beads/artifacts/her-feat-api-rate-limiting-1p8/prd.md`
- Plan: `.beads/artifacts/her-feat-api-rate-limiting-1p8/plan.md`
- Evidence: `.beads/artifacts/her-feat-api-rate-limiting-1p8/completion-evidence.json`
- Review: `.beads/artifacts/her-feat-api-rate-limiting-1p8/review-report.md`

## Br Bead

- Bead: `her-feat-api-rate-limiting-1p8`
- Status: closed
- Priority: P2
