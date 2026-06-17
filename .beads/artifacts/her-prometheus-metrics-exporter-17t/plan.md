---
purpose: Wave-sequenced implementation plan
updated: 2026-06-16
---

# Plan: her-prometheus-metrics-exporter-17t

**Goal:** Add a Prometheus-compatible `/metrics` endpoint that exposes TPS data in standard exposition format, enabling Grafana and other Prometheus-compatible monitoring tools to scrape TPS metrics.

## Graph Context

- **Blast radius:** `__init__.py`, `api.py`, `tests/test_prometheus.py` (new)
- **Unblocks:** Grafana dashboards, Prometheus alerting, external observability stack
- **Blocked by:** None (leaf node)
- **Critical path:** No — standalone feature, no downstream beads depend on it
- **Forecast:** ~85 minutes (estimate 60m × feature 1.3 × depth 1.1)
- **Risk:** Low — stable dependency structure, isolated feature addition

## Observable Truths

1. `GET /metrics` returns HTTP 200 with `Content-Type: text/plain; version=0.0.4; charset=utf-8` and response body containing `# HELP` and `# TYPE` lines
2. After recording 2 API calls via the hook, `tps_last_call` and `tps_avg` gauge values match the expected TPS calculations
3. `tps_tokens_total{direction="output"}` counter value equals the session's total_output_tokens
4. Per-model metrics (e.g., `tps_model_avg{model="openai/gpt-4o"}`) and per-provider metrics (e.g., `tps_provider_avg{provider="openai"}`) appear with correct labels
5. Plugin works without `prometheus_client` installed — `/metrics` returns 503 or is not mounted
6. All existing tests pass (`pytest tests/ -v` — 0 failures)

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Prometheus module | Metric definitions, registry, update functions | `prometheus_metrics.py` | Need |
| API endpoint | `/metrics` route on FastAPI app | `api.py` (modify) | Need |
| Hook integration | Update metrics in `_on_post_api_request` | `__init__.py` (modify) | Need |
| Tests | Full coverage of metrics endpoint and updates | `tests/test_prometheus.py` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | T1: Create prometheus_metrics.py | No | None | Module imports without error |
| 2 | T2: Wire metrics into hook, T3: Add /metrics to API | Yes (parallel) | Wave 1 complete | `pytest tests/test_prometheus.py -v` |
| 3 | T4: Config integration | No | Wave 2 complete | `pytest tests/ -v` (all pass) |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Delegation Packets

### Packet 1: Core metrics module (Wave 1)
```
Task: Create prometheus_metrics.py with custom CollectorRegistry, all metric definitions, and update_metrics() function
Files: prometheus_metrics.py (new)
Pattern: Follow store.py style — module-level state, thread-safe, try/except import
Reference: prd.md requirements 1-6, decisions.md D1-D6
```

### Packet 2a: Hook integration (Wave 2)
```
Task: Import and call update_metrics() in _on_post_api_request inside existing _STATE_LOCK block
Files: __init__.py (modify _on_post_api_request)
Pattern: Follow existing _persist_state() call pattern — inline, under lock, wrapped in try/except
Reference: __init__.py lines ~200-220 (existing hook body)
```

### Packet 2b: API endpoint (Wave 2)
```
Task: Add /metrics route to create_app() that calls generate_metrics() from prometheus_metrics module
Files: api.py (modify create_app)
Pattern: Follow existing endpoint pattern — FastAPI route, error handling, graceful degradation
Reference: api.py health endpoint pattern, prd.md requirement 8
```

### Packet 3: Config integration (Wave 3)
```
Task: Add prometheus.enabled config option to register(), conditionally enable metric updates
Files: __init__.py (modify register)
Pattern: Follow existing api.enabled config pattern
Reference: __init__.py register() function
```

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
pytest tests/test_prometheus.py -v          # New tests pass
pytest tests/ -v                            # All existing tests still pass
python -c "from prometheus_metrics import REGISTRY; print('OK')"  # Module imports
```
