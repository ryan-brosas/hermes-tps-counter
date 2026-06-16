---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-feat-api-rate-limiting-1p8

**Goal:** Add per-IP rate limiting middleware to REST API endpoints so burst requests cannot overwhelm the SQLite backend.

## Graph Context

- **Blast radius:** `api.py`, `config.py`, `prometheus_metrics.py`, `tests/test_api.py`, `tests/test_config.py`, `tests/test_rate_limiting.py` (new). No existing beads share open work on these files.
- **Unblocks:** None directly. Enables safer future API features.
- **Blocked by:** None (root node, depth=0).
- **Critical path:** No. All slack=1, no articulation points.
- **Forecast:** ~85 minutes. Confidence 0.35 (velocity is low for this label).

## Observable Truths

1. Burst requests from one IP to protected REST endpoints receive HTTP 429 with `Retry-After` header before reaching SQLite-backed handler logic.
2. Under-limit requests from the same IP pass through unchanged — existing API response contracts are preserved.
3. `/api/v1/health` returns liveness info even when the same client is otherwise over limit.
4. `TPSConfig` exposes `requests_per_minute` and `burst_size` with defaults, TOML, env, and ctx override loading plus validation.
5. Prometheus exposes `tps_api_rate_limited_total` counter incremented by rate-limited requests.
6. Stale per-IP entries are pruned after their request windows expire — no unbounded memory growth.

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Config fields | Rate limit configuration plumbing | `config.py` | Need |
| Prometheus counter | Rate-limited request observation | `prometheus_metrics.py` | Need |
| Rate limit middleware | Per-IP sliding window enforcement | `api.py` | Need |
| Rate limiting tests | Behavioral verification | `tests/test_rate_limiting.py` | Need |
| Config tests update | New field coverage | `tests/test_config.py` | Need |
| API tests update | Existing endpoint regression check | `tests/test_api.py` | Verify |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | 1.1 Config fields, 1.2 Prometheus counter | Yes | PRD exists, codebase readable | `python -m pytest tests/test_config.py tests/test_prometheus.py -x` |
| 2 | 2.1 Rate limit middleware, 2.2 Wire middleware into create_app | Yes | Wave 1 complete | `python -m pytest tests/test_api.py -x` |
| 3 | 3.1 Rate limiting tests | No | Wave 2 complete | `python -m pytest tests/test_rate_limiting.py -x` |
| 4 | 4.1 Full verification | No | Wave 3 complete | `python -m pytest tests/test_api.py tests/test_config.py tests/test_rate_limiting.py tests/test_prometheus.py` |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
python -m pytest tests/test_config.py -x -q
python -m pytest tests/test_api.py -x -q
python -m pytest tests/test_rate_limiting.py -x -q
python -m pytest tests/test_api.py tests/test_config.py tests/test_rate_limiting.py tests/test_prometheus.py -x -q
```
