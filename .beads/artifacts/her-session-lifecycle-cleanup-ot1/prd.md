# PRD: Session Lifecycle Cleanup and LRU Eviction

## Problem
The `_SESSIONS` dict in the tps-counter plugin grows unboundedly. Every session that calls the LLM creates a `_SessionTPS` entry that is never removed. In a long-running Hermes gateway process handling many sessions, this is a memory leak. There is no `on_session_end` hook, no max session limit, and no TTL.

## Goal
Add session lifecycle awareness: event-driven cleanup via `on_session_end` hook, LRU eviction as a safety net, and expose session duration in the stats API.

## Scope
- In: `on_session_end` hook registration, LRU eviction (MAX_SESSIONS=50), `session_duration` field in `get_tps_stats`, `__slots__` update, README update
- Out: Persistence to disk, per-model tracking, new CLI commands, cost calculation

## Affected Files
- `__init__.py` (modify) — add hook, LRU eviction, session duration
- `README.md` (modify) — document session lifecycle behavior
- `plugin.yaml` (modify) — add `on_session_end` to provides_hooks

## Functional Requirements
1. Register `on_session_end` hook in `register()` that calls `_cleanup_session(session_id)`
2. `_cleanup_session(session_id)` removes the session from `_SESSIONS` under `_STATE_LOCK`
3. LRU eviction: after each `record()`, if `len(_SESSIONS) > MAX_SESSIONS`, evict the session with the oldest `turn_start_time`
4. `MAX_SESSIONS` is a module-level constant (default 50)
5. `_SessionTPS` gains `created_at: float` field (set in `__init__` to `time.time()`)
6. `get_tps_stats` returns `session_duration` (seconds since session creation)
7. Thread safety: all cleanup and eviction paths use existing `_STATE_LOCK`
8. `_on_post_api_request` calls `_evict_if_needed()` after recording

## Success Criteria
- [ ] `on_session_end` hook registered in `register()`
- [ ] `_cleanup_session` removes session from `_SESSIONS`
- [ ] LRU evicts oldest session when `_SESSIONS` exceeds `MAX_SESSIONS`
- [ ] `get_tps_stats` includes `session_duration` field
- [ ] Thread-safe: no races between record/cleanup/evict
- [ ] All existing behavior preserved (backward compatible)
- [ ] No new dependencies (stdlib only)

## Non-Goals
- Persistence of TPS data across process restarts
- Per-model or per-provider tracking
- New slash commands or CLI subcommands
- Configurable MAX_SESSIONS (hardcoded constant is fine for v1)

## Risks
- Risk: `on_session_end` may not fire if process is killed
  - Mitigation: LRU eviction catches this — bounded memory regardless
- Risk: Evicting an active session mid-record
  - Mitigation: All operations under `_STATE_LOCK`; eviction only removes from dict, doesn't corrupt in-flight data
- Risk: `on_session_end` hook context may not include `session_id`
  - Mitigation: Log warning if missing; LRU is the real safety net
