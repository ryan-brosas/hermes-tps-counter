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

### Stale / Session-Mismatch Handling

Every `_tps_snapshot` includes freshness metadata that consumers can use to suppress stale or cross-session TPS values:

| Field | Type | Description |
|-------|------|-------------|
| `updated_at` | `float` | Wall-clock time (`time.time()`) when the snapshot was created. Useful for logging and diagnostics. |
| `updated_monotonic` | `float` | Monotonic time (`time.monotonic()`) when the snapshot was created. Use this for robust age calculations that survive system clock changes. |
| `session_id` | `str` | The session that produced this snapshot. Compare against the active session to detect cross-session data leakage. |

**Recommended stale-threshold behavior** — consumers should compare `time.monotonic() - snapshot["updated_monotonic"]` against a configurable threshold (e.g. 30–120 seconds). If the age exceeds the threshold, suppress or gray-out the TPS display rather than showing potentially stale data.

**Recommended session-mismatch behavior** — if `snapshot["session_id"]` does not match the active session identifier, consumers should ignore or reset the TPS display.

**Example with freshness checks:**

```python
import time

tps = getattr(agent, "_tps_snapshot", None)
if tps:
    age = time.monotonic() - tps.get("updated_monotonic", 0)
    session_match = tps.get("session_id") == active_session_id
    if age < STALE_THRESHOLD and session_match:
        tps_val = tps.get("last_tps", 0)
        if tps_val > 0:
            snapshot["tps_label"] = f"⚡{tps_val:.0f} tok/s"
        else:
            snapshot["tps_label"] = ""
    else:
        snapshot["tps_label"] = ""  # Suppress stale or mismatched data
else:
    snapshot["tps_label"] = ""
```

All freshness fields are **additive and backward compatible** — existing consumers that do not read them will continue to work unchanged. The stale-threshold value is implementation-defined and should be tuned to match the consumer's rendering cadence and acceptable staleness window.

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
