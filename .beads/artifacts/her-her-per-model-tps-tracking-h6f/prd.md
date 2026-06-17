# PRD: Per-Model TPS Tracking

## Problem
When a user switches models mid-session (e.g., from gpt-4o to claude-sonnet), the TPS stats get polluted. The avg_tps and peak_tps reflect a mix of different model speeds, making the stats meaningless for performance comparison.

## Scope
- Track TPS per model within each session
- Expose per-model stats via API
- Don't break existing per-session stats

## Requirements
1. Extend `_SessionTPS` to store per-model TPS data
2. Extract model name from hook kwargs (same pattern as provider extraction)
3. Track avg_tps, peak_tps, call_count, total_output_tokens per model
4. Add `get_model_stats(session_id)` public API
5. Include per-model breakdown in `_tps_snapshot`

## Approach
- Add `_ModelTPS` class (mirrors `_SessionTPS` but simpler)
- Add `_MODELS: Dict[str, Dict[str, _ModelTPS]]` per-session storage
- Extract model from `kwargs.get("model", "")` in hook
- Guard with existing `_STATE_LOCK`

## Acceptance Criteria
- Per-model stats available via `get_model_stats(session_id)`
- Existing `get_tps_stats` unchanged
- Model switching doesn't pollute cross-model averages
