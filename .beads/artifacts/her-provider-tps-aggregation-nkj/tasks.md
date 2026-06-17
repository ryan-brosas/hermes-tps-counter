# Tasks: her-provider-tps-aggregation-nkj

## Task 1: Add provider extraction helper
**File:** __init__.py
**Action:** Add `_extract_provider(model: str) -> str` function. Splits model string on `/`, returns prefix or `"default"`. Covers: `openai/gpt-4o` → `openai`, `anthropic/claude-sonnet-4` → `anthropic`, `gpt-4` → `default`.
**Verification:** Unit test for edge cases (no slash, empty string, multiple slashes)
**Parallel:** No
**Depends on:** None

## Task 2: Add _ProviderTPS class
**File:** __init__.py
**Action:** Create `_ProviderTPS` class with avg_tps, peak_tps, call_count, total_output_tokens, total_duration. Add `record(output_tokens, duration)` method. Add `avg_tps` and `peak_tps` properties.
**Verification:** Class instantiation and record method work correctly
**Parallel:** No
**Depends on:** Task 1

## Task 3: Add per-provider state tracking
**File:** __init__.py
**Action:** Add `_PROVIDERS: Dict[str, Dict[str, _ProviderTPS]]` (session_id → provider → stats). Add `_get_provider(session_id, provider) -> _ProviderTPS` helper. Guard with existing `_STATE_LOCK`.
**Verification:** State tracking works under lock
**Parallel:** No
**Depends on:** Task 2

## Task 4: Hook into _on_post_api_request
**File:** __init__.py
**Action:** After session record, extract provider from `kwargs.get("model", "")`. Update provider stats. Include providers dict in `_tps_snapshot["providers"]`.
**Verification:** Provider stats populated after API call
**Parallel:** No
**Depends on:** Task 3

## Task 5: Add public API
**File:** __init__.py
**Action:** Add `get_provider_stats(session_id) -> Dict[str, Dict[str, Any]]`. Returns provider_name → {avg_tps, peak_tps, calls, total_output_tokens, total_duration}.
**Verification:** API returns correct structure
**Parallel:** No
**Depends on:** Task 4

## Task 6: Integration with session cleanup
**File:** __init__.py
**Action:** Provider state for a session should be cleaned up when session is evicted. Piggyback on session eviction hook from `her-session-lifecycle-cleanup-ot1`.
**Verification:** Provider state removed when session evicted
**Parallel:** No
**Depends on:** Task 5, her-session-lifecycle-cleanup-ot1
