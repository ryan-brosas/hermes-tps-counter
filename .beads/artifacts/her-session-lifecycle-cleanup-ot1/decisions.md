# Decisions: Session Lifecycle Cleanup

## D1: Use on_session_end hook + LRU eviction (not TTL sweep)
- **Chosen:** Event-driven cleanup via `on_session_end` + LRU eviction as safety net
- **Rejected:** TTL sweep on each API call — O(n) per call, adds latency, delays cleanup
- **Rationale:** Hook handles graceful close (95% of cases). LRU catches killed sessions and hook failures. Zero per-call overhead for normal path.

## D2: MAX_SESSIONS = 50 (hardcoded constant)
- **Chosen:** Module-level constant, not configurable
- **Rejected:** Env var or config file for MAX_SESSIONS
- **Rationale:** YAGNI — 50 is generous for typical usage. Can add configurability later if needed. Keeps the plugin zero-config.

## D3: Evict by oldest turn_start_time (LRU-ish)
- **Chosen:** Evict session with oldest `turn_start_time`
- **Rejected:** True LRU (track access time on every read), FIFO (evict by creation time)
- **Rationale:** `turn_start_time` is already updated on each `record()` call, so it approximates recency without extra bookkeeping. FIFO would evict long-lived but active sessions.

## D4: session_duration uses created_at, not turn_start_time
- **Chosen:** `time.time() - state.created_at` for session duration
- **Rejected:** Using `turn_start_time`
- **Rationale:** `created_at` measures total session lifetime. `turn_start_time` resets on `reset_turn()`. Users want to know how long the session has been alive.

## D5: Cleanup in _on_post_api_request (not separate thread)
- **Chosen:** Call `_evict_if_needed()` inline after `record()`
- **Rejected:** Background cleanup thread with periodic sweep
- **Rationale:** Inline call is simpler, no thread management, and `_STATE_LOCK` already serializes access. Eviction is O(n) but n≤50, so negligible.
