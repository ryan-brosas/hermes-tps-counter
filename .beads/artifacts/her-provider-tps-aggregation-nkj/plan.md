# Plan: Provider-Level TPS Aggregation

## Wave Sequence

Single wave — all tasks are sequential (same file, dependent changes).

### Wave 1 (sequential)

**Task 1: Add provider extraction helper**
- Add `_extract_provider(model: str) -> str` function
- Splits model string on `/`, returns prefix or `"default"`
- Covers: `openai/gpt-4o` → `openai`, `anthropic/claude-sonnet-4` → `anthropic`, `gpt-4` → `default`
- Tests: unit test for edge cases (no slash, empty string, multiple slashes)

**Task 2: Add `_ProviderTPS` class**
- Mirrors `_SessionTPS` but simpler: avg_tps, peak_tps, call_count, total_output_tokens, total_duration
- `record(output_tokens, duration)` method
- `avg_tps` and `peak_tps` properties

**Task 3: Add per-provider state tracking**
- `_PROVIDERS: Dict[str, Dict[str, _ProviderTPS]]` — session_id → provider → stats
- `_get_provider(session_id, provider) -> _ProviderTPS` helper
- Guard with existing `_STATE_LOCK`

**Task 4: Hook into `_on_post_api_request`**
- After session record, extract provider from `kwargs.get("model", "")`
- Update provider stats
- Include providers dict in `_tps_snapshot["providers"]`

**Task 5: Add public API**
- `get_provider_stats(session_id) -> Dict[str, Dict[str, Any]]`
- Returns provider_name → {avg_tps, peak_tps, calls, total_output_tokens, total_duration}

**Task 6: Integration with session cleanup**
- Provider state for a session should be cleaned up when session is evicted (depends on `her-session-lifecycle-cleanup-ot1` for the eviction hook)

## Dependencies

- `her-session-lifecycle-cleanup-ot1` — provider cleanup should piggyback on session eviction
- `her-her-per-model-tps-tracking-h6f` — coordinate on shared model parsing logic

## Context Capsule

- File: `__init__.py` (169 lines, single-file plugin)
- Key classes: `_SessionTPS` (lines 23-98), `_on_post_api_request` (lines 108-146)
- Lock pattern: `_STATE_LOCK` with `_SESSIONS` dict
- Model string format: `provider/model-name` (LiteLLM convention)
- Status bar snapshot: `agent._tps_snapshot` dict with last_tps, avg_tps, peak_tps, output_tokens
