# Decisions: her-prometheus-metrics-exporter-17t

## Decision Log

### D1: Use prometheus_client library vs. custom text format
**Decision:** Use `prometheus_client` Python library
**Rationale:** Canonical Prometheus client for Python. Handles metric registration, text format serialization, HELP/TYPE metadata, and CollectorRegistry isolation. Custom text format would be fragile and reinvent the wheel.
**Rejected alternative:** Custom text formatter — error-prone, no room for future Histogram/Summary support.

### D2: Custom CollectorRegistry vs. default global registry
**Decision:** Use a custom `CollectorRegistry` instance, not the global `REGISTRY`
**Rationale:** Prevents metric name collisions with other plugins or applications using prometheus_client. Isolates TPS metrics cleanly.
**Rejected alternative:** Global registry — simpler but risks collisions in multi-plugin setups.

### D3: Mount on existing FastAPI app vs. standalone server
**Decision:** Mount `/metrics` route on existing FastAPI app when API is enabled
**Rationale:** No additional port, no additional thread, single config surface. Users already configure the API port. If API is not enabled, `/metrics` is not available (acceptable tradeoff).
**Rejected alternative:** Standalone HTTP server — more config, more complexity, another port to manage.

### D4: Optional dependency (graceful degradation)
**Decision:** Import `prometheus_client` with try/except. If unavailable, skip metric registration and return 503 from `/metrics`.
**Rationale:** `prometheus_client` is not a core dependency. Users who don't need Prometheus integration shouldn't be forced to install it. Matches the existing pattern (FastAPI/uvicorn are optional for the REST API).
**Rejected alternative:** Required dependency — forces installation even when not needed.

### D5: Update metrics in existing hook vs. separate background thread
**Decision:** Update metrics inline in `_on_post_api_request` alongside existing state updates
**Rationale:** Gauge.set() and Counter.inc() in prometheus_client are sub-microsecond. No need for a separate thread. Keeps the code simple and ensures metrics are always in sync with state.
**Rejected alternative:** Background thread — unnecessary complexity, potential for stale metrics.

### D6: Metric naming convention
**Decision:** Prefix all metrics with `tps_` (e.g., `tps_last_call`, `tps_tokens_total`)
**Rationale:** Clear namespace, avoids collision with other Prometheus metrics. Follows Prometheus naming convention: `unit_suffix` for gauges, `_total` suffix for counters.
**Rejected alternative:** No prefix — risks collision with system or application metrics.

## Assumptions

1. `prometheus_client` is available via pip if the user wants it — no special installation needed
2. The existing FastAPI app is sufficient for serving `/metrics` (no need for a separate ASGI app)
3. Session label cardinality is bounded by MAX_SESSIONS (50) — acceptable for Prometheus
4. Per-call event metrics (from event storage bead) are out of scope — this bead only exposes aggregate session/model/provider metrics

## Open Questions

1. Should we expose the `_prometheus_registry` for advanced users who want to add custom collectors? (Answer: yes, as a module-level attribute)
2. Should metric labels include the full model string or just the model name? (Answer: full string for consistency with existing API)
