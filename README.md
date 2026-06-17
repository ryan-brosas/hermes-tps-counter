# hermes-tps-counter

Hermes Agent plugin that tracks tokens-per-second (TPS) throughput after LLM calls and exposes it to status-bar and in-process observability consumers.

## What It Does

- Hooks into `post_api_request` to capture input/output tokens and API duration after each LLM call
- Maintains per-session stats: last TPS, rolling average, peak TPS, total input/output/total tokens
- Injects TPS data into the Hermes status bar: `⚕ glm-5.1 │ ⚡114 tok/s │ 20.2K/202.8K │ [█░░░░░░░░░] 10% │ 1m │ ⏲ 28s │ ✓ 4s`

## Quickstart: Install, Restart, Verify

From this repository checkout, copy the plugin into a Hermes plugins directory, restart Hermes, and trigger an LLM call:

```bash
# From the hermes-tps-counter repository root
mkdir -p ~/.hermes/plugins
rm -rf ~/.hermes/plugins/tps-counter
cp -R . ~/.hermes/plugins/tps-counter

# Restart Hermes so the plugin loader sees plugin.yaml and registers post_api_request.
# Then run a normal Hermes LLM interaction that produces output tokens.
```

Verification checklist:

1. Confirm the copied plugin contains `~/.hermes/plugins/tps-counter/plugin.yaml` with `name: tps-counter` and hook `post_api_request`.
2. Restart Hermes; look for a plugin-loader log line equivalent to `tps-counter plugin registered` if your runtime logs plugin registration.
3. Make a successful LLM call with output tokens and a positive API duration.
4. Verify TPS through one of the currently available in-process surfaces:
   - Status-bar integration reads `agent._tps_snapshot` on the active CLI agent once the status-bar patch points below are present.
   - Python consumers can call `get_tps_stats(session_id)` for the active session.

The plugin does not install a REST route, WebSocket stream, Prometheus exporter, package manager dependency, or standalone daemon on this branch.

## Status-Bar Integration

The plugin produces status-bar data, but Hermes core must still expose the active CLI instance and render the fragment. The expected flow is:

1. Hermes starts the CLI and stores the active CLI instance in `hermes_cli._ACTIVE_CLI_INSTANCE`.
2. The plugin receives `post_api_request` after a successful LLM call.
3. The plugin calculates TPS and assigns the latest privacy-treated payload to `agent._tps_snapshot` on that active CLI agent.
4. The status-bar snapshot builder copies safe TPS fields into its own render snapshot.
5. The fragment renderer shows a short label such as `⚡114 tok/s` only when the value is fresh, session-matched, and positive.

### Required Hermes Patch Points

#### 1. `hermes_cli/__init__.py` — active CLI instance global

```python
# At module scope:
_ACTIVE_CLI_INSTANCE = None
```

#### 2. `cli.py` — register the active CLI instance on startup

After `cli = HermesCLI(...)`:

```python
try:
    import hermes_cli
    hermes_cli._ACTIVE_CLI_INSTANCE = cli
except Exception:
    pass
```

#### 3. `cli.py` — copy TPS into the status-bar snapshot

In `_get_status_bar_snapshot()`, before `return snapshot`, consume `agent._tps_snapshot` defensively:

```python
import time

STALE_THRESHOLD_SECONDS = 60

tps = getattr(agent, "_tps_snapshot", None)
snapshot["tps_label"] = ""

if tps:
    age = time.monotonic() - tps.get("updated_monotonic", 0)
    session_match = tps.get("session_id") == active_session_id
    if age <= STALE_THRESHOLD_SECONDS and session_match:
        tps_val = tps.get("last_tps", 0)
        if tps_val > 0:
            snapshot["tps_last"] = tps_val
            snapshot["tps_avg"] = tps.get("avg_tps", 0)
            snapshot["tps_label"] = f"⚡{tps_val:.0f} tok/s"
```

If privacy mode pseudonymizes, redacts, or omits `session_id`, compare the active session identifier after applying the same policy described by `get_observability_contract()["privacy"]["field_treatments"]`; do not compare a raw active session id to a privacy-treated snapshot id.

#### 4. `cli.py` — render the TPS status fragment

In `_get_status_bar_fragments()`, add the label only when non-empty. For the wide variant (>=76 columns), place it after the model fragment:

```python
tps_label = snapshot.get("tps_label", "")
if tps_label:
    frags.append(("class:status-bar-strong", tps_label))
    frags.append(("class:status-bar-dim", " │ "))
```

For medium layouts (52-75 columns), use the same label with the existing medium separator style, such as `" · "`.

### Snapshot Fields

`agent._tps_snapshot` is the latest outbound status payload for one successful call. Current fields are:

| Field | Presence | Description |
|-------|----------|-------------|
| `last_tps` | Required | Unrounded TPS for the most recent successful API call: `output_tokens / api_duration`. |
| `avg_tps` | Required | Unrounded rolling average for the session: total output tokens / total API duration. |
| `peak_tps` | Required | Highest `last_tps` seen for the session. |
| `output_tokens` | Required | Cumulative output tokens recorded for the session. |
| `updated_at` | Required | Wall-clock `time.time()` timestamp for logging/diagnostics. Do not use it for robust age checks. |
| `updated_monotonic` | Required | `time.monotonic()` timestamp for stale-display checks. |
| `session_id` | Required unless omitted by privacy policy | Session that produced the snapshot; privacy mode may pseudonymize, redact, or omit it. |
| `model` | Optional | Present when the hook receives `model`; privacy mode may transform it. |
| `provider` | Optional | Present when the hook receives `provider`; privacy mode may transform it. |

Display rules for consumers:

- Show TPS only when `last_tps > 0`.
- Leave `tps_label` empty for missing snapshots, zero/negative TPS, stale snapshots, or session mismatches. This avoids misleading labels.
- Calculate age with `time.monotonic() - snapshot["updated_monotonic"]`; use a consumer-defined threshold, commonly 30-120 seconds.
- Suppress or gray-out values beyond that threshold.
- Ignore or clear the display when `snapshot["session_id"]` does not match the active session after applying the same privacy treatment policy.

## In-Process API Helper

Use `get_tps_stats(session_id)` for read-only session stats inside the same Python process:

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

When the API is enabled, open `http://127.0.0.1:9127/` (or your configured host/port) in a browser for a live TPS monitoring dashboard. The dashboard:

- Shows real-time TPS updates via WebSocket (`/ws/tps`)
- Displays aggregate stats (average TPS, total calls, total tokens, active sessions)
- Lists per-session TPS stats in a table
- Shows model and provider breakdowns
- Renders a sparkline of recent TPS values
- Falls back to REST polling (every 5 seconds) if WebSocket is unavailable
- Auto-reconnects WebSocket with exponential backoff on disconnect
- Works offline after page load — zero external dependencies (no CDNs, no remote fonts)

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Health check — verify API and DB are reachable |
| `GET` | `/api/v1/health/diagnostics` | Comprehensive component-level health diagnostics |
| `GET` | `/api/v1/sessions` | List all sessions with TPS stats |
| `POST` | `/api/v1/sessions/batch/tps` | TPS stats for multiple requested sessions |
| `GET` | `/api/v1/sessions/{session_id}/tps` | TPS stats for a single session |
| `POST` | `/api/v1/sessions/batch/tps` | TPS stats for multiple sessions in one request |
| `GET` | `/api/v1/summary` | Aggregated TPS summary across all sessions |
| `GET` | `/api/v1/events/{session_id}` | Per-call events for a session |
| `GET` | `/api/v1/trends/{session_id}` | Per-model and per-provider aggregated trends |
| `GET` | `/api/v1/export/history` | Bounded historical export for offline analysis |
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

### `POST /api/v1/sessions/batch/tps`

Returns TPS stats for a requested subset of sessions in one call. Duplicate IDs are normalized (first-seen order is preserved), and missing sessions are reported in `missing_session_ids` instead of failing the whole request. Empty `session_ids` or non-list input returns FastAPI/Pydantic validation error `422`.

Request:

```json
{
  "session_ids": ["abc123", "def456"]
}
```

Full-hit response:

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
    },
    {
      "session_id": "def456",
      "call_count": 8,
      "total_output_tokens": 6789,
      "total_input_tokens": 22000,
      "total_duration": 80.0,
      "peak_tps": 220.4,
      "last_call_tps": 85.0,
      "avg_tps": 84.9,
      "updated_at": "2026-06-16T10:31:00Z"
    }
  ],
  "missing_session_ids": []
}
```

Partial-miss response:

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
  ],
  "missing_session_ids": ["missing-session"]
}
```

### `GET /api/v1/sessions/{session_id}/tps`

Same response shape as a single session entry above. Returns `404` if the session is not found.

### `POST /api/v1/sessions/batch/tps`

Request TPS stats for multiple session IDs in a single HTTP request. Found sessions are returned in `sessions`; IDs not present in the store are listed in `missing_session_ids`. Duplicate IDs in the request are normalised (first-seen order preserved).

**Request:**

```json
{
  "session_ids": ["abc123", "def456", "ghost"]
}
```

**Response (partial hit):**

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
  ],
  "missing_session_ids": ["def456", "ghost"]
}
```

**Validation:** Empty `session_ids` list or non-list input returns `422`. Returns `503` if the database is unavailable.

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

### `GET /api/v1/export/history`

Bounded historical export for offline analysis and dashboard import. Returns session TPS summaries and per-call events as JSON (default) or CSV. Every request is explicitly bounded — no unbounded SQLite reads.

**Intended use:** Import into notebooks, spreadsheets, BI tools, or dashboard import flows. This endpoint is for local offline analysis, not remote public exposure.

Query parameters:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `session_id` | string | — | Filter to a specific session |
| `since` | string | — | ISO 8601 timestamp lower bound |
| `until` | string | — | ISO 8601 timestamp upper bound |
| `limit` | int | `100` | Max rows to return (capped at `max_limit`) |
| `max_limit` | int | `1000` | Hard upper bound on limit |
| `format` | string | `json` | Response format: `json` or `csv` |

**Bounds enforcement:**
- Default limit: 100 rows
- Maximum limit: 1000 rows — requests with `limit > 1000` return `422`
- `limit <= 0` returns `422`
- Unsupported `format` values return `400`

**JSON response example:**

```json
{
  "metadata": {
    "generated_at": "2026-06-16T10:30:00+00:00",
    "filters": {
      "limit": 100
    },
    "session_count": 2,
    "event_count": 5,
    "format": "json"
  },
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
  ],
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

**CSV response example** (`format=csv`):

Returns `text/csv` with event rows. Sessions are not included in CSV output.

```csv
id,session_id,model,provider,input_tokens,output_tokens,duration,tps,created_at
1,abc123,gpt-4o,openai,1500,800,2.3,347.8,2026-06-16T10:30:00Z
```

**Empty results:** Valid bounded queries with no matching data return `200` with empty `sessions` and `events` arrays (JSON) or a CSV with only the header row.

**Error responses:**
- `400` — unsupported format (e.g., `format=xml`)
- `422` — invalid limit (zero, negative, or exceeds max)
- `503` — store unavailable

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

#### Aggregate Metrics (Default)

These metrics have **no `session_id` label** — series count is fixed regardless of how many sessions exist. This is the default and recommended mode.

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `tps_last_call_aggregate` | Gauge | — | Most recent TPS across all sessions |
| `tps_avg_aggregate` | Gauge | — | Average TPS from the most recently updated session |
| `tps_peak_aggregate` | Gauge | — | Peak TPS from the most recently updated session |
| `tps_tokens_total_aggregate` | Counter | `direction` | Total tokens processed across all sessions |
| `tps_api_calls_total_aggregate` | Counter | — | Total API calls recorded across all sessions |
| `tps_model_avg_aggregate` | Gauge | `model` | Average TPS per model (bounded) |
| `tps_model_peak_aggregate` | Gauge | `model` | Peak TPS per model (bounded) |
| `tps_provider_avg_aggregate` | Gauge | `provider` | Average TPS per provider (bounded) |
| `tps_provider_peak_aggregate` | Gauge | `provider` | Peak TPS per provider (bounded) |
| `tps_model_avg_overflow` | Gauge | — | Overflow avg TPS when model cap exceeded |
| `tps_model_peak_overflow` | Gauge | — | Overflow peak TPS when model cap exceeded |
| `tps_provider_avg_overflow` | Gauge | — | Overflow avg TPS when provider cap exceeded |
| `tps_provider_peak_overflow` | Gauge | — | Overflow peak TPS when provider cap exceeded |

#### Prometheus Cardinality

**Why no `session_id` label by default?**

Every unique combination of metric name + label values creates a separate time series in Prometheus. A `session_id` label means each new session creates new series — unbounded growth that consumes memory in both Prometheus and the plugin. This is a well-known anti-pattern in the Prometheus ecosystem.

Instead, the plugin exports **aggregate metrics** that always reflect the latest state. Per-session detail remains available via the REST API, WebSocket, and SQLite persistence.

**Bounded model/provider labels:**

Per-model and per-provider metrics are capped at 50 distinct values by default. When the cap is exceeded, new values route to overflow aggregate gauges (`tps_model_avg_overflow`, etc.) instead of creating new label sets. Adjust the cap:

```bash
export TPS_COUNTER_PROMETHEUS_LABEL_CARDINALITY_CAP=100
```

**Legacy session labels (opt-in):**

If you need per-session Prometheus labels for backward compatibility, enable them explicitly:

```bash
export TPS_COUNTER_PROMETHEUS_LEGACY_SESSION_LABELS=1
```

Or in TOML:

```toml
[prometheus]
enabled = true
legacy_session_labels = true
```

> **Warning:** Enabling legacy session labels restores unbounded cardinality. Use only if you have a retention policy or cardinality-aware Prometheus setup.

#### Legacy Session-Labeled Metrics

When `prometheus_legacy_session_labels` is enabled, these additional metrics are emitted:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `tps_last_call` | Gauge | `session_id` | TPS for the most recent API call |
| `tps_avg` | Gauge | `session_id` | Rolling average TPS for the session |
| `tps_peak` | Gauge | `session_id` | Peak TPS observed in this session |
| `tps_tokens_total` | Counter | `session_id`, `direction` | Total tokens processed |
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
legacy_session_labels = false
label_cardinality_cap = 50
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
| `TPS_COUNTER_PROMETHEUS_LEGACY_SESSION_LABELS` | bool | `false` | Emit per-session_id Prometheus labels (unbounded cardinality) |
| `TPS_COUNTER_PROMETHEUS_LABEL_CARDINALITY_CAP` | int | `50` | Max distinct model/provider label values before overflow |
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
