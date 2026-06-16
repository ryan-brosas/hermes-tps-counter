# hermes-tps-counter

Hermes Agent plugin that tracks tokens-per-second (TPS) throughput and displays it in the status bar.

## What It Does

- Hooks into `post_api_request` to capture input/output tokens and API duration after each LLM call
- Maintains per-session stats: last TPS, rolling average, peak TPS, total input/output/total tokens
- Injects TPS data into the Hermes status bar: `⚕ glm-5.1 │ ⚡114 tok/s │ 20.2K/202.8K │ [█░░░░░░░░░] 10% │ 1m │ ⏲ 28s │ ✓ 4s`

## Install

```bash
# Copy plugin to Hermes plugins directory
cp -r . ~/.hermes/plugins/tps-counter/

# Restart Hermes to load the plugin
```

## Status Bar Integration

The plugin exposes TPS data via `agent._tps_snapshot` which the status bar reads. This requires small patches to the Hermes agent codebase:

### 1. `hermes_cli/__init__.py` — Add active CLI instance global

```python
# At the bottom of the file:
_ACTIVE_CLI_INSTANCE = None
```

### 2. `cli.py` — Register CLI instance on startup

After `cli = HermesCLI(...)`:

```python
try:
    import hermes_cli
    hermes_cli._ACTIVE_CLI_INSTANCE = cli
except Exception:
    pass
```

### 3. `cli.py` — Inject TPS into status bar snapshot

In `_get_status_bar_snapshot()`, before `return snapshot`:

```python
# Inject TPS data from plugins (e.g. tps-counter)
tps = getattr(agent, "_tps_snapshot", None)
if tps:
    tps_val = tps.get("last_tps", 0)
    if tps_val > 0:
        snapshot["tps_last"] = tps_val
        snapshot["tps_avg"] = tps.get("avg_tps", 0)
        snapshot["tps_label"] = f"⚡{tps_val:.0f} tok/s"
    else:
        snapshot["tps_label"] = ""
else:
    snapshot["tps_label"] = ""
```

### 4. `cli.py` — Render TPS in status bar fragments

In `_get_status_bar_fragments()`, wide variant (>=76 cols), after the model_short fragment:

```python
tps_label = snapshot.get("tps_label", "")
if tps_label:
    frags.append(("class:status-bar-strong", tps_label))
    frags.append(("class:status-bar-dim", " │ "))
```

For medium variant (52-75 cols), same but with `" · "` separator.

## API

```python
from tps_counter import get_tps_stats, get_model_stats

# Session-level stats
stats = get_tps_stats(session_id)
# {"calls": 5, "avg_tps": 98.7, "last_tps": 114.0, "peak_tps": 456.2,
#  "total_output_tokens": 12345, "total_input_tokens": 45000,
#  "total_tokens": 57345, "total_duration": 125.3}

# Per-model stats (new)
model_stats = get_model_stats(session_id)
# {"gpt-4o": {"avg_tps": 120.5, "peak_tps": 456.2, "calls": 3, "total_output_tokens": 8000, "total_duration": 66.4},
#  "claude-sonnet": {"avg_tps": 78.3, "peak_tps": 95.1, "calls": 2, "total_output_tokens": 4345, "total_duration": 55.5}}
```

### Per-Model Tracking

When switching models mid-session, per-model stats prevent cross-model pollution. Each model's `avg_tps` and `peak_tps` are tracked independently. Model data is automatically included in `_tps_snapshot["models"]` for status bar integration.

### Session Lifecycle

The plugin automatically manages session state to prevent unbounded memory growth:

- **Event-driven cleanup:** When a session ends (via the `on_session_end` hook), all in-memory state for that session is removed immediately.
- **LRU eviction:** As a safety net for sessions that don't trigger `on_session_end` (e.g., process killed), the plugin evicts the least-recently-active session when the total exceeds `MAX_SESSIONS` (default: 50). Eviction targets the session with the oldest `turn_start_time`.
- **Session duration:** `get_tps_stats` returns a `session_duration` field (seconds since session creation) alongside existing metrics.

Both cleanup paths are fully thread-safe via the existing `_STATE_LOCK`.

## No Configuration Required

Works out of the box. No env vars or config needed. All features below are optional — the plugin tracks TPS in-memory and displays it in the status bar with zero configuration.

## REST API

When enabled, the plugin starts a FastAPI server exposing TPS data over HTTP. Enable it with:

```bash
export TPS_COUNTER_API_ENABLED=1
```

Or in TOML (see [Configuration](#configuration)):

```toml
[api]
enabled = true
```

The API runs on `127.0.0.1:9127` by default. FastAPI auto-generates interactive docs at `/docs` when the server is running.

### Dashboard

When the API is enabled, open `http://<host>:<port>/` (for the default local server: `http://127.0.0.1:9127/`) to view the built-in TPS Dashboard. The dashboard is served by `GET /` and provides live aggregate TPS, total calls/tokens, API health, recent TPS history, session-level rows, and model/provider breakdowns when that data is available.

The page uses the existing `/ws/tps` WebSocket stream for real-time updates and fetches `/api/v1/summary`, `/api/v1/sessions`, `/api/v1/health`, and `/api/v1/health/diagnostics` for initial state. If the WebSocket is unavailable or disconnects, it automatically reconnects with backoff and falls back to REST polling. All CSS and JavaScript are embedded in the page; there are no CDN, font, or external asset dependencies, so it works offline after loading from the local API server.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Health check — verify API and DB are reachable |
| `GET` | `/api/v1/health/diagnostics` | Comprehensive component-level health diagnostics |
| `GET` | `/api/v1/sessions` | List all sessions with TPS stats |
| `GET` | `/api/v1/sessions/{session_id}/tps` | TPS stats for a single session |
| `GET` | `/api/v1/summary` | Aggregated TPS summary across all sessions |
| `GET` | `/api/v1/events/{session_id}` | Per-call events for a session |
| `GET` | `/api/v1/trends/{session_id}` | Per-model and per-provider aggregated trends |
| `GET` | `/metrics` | Prometheus metrics (see [Prometheus](#prometheus)) |

### `GET /api/v1/health`

```json
{
  "status": "ok",
  "db": "connected"
}
```

### `GET /api/v1/health/diagnostics`

Comprehensive component-level health diagnostics. Returns status for all plugin subsystems in a single request. Use this when debugging plugin issues — it replaces the need to check multiple endpoints separately.

```json
{
  "status": "ok",
  "components": {
    "memory": {
      "status": "ok",
      "sessions": 3,
      "max_sessions": 50,
      "models": 5,
      "providers": 2
    },
    "sqlite": {
      "status": "ok",
      "connected": true,
      "session_count": 3,
      "event_count": 127,
      "retention_days": 7
    },
    "prometheus": {
      "status": "ok",
      "enabled": true,
      "available": true,
      "registered_collectors": 15
    },
    "websocket": {
      "status": "ok",
      "enabled": true,
      "active_connections": 2
    },
    "health_counters": {
      "status": "ok",
      "usage_extraction_failures": 0,
      "db_write_errors": 0,
      "db_read_errors": 0,
      "ws_broadcast_failures": 0,
      "ws_dead_clients": 0
    }
  },
  "timestamp": "2026-06-16T10:30:00+00:00"
}
```

**Status values:** `ok` — component healthy; `degraded` — component partially functional; `unavailable` — component not reachable.

**Backward compatibility:** The existing `GET /api/v1/health` endpoint is unchanged.

### `GET /api/v1/sessions`

Returns an array of all tracked sessions:

```json
{
  "sessions": [
    {
      "session_id": "abc123",
      "call_count": 15,
      "total_output_tokens": 12345,
      "total_input_tokens": 45000,
      "total_duration": 125.3,
      "peak_tps": 456.2,
      "last_call_tps": 114.0,
      "avg_tps": 98.7,
      "updated_at": "2026-06-16T10:30:00Z"
    }
  ]
}
```

### `GET /api/v1/sessions/{session_id}/tps`

Same response shape as a single session entry above. Returns `404` if the session is not found.

### `GET /api/v1/summary`

```json
{
  "total_sessions": 3,
  "total_calls": 47,
  "total_tokens": 573450,
  "average_tps": 102.5
}
```

### `GET /api/v1/events/{session_id}`

Query parameters:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `since` | string | — | ISO 8601 timestamp lower bound |
| `until` | string | — | ISO 8601 timestamp upper bound |
| `limit` | int | `100` | Max events to return |

```json
{
  "events": [
    {
      "id": 1,
      "session_id": "abc123",
      "model": "gpt-4o",
      "provider": "openai",
      "input_tokens": 1500,
      "output_tokens": 800,
      "duration": 2.3,
      "tps": 347.8,
      "created_at": "2026-06-16T10:30:00Z"
    }
  ]
}
```

### `GET /api/v1/trends/{session_id}`

Query parameters:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `since` | string | — | ISO 8601 timestamp lower bound |

```json
{
  "session_id": "abc123",
  "models": {
    "gpt-4o": { "avg_tps": 120.5, "peak_tps": 456.2, "calls": 3, "total_output_tokens": 8000, "total_duration": 66.4 }
  },
  "providers": {
    "openai": { "avg_tps": 120.5, "peak_tps": 456.2, "calls": 3, "total_output_tokens": 8000, "total_duration": 66.4 }
  }
}
```

> **Note:** CORS is wide-open (`*`) for local dashboard development. Not suitable for public-facing deployments without a reverse proxy.

## WebSocket

The API server also exposes a WebSocket endpoint for real-time TPS streaming.

**Endpoint:** `ws://127.0.0.1:9127/ws/tps`

The server pushes a JSON message after every LLM call. Clients do not send messages — the connection is receive-only.

### Message Format

```json
{
  "type": "tps_update",
  "data": {
    "session_id": "abc123",
    "last_tps": 114.0,
    "avg_tps": 98.7,
    "peak_tps": 456.2,
    "output_tokens": 12345,
    "input_tokens": 45000,
    "total_tokens": 57345,
    "call_count": 15
  },
  "timestamp": "2026-06-16T10:30:00.123456+00:00"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"tps_update"` |
| `data` | object | Session TPS snapshot (same fields as the REST session endpoint) |
| `timestamp` | string | ISO 8601 UTC timestamp of the broadcast |

### Example (JavaScript)

```javascript
const ws = new WebSocket("ws://127.0.0.1:9127/ws/tps");
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "tps_update") {
    console.log(`${msg.data.session_id}: ${msg.data.last_tps} tok/s`);
  }
};
```

Dead clients are automatically cleaned up. A slow client cannot block broadcasts to other clients.

## Prometheus

When enabled, the plugin exports metrics in Prometheus text exposition format at `/metrics`.

```bash
export TPS_COUNTER_PROMETHEUS_ENABLED=1
```

Or in TOML:

```toml
[prometheus]
enabled = true
```

Requires the `prometheus_client` Python package:

```bash
pip install prometheus_client
```

### Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `tps_last_call` | Gauge | `session_id` | TPS for the most recent API call |
| `tps_avg` | Gauge | `session_id` | Rolling average TPS for the session |
| `tps_peak` | Gauge | `session_id` | Peak TPS observed in this session |
| `tps_tokens_total` | Counter | `session_id`, `direction` | Total tokens processed (`direction`: `input` or `output`) |
| `tps_api_calls_total` | Counter | `session_id` | Total API calls recorded |
| `tps_model_avg` | Gauge | `session_id`, `model` | Average TPS for a specific model |
| `tps_model_peak` | Gauge | `session_id`, `model` | Peak TPS for a specific model |
| `tps_provider_avg` | Gauge | `session_id`, `provider` | Average TPS for a specific provider |
| `tps_provider_peak` | Gauge | `session_id`, `provider` | Peak TPS for a specific provider |
| `tps_distribution` | Histogram | `model` | Per-call TPS distribution with buckets `1`, `5`, `10`, `25`, `50`, `100`, `250`, `500`, `1000` tok/s for percentile queries |
| `api_call_latency_seconds` | Histogram | `model` | API latency distribution with buckets `0.1`, `0.25`, `0.5`, `1`, `2.5`, `5`, `10`, `30`, `60` seconds for percentile queries |

Histogram percentiles can be queried in Prometheus/Grafana with `histogram_quantile()`, for example:

```promql
histogram_quantile(0.95, sum by (le, model) (rate(tps_distribution_bucket[5m])))
histogram_quantile(0.99, sum by (le, model) (rate(api_call_latency_seconds_bucket[5m])))
```

The histogram `model` label is capped to protect Prometheus from unbounded cardinality; observations for model labels beyond the cap are discarded silently.

### Prometheus Scrape Config

```yaml
scrape_configs:
  - job_name: "tps-counter"
    static_configs:
      - targets: ["127.0.0.1:9127"]
    metrics_path: /metrics
```

## Configuration

The plugin works with zero configuration. All settings below are optional and have sensible defaults.

### Merge Precedence

Settings are resolved in this order (lowest to highest priority):

1. **Defaults** — built-in values in the plugin
2. **TOML file** — `~/.hermes/plugins/tps-counter/config.toml`
3. **Environment variables** — `TPS_COUNTER_*` prefix
4. **Context overrides** — Hermes plugin context (programmatic)

Higher-priority sources override lower ones.

### TOML Config File

Create `~/.hermes/plugins/tps-counter/config.toml`:

```toml
# Session tracking
max_sessions = 50
db_path = "~/.hermes/plugins/tps-counter/tps.db"
retention_days = 7

# REST API
[api]
enabled = true
host = "127.0.0.1"
port = 9127

# Prometheus
[prometheus]
enabled = true
```

### Environment Variables

All env vars use the `TPS_COUNTER_` prefix:

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `TPS_COUNTER_MAX_SESSIONS` | int | `50` | LRU eviction threshold for in-memory sessions |
| `TPS_COUNTER_DB_PATH` | string | `~/.hermes/plugins/tps-counter/tps.db` | Path to SQLite database file |
| `TPS_COUNTER_RETENTION_DAYS` | int | `7` | Days to retain call events before cleanup |
| `TPS_COUNTER_API_HOST` | string | `127.0.0.1` | REST API bind address |
| `TPS_COUNTER_API_PORT` | int | `9127` | REST API port |
| `TPS_COUNTER_PROMETHEUS_ENABLED` | bool | `false` | Enable Prometheus `/metrics` endpoint |
| `TPS_COUNTER_API_ENABLED` | bool | `false` | Enable REST API server |

Boolean env vars accept `1`, `true`, `yes`, or `on` (case-insensitive) as truthy values.

### Quick Start

Enable both the API and Prometheus with env vars:

```bash
export TPS_COUNTER_API_ENABLED=1
export TPS_COUNTER_PROMETHEUS_ENABLED=1
# Restart Hermes
```

Or with a single TOML file:

```toml
[api]
enabled = true

[prometheus]
enabled = true
```

## Supported Provider Usage Formats

The plugin extracts token counts from multiple provider formats automatically:

| Provider  | Output tokens key      | Input tokens key       |
|-----------|------------------------|------------------------|
| Anthropic | `usage.output_tokens`  | `usage.input_tokens`   |
| OpenAI    | `usage.completion_tokens` | `usage.prompt_tokens` |
| Google    | `usage.completionTokens` | `usage.promptTokens`  |

Fallback order: primary key is tried first, then alternatives. Unknown formats return 0 without crashing.
