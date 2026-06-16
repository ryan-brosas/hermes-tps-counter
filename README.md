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

Works out of the box. No env vars or config needed.

## Supported Provider Usage Formats

The plugin extracts token counts from multiple provider formats automatically:

| Provider  | Output tokens key      | Input tokens key       |
|-----------|------------------------|------------------------|
| Anthropic | `usage.output_tokens`  | `usage.input_tokens`   |
| OpenAI    | `usage.completion_tokens` | `usage.prompt_tokens` |
| Google    | `usage.completionTokens` | `usage.promptTokens`  |

Fallback order: primary key is tried first, then alternatives. Unknown formats return 0 without crashing.
