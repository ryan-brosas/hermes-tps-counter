# Decision Log

## 2026-06-16 — Bead created: her-input-token-tracking-z7h

### Decision: Track input tokens alongside output tokens
- **Rationale**: The `post_api_request` hook already receives `input_tokens` in the `usage` dict but the plugin ignores them. This is the lowest-effort feature with highest information gain — complete token visibility (input + output + total) with ~30 lines of changes.
- **Alternatives considered**:
  - TPS history persistence (JSON to disk) — higher effort, complex atomic writes
  - /tps slash command — needs Hermes command registration research
  - Per-model tracking — scope creep, not needed yet
- **Trade-off**: Adds complexity to _SessionTPS but the class is already tracking output tokens; input tokens follow the same pattern exactly.

### Decision: Keep TPS calculation based on output tokens only
- **Rationale**: TPS (tokens per second) is a generation speed metric — it measures how fast the model produces output. Input tokens are consumed instantly (prompt processing), so mixing them into TPS would dilute the signal. Input tokens are tracked for volume/cost awareness, not speed.
- **Alternative**: Could compute separate input_TPS and output_TPS, but that's overengineering for now.

### Decision: Additive-only changes to _tps_snapshot
- **Rationale**: The status bar reads `_tps_snapshot` from the agent. We add new keys (`input_tokens`, `total_tokens`) without changing existing keys (`last_tps`, `avg_tps`, `peak_tps`, `output_tokens`). This ensures backward compatibility.
