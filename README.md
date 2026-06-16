# hermes-tps-counter

Hermes Agent plugin that tracks tokens-per-second (TPS) throughput and displays it in the status bar.

## What It Does

- Hooks into `post_api_request` to capture output tokens and API duration after each LLM call
- Maintains per-session stats: last TPS, rolling average, peak TPS, total output tokens
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
from tps_counter import get_tps_stats

stats = get_tps_stats(session_id)
# {"calls": 5, "avg_tps": 98.7, "last_tps": 114.0, "peak_tps": 456.2, "total_output_tokens": 12345, "total_duration": 125.3}
```

## No Configuration Required

Works out of the box. No env vars or config needed.

## Threshold Alerting

The plugin can alert you when TPS drops below acceptable levels. Alerts are evaluated in-hook after each API call — no background threads.

### How It Works

1. **Cold start**: The first 10 API calls establish a baseline TPS. The auto-threshold is set to 50% of that baseline.
2. **Rolling window**: After each call, the plugin evaluates the average TPS over the last N calls (default: 5).
3. **State machine**: Alert state transitions: `idle` → `firing` → `resolved`. Each transition emits a `tps_alert` hook event.
4. **Status bar**: When the alert is firing, the status bar shows `⚠ TPS ALERT`.

### Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `TPS_THRESHOLD` | Auto-calculated | Fixed TPS threshold in tok/s. If not set, auto-calculated from first 10 calls. |
| `TPS_EVAL_WINDOW` | `5` | Number of recent calls to evaluate for the rolling average. |

```bash
# Set a fixed threshold of 50 tok/s
export TPS_THRESHOLD=50

# Evaluate over the last 10 calls instead of 5
export TPS_EVAL_WINDOW=10
```

### Hook: `tps_alert`

Other plugins can subscribe to alert events:

```python
def my_alert_handler(**kwargs):
    session_id = kwargs["session_id"]
    state = kwargs["state"]       # "firing" or "resolved"
    tps = kwargs["tps"]           # current rolling average
    threshold = kwargs["threshold"]
    timestamp = kwargs["timestamp"]

ctx.register_hook("tps_alert", my_alert_handler)
```

### Stats API

`get_tps_stats()` now includes alert fields:

```python
stats = get_tps_stats(session_id)
# {
#   "calls": 15, "avg_tps": 98.7, "last_tps": 114.0, "peak_tps": 456.2,
#   "total_output_tokens": 12345, "total_duration": 125.3,
#   "alert_state": "idle",              # idle | firing | resolved
#   "alert_threshold": 50.0,            # tok/s (None during cold start)
# }
```
