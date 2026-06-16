---
purpose: Decision log for a bead
updated: 2026-06-17
---

# Decisions: her-feat-api-rate-limiting-1p8

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Use in-process per-IP middleware for REST throttling. | Middleware consistently protects all REST endpoints before SQLite-backed handlers run and matches the plugin's local, single-process deployment model. | High |
| 2 | Use a stdlib sliding-window data structure keyed by client IP. | The bead explicitly forbids external dependencies and calls for simple `collections`-based tracking; a deque per IP is easy to prune and test. | High |
| 3 | Configure limits through `TPSConfig` as `requests_per_minute` and `burst_size`. | Existing config already centralizes API settings across defaults, TOML, env vars, and Hermes context overrides; adding fields there keeps operator configuration consistent. | High |
| 4 | Return HTTP 429 with `Retry-After` and JSON detail. | This is the expected HTTP contract for throttling and gives clients a deterministic retry signal without changing successful responses. | High |
| 5 | Exempt `/api/v1/health` from rate limiting. | Health checks should remain reliable during bursts so supervisors and users can distinguish throttling from process failure. | High |
| 6 | Add `tps_api_rate_limited_total` to the existing Prometheus registry with a no-op helper when unavailable. | Existing metrics code centralizes operational counters and gracefully degrades when `prometheus_client` is absent. | High |
| 7 | Keep proxy-aware IP parsing out of the initial feature. | The current API defaults to local usage; trusting forwarded headers without a trusted proxy model could create spoofing risk. | Med |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Add `slowapi` or another FastAPI rate-limit dependency. | Bead constraints explicitly prohibit new external dependencies and mention no slowapi. | Dependency churn and packaging failures for a small local plugin feature. |
| 2 | Use Redis or another shared backend for distributed limits. | The plugin uses local SQLite and runs as a local Hermes plugin; distributed throttling is out of scope. | Operational complexity and credentials/config burden disproportionate to the need. |
| 3 | Implement endpoint-by-endpoint decorators. | Duplicates policy across handlers and makes it easier to miss future endpoints. | Inconsistent protection and regressions when routes are added. |
| 4 | Rate limit `/api/v1/health`. | Liveness checks should remain available during high traffic and were explicitly called out for exemption support. | Supervisors may mark the API unhealthy because throttling hides basic process liveness. |
| 5 | Trust `X-Forwarded-For` by default. | The API has no trusted-proxy configuration, so forwarded headers can be spoofed. | Attackers can evade per-IP limits by rotating header values. |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | The REST API is primarily local or single-process, matching the current `api.create_app` and daemon-thread startup pattern. | Validated by code defaults: `api_host` is `127.0.0.1`, `api_enabled` defaults false, and no multi-process coordination exists. | A future multi-process deployment would need shared-state or proxy-layer rate limiting. |
| 2 | `request.client.host` is sufficient for the initial per-IP identity. | Unknown until deployed behind any proxy; acceptable for local/default use. | Proxy deployments may see all clients as the proxy IP or require trusted-forwarded-header support. |
| 3 | Health endpoint exemption should apply to `/api/v1/health` only, not diagnostics. | Validated by endpoint roles: diagnostics can inspect SQLite/Prometheus and is heavier than basic liveness. | If operators depend on diagnostics as a health probe, exemption scope may need expansion. |
| 4 | Prometheus may be absent, so metrics increments must remain no-op safe. | Validated by existing `prometheus_metrics.py` optional import pattern. | Direct metric access without no-op guards would break environments without `prometheus_client`. |
| 5 | Tests can be deterministic by injecting or monkeypatching the limiter time source rather than using sleeps. | Unknown until implementation, but compatible with a small helper class/function. | Wall-clock tests could become flaky and slow. |
