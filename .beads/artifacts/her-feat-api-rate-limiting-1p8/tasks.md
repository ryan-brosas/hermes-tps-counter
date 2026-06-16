---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-feat-api-rate-limiting-1p8

## Task Metadata

```yaml
id: "1.1"
depends_on: []
parallel: true
conflicts_with: []
files: ["config.py", "tests/test_config.py"]
estimated_minutes: 15
```

## 1. Foundation (Wave 1 — parallel)

### 1.1 Add rate limit fields to TPSConfig

```yaml
depends_on: []
parallel: true
files: ["config.py", "tests/test_config.py"]
```

- [ ] Add `requests_per_minute: int = 60` and `burst_size: int = 10` fields to `TPSConfig` dataclass.
- [ ] Add `REQUESTS_PER_MINUTE` and `BURST_SIZE` to `_ENV_FIELD_MAP` for env var loading (`TPS_COUNTER_REQUESTS_PER_MINUTE`, `TPS_COUNTER_BURST_SIZE`).
- [ ] Extend `_load_from_toml` to read from flat keys and nested `[api]` section (`rate_limit.requests_per_minute`, `rate_limit.burst_size`).
- [ ] Extend `_load_from_ctx` to read `requests_per_minute` and `burst_size` from direct keys and nested `api` section.
- [ ] Extend `_validate` to clamp `requests_per_minute` to minimum 1 and `burst_size` to minimum 1, with warning logs.
- [ ] Add tests in `tests/test_config.py`: defaults, env override, TOML flat, TOML nested `[api]`, ctx override, validation clamping for zero/negative values.

### 1.2 Add rate-limited request counter to Prometheus metrics

```yaml
depends_on: []
parallel: true
files: ["prometheus_metrics.py"]
```

- [ ] Add `_rate_limited_total` module-level variable (Any, initially None).
- [ ] In `_init_metrics`, create `Counter("tps_api_rate_limited_total", "Total requests rejected by rate limiting", registry=REGISTRY)`.
- [ ] Add `increment_rate_limited()` helper function following existing pattern (check `_PROMETHEUS_AVAILABLE`, check counter is not None, call `.inc()`).
- [ ] Ensure `reset_metrics()` resets the counter via `_init_metrics()`.
- [ ] Verify no external dependencies added.

## 2. Core Implementation (Wave 2 — parallel)

### 2.1 Implement sliding-window rate limiter middleware

```yaml
depends_on: ["1.1", "1.2"]
parallel: true
files: ["api.py"]
```

- [ ] Create a `RateLimitMiddleware` class (subclass Starlette `BaseHTTPMiddleware`) inside or near `create_app`.
- [ ] Accept `requests_per_minute` and `burst_size` as constructor params.
- [ ] Resolve client key from `request.client.host` (fallback to `"unknown"` if None).
- [ ] Maintain a `dict[str, deque[float]]` mapping IP → timestamps of recent requests.
- [ ] On each request: prune timestamps outside the 60-second window; if remaining count >= `requests_per_minute + burst_size`, return 429 with `Retry-After` header and JSON `{"detail": "Rate limit exceeded", "retry_after": <seconds>}`.
- [ ] Exempt `/api/v1/health` from rate limiting (check `request.url.path`).
- [ ] On allowed requests, append current timestamp to the deque and call `call_next`.
- [ ] Clean up empty IP entries after pruning to bound memory.
- [ ] Log throttled requests at DEBUG level with client IP and retry timing.
- [ ] Call `increment_rate_limited()` on throttled requests.
- [ ] Use an injectable time source (defaulting to `time.time`) so tests can advance time deterministically.

### 2.2 Wire middleware into create_app

```yaml
depends_on: ["2.1"]
parallel: false
files: ["api.py"]
```

- [ ] Import `get_config` in `create_app` (or accept config as optional param).
- [ ] Instantiate `RateLimitMiddleware` with config values and add to the app via `app.add_middleware(RateLimitMiddleware, ...)` after CORS middleware.
- [ ] Ensure middleware is added before endpoint registration so it intercepts requests first.

## 3. Testing (Wave 3)

### 3.1 Write comprehensive rate limiting tests

```yaml
depends_on: ["2.2"]
parallel: false
files: ["tests/test_rate_limiting.py"]
```

- [ ] Create `tests/test_rate_limiting.py` with fixtures: temp store, app with low rate limit config (e.g., 2 requests/min, burst=1), TestClient.
- [ ] Test allowed requests: 2 requests succeed with 200 (within limit).
- [ ] Test throttled requests: 3rd request returns 429 with `Retry-After` header and JSON detail.
- [ ] Test health exemption: send requests to exhaust limit, then hit `/api/v1/health` — must return 200.
- [ ] Test config loading: create app with custom `requests_per_minute`/`burst_size`, verify limits applied.
- [ ] Test stale cleanup: advance time past window, verify new requests are allowed again.
- [ ] Test Prometheus metric: send throttled request, verify `tps_api_rate_limited_total` incremented (or gracefully absent if prometheus_client not installed).
- [ ] Test existing endpoints preserve contracts: verify `/api/v1/health`, `/api/v1/summary`, `/api/v1/sessions` return expected shapes when under limit.

## 4. Verification (Wave 4)

### 4.1 Full test suite passes

```yaml
depends_on: ["3.1"]
parallel: false
```

- [ ] `python -m pytest tests/test_api.py tests/test_config.py tests/test_rate_limiting.py tests/test_prometheus.py -x -q`
- [ ] No new external dependencies in any modified file.
- [ ] All existing tests continue to pass (no regressions).
