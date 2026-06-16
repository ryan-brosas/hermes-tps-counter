# hermes-tps-counter

Hermes Agent plugin that tracks tokens-per-second (TPS) throughput after LLM calls and exposes it to status-bar and in-process observability consumers.

## What It Does

- Registers the `post_api_request` hook declared in `plugin.yaml` (`name: tps-counter`, version `1.0.0`).
- Records successful LLM calls when `session_id` is present and both `usage["output_tokens"]` and `api_duration` are greater than zero.
- Maintains per-session counters: last TPS, rolling average TPS, peak TPS, total output tokens, and total duration.
- Injects the latest status snapshot into the active Hermes CLI agent as `agent._tps_snapshot` for status-bar integrations.
- Provides dependency-free in-process helpers for stats, observability contract metadata, and secret-safe privacy diagnostics.

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
from tps_counter import get_tps_stats

stats = get_tps_stats(session_id)
# Observed session:
# {
#   "calls": 5,
#   "avg_tps": 98.7,
#   "last_tps": 114.0,
#   "peak_tps": 456.2,
#   "total_output_tokens": 12345,
#   "total_duration": 125.3,
# }
```

For an unknown or unobserved session, the helper returns zero values without `total_duration`:

```python
{"calls": 0, "avg_tps": 0, "last_tps": 0, "peak_tps": 0, "total_output_tokens": 0}
```

`get_tps_stats(session_id)` expects the raw internal `session_id`; privacy redaction is applied to outbound observability payloads, not to `_SESSIONS` lookup correctness.

## Observability Contract

The machine-readable contract describes what consumers may rely on without scanning live sessions or importing optional server dependencies:

```python
from tps_counter import get_observability_contract

contract = get_observability_contract()
assert contract["contract"]["contract_version"] == "1.0.0"
```

Current contract surfaces:

| Surface | Availability on this branch | Consumer guidance |
|---------|-----------------------------|-------------------|
| `agent._tps_snapshot` | Available | Latest status-bar snapshot on the active CLI agent after successful hooks. Apply freshness and session checks. |
| `get_tps_stats(session_id)` | Available | In-process read-only helper for one raw session id. Missing sessions return zero values. |
| `get_observability_contract()` | Available | Static, dependency-free metadata; reading it does not create session state. |
| `get_privacy_diagnostics()` | Available | Secret-safe privacy mode diagnostics. |
| REST observability route | Unavailable when the contract marks `available: false` | No REST router is present in this branch; use `get_observability_contract()` instead. |
| WebSocket stream | Unavailable when the contract marks `available: false` | Do not assume TPS events are emitted; use status snapshots or in-process helpers. |
| Prometheus exporter | Unavailable when the contract marks `available: false` | Do not scrape plugin-specific metrics until a future contract lists metric names, units, and labels. |

The contract includes additive top-level sections for `contract`, `compatibility`, `privacy`, `status_snapshot`, `api`, `websocket`, and `prometheus`. Compatible consumers should ignore unknown fields or sections. Breaking changes require a new major `contract_version`.

## Privacy Redaction

Default behavior is raw/backward-compatible: existing status-bar integrations and raw `snapshot["session_id"]` comparisons continue to work unless privacy mode is enabled.

Configure privacy with these environment variables:

| Variable | Purpose |
|----------|---------|
| `HERMES_TPS_PRIVACY_MODE` | `disabled`/raw-compatible by default; accepts pseudonymized, redacted, or omitted modes (common aliases are normalized by the plugin). |
| `HERMES_TPS_PRIVACY_SALT` | Secret salt for deterministic pseudonyms. Do not put real secret values in docs, logs, or examples. |
| `HERMES_TPS_PRIVACY_SCOPE` | Optional grouping scope for pseudonyms; changing it changes pseudonym outputs. |
| `HERMES_TPS_PRIVACY_FIELDS` | Comma-separated additional identifier-like fields to treat as privacy-covered. Built-ins are `session_id`, `model`, and `provider`. |
| `HERMES_TPS_PRIVACY_TREATMENTS` | Per-field overrides such as `provider=redacted,tenant_id=omitted`. Valid treatments are `raw`, `pseudonymized`, `redacted`, and `omitted`. |

Treatment meanings:

| Treatment | Behavior |
|-----------|----------|
| `raw` | Emit the identifier unchanged. This is the disabled/default behavior. |
| `pseudonymized` | Emit a deterministic HMAC-SHA256 pseudonym scoped by field and configured scope. |
| `redacted` | Emit the constant `[redacted]` marker. |
| `omitted` | Remove the field from outbound payloads when the surface can tolerate omission. |

Secrets and raw identifiers are not emitted by privacy diagnostics or the observability contract when privacy mode is enabled. Snapshots and debug logs are privacy-treated at outbound boundaries; raw identifiers remain internal for session lookup and TPS aggregation.

## Troubleshooting

| Symptom | Likely cause | Checks and remediation |
|---------|--------------|------------------------|
| No TPS display in the status bar | Plugin not copied/enabled, Hermes not restarted, status-bar patches missing, no successful LLM call yet, or no active CLI instance for injection. | Verify `~/.hermes/plugins/tps-counter/plugin.yaml`; restart Hermes; confirm the hook is `post_api_request`; make a successful LLM call; confirm `hermes_cli._ACTIVE_CLI_INSTANCE` points to the running CLI and the status bar reads `agent._tps_snapshot`. |
| TPS stats stay zero | The session is unknown/unobserved, the call had `output_tokens <= 0`, `api_duration <= 0`, or `session_id` was missing. | Call `get_tps_stats(raw_session_id)` after a successful generation; check provider usage parsing supplies `usage["output_tokens"]`; check API duration is positive. Unknown sessions intentionally return zero values. |
| TPS appears briefly but later becomes stale | Consumer renders the last label without checking `updated_monotonic`, or the stale threshold is too long. | Compute `time.monotonic() - snapshot["updated_monotonic"]`; suppress or gray-out values older than the chosen 30-120 second threshold; clear `tps_label` when stale. |
| TPS from another session appears | The status-bar consumer is not comparing `snapshot["session_id"]` to the active session, or privacy mode changed the snapshot identifier. | Compare against the active session before rendering. If privacy is enabled, apply the same field treatment before comparing; never compare a raw active id to `session_id:pseudonym:...`, `[redacted]`, or an omitted field. |
| `session_id`, `model`, or `provider` looks pseudonymized/redacted/missing | Privacy mode or `HERMES_TPS_PRIVACY_TREATMENTS` is active. | Inspect `get_observability_contract()["privacy"]` or `get_privacy_diagnostics()` for mode and field treatments. This is expected; salts and raw secrets should not appear in outputs. |
| REST, WebSocket, or Prometheus integration cannot find an endpoint/exporter | Those optional surfaces are not implemented on this branch and the contract marks them unavailable. | Check `get_observability_contract()`; when `available: false`, use `agent._tps_snapshot`, `get_tps_stats(session_id)`, or `get_observability_contract()` instead. Do not assume route paths or metric names exist. |
| Plugin registration fails | Wrong plugin location, missing/invalid `plugin.yaml`, Hermes not restarted, hook name mismatch, or loader log errors. | Confirm the copied directory includes `plugin.yaml` with `name: tps-counter`, `version: "1.0.0"`, and `hooks: [post_api_request]`; restart Hermes; inspect plugin-loader logs for import or registration errors. |
| Status-bar label is always blank even though stats exist | `last_tps <= 0`, stale/session checks suppress it, or render fragments only add non-empty labels. | Inspect `agent._tps_snapshot` in-process; verify `last_tps > 0`, age is below threshold, session matches, and `_get_status_bar_fragments()` appends `snapshot["tps_label"]` when present. |

## Default Configuration

The plugin works out of the box with privacy redaction disabled for backward compatibility. Set the privacy environment variables only when outbound observability identifiers need pseudonymization, redaction, or omission.
