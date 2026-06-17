---
purpose: Task decomposition with dependency tracking
updated: 2026-06-16
---

# Tasks: her-her-readme-api-ws-prom-config-6y0

## Task Metadata

```yaml
id: "1.1"
depends_on: []
parallel: true
conflicts_with: []
files: ["README.md"]
estimated_minutes: 45
```

## 1. Document REST API

### 1.1 Write REST API section

```yaml
depends_on: []
parallel: true
files: ["README.md"]
```

- [ ] Document all 7 endpoints: `/api/v1/health`, `/api/v1/sessions`, `/api/v1/sessions/{id}/tps`, `/api/v1/summary`, `/api/v1/events/{id}`, `/api/v1/trends/{id}`, `/metrics`
- [ ] Include HTTP method, path, query params, and example JSON response for each
- [ ] Note CORS is wide-open for local development

### 1.2 Write WebSocket section

```yaml
depends_on: []
parallel: true
files: ["README.md"]
```

- [ ] Document `/ws/tps` endpoint with connection URL
- [ ] Document message envelope format: `{"type": "tps_update", "data": {...}, "timestamp": "..."}`
- [ ] Include fields in `data` object: session_id, last_tps, avg_tps, peak_tps, output_tokens, input_tokens, total_tokens, call_count
- [ ] Note client sends no messages; server pushes on each LLM call

### 1.3 Write Prometheus section

```yaml
depends_on: []
parallel: true
files: ["README.md"]
```

- [ ] Document how to enable: `TPS_COUNTER_PROMETHEUS_ENABLED=1` or TOML `[prometheus] enabled = true`
- [ ] List all 9 metrics in a table:
  - `tps_last_call` (gauge, labels: session_id)
  - `tps_avg` (gauge, labels: session_id)
  - `tps_peak` (gauge, labels: session_id)
  - `tps_tokens_total` (counter, labels: session_id, direction)
  - `tps_api_calls_total` (counter, labels: session_id)
  - `tps_model_avg` (gauge, labels: session_id, model)
  - `tps_model_peak` (gauge, labels: session_id, model)
  - `tps_provider_avg` (gauge, labels: session_id, provider)
  - `tps_provider_peak` (gauge, labels: session_id, provider)
- [ ] Note: requires `prometheus_client` package

### 1.4 Write Configuration section

```yaml
depends_on: []
parallel: true
files: ["README.md"]
```

- [ ] Document merge precedence: defaults < TOML < env vars < ctx overrides
- [ ] Document TOML config file location: `~/.hermes/plugins/tps-counter/config.toml`
- [ ] Document all 7 fields in a table:
  - `max_sessions` (int, default 50, `TPS_COUNTER_MAX_SESSIONS`)
  - `db_path` (str, default `~/.hermes/plugins/tps-counter/tps.db`, `TPS_COUNTER_DB_PATH`)
  - `retention_days` (int, default 7, `TPS_COUNTER_RETENTION_DAYS`)
  - `api_host` (str, default `127.0.0.1`, `TPS_COUNTER_API_HOST`)
  - `api_port` (int, default 9127, `TPS_COUNTER_API_PORT`)
  - `prometheus_enabled` (bool, default false, `TPS_COUNTER_PROMETHEUS_ENABLED`)
  - `api_enabled` (bool, default false, `TPS_COUNTER_API_ENABLED`)
- [ ] Provide example TOML config snippet
- [ ] Provide example env var usage

## 2. Integration

### 2.1 Insert sections into README.md

```yaml
depends_on: ["1.1", "1.2", "1.3", "1.4"]
parallel: false
files: ["README.md"]
```

- [ ] Insert after existing "Supported Provider Usage Formats" section
- [ ] Keep "No Configuration Required" section but update to reference new config section
- [ ] Ensure consistent heading levels and style with existing README

## 3. Verification

### 3.1 Verify all sections present

```yaml
depends_on: ["2.1"]
parallel: false
files: ["README.md"]
```

- [ ] `grep -c '/api/v1/' README.md` returns >= 6
- [ ] `grep 'ws/tps' README.md` finds WebSocket section
- [ ] `grep -c 'tps_' README.md` in Prometheus section returns >= 9
- [ ] `grep -c 'TPS_COUNTER_' README.md` returns >= 7
