# PRD: Add SQLite persistence for TPS session data

## Problem

All TPS metrics are stored in an in-memory `_SESSIONS` dict (see `__init__.py` line 20). When Hermes restarts — whether from a crash, update, or intentional restart — all historical TPS data is lost. This means:

1. Peak TPS records vanish — users can't compare performance across sessions
2. Average TPS resets — no long-running baseline exists
3. Total output token counts reset — usage tracking is ephemeral
4. The gotchas file (`HERMES.md`) explicitly flags this: "In-memory only — data lost on restart (Phase 1 fixes this)"

This is the foundational infrastructure gap blocking real-world utility of the plugin.

## Scope

### In Scope
- SQLite database for persisting per-session TPS data
- Auto-create DB on first use (no manual setup)
- Write-through: record to DB on every `_SessionTPS.record()` call
- Read-through: populate `_SESSIONS` from DB on startup/get
- DB schema for session TPS snapshots (session_id, call_count, total_output_tokens, total_duration, peak_tps, last_tps, avg_tps, updated_at)
- Configurable DB path via plugin config (default: `~/.hermes/plugins/tps-counter/tps.db`)
- Thread-safe DB access (the plugin already uses `_STATE_LOCK`)
- Migration-friendly schema (version table for future changes)

### Out of Scope
- Historical time-series storage (per-call granularity) — future bead
- DB cleanup/pruning of old sessions — future bead
- Analytics queries (daily/weekly aggregation) — covered by `her-provider-tps-aggregation-nkj`
- Per-model tracking — covered by `her-her-per-model-tps-tracking-h6f`

## Requirements

1. **R1**: TPS data persists across plugin/agent restarts
2. **R2**: On startup, `_get_session()` loads existing data from DB if present
3. **R3**: Every `record()` call writes through to SQLite
4. **R4**: DB is created automatically with correct schema on first use
5. **R5**: Thread-safe — no data corruption under concurrent access
6. **R6**: Graceful degradation — if DB is unavailable, fall back to in-memory only (current behavior)
7. **R7**: No performance regression — DB writes must not block the API call path noticeably (<5ms)
8. **R8**: Tests pass with both in-memory and persistent backends

## Approach

Use Python's built-in `sqlite3` module (no external deps). Implement a `PersistentSessionStore` class that wraps the existing `_SessionTPS` pattern:

- **Write path**: `_SessionTPS.record()` → also persists to SQLite via `store.save(session_id, state)`
- **Read path**: `_get_session(session_id)` → checks in-memory first, then DB, then creates new
- **Schema**: Single `session_tps` table with UPSERT semantics (INSERT OR REPLACE)
- **Connection**: Single connection per plugin lifetime, WAL mode for concurrent reads
- **Config**: Read DB path from plugin config dict passed in `register(ctx)` or default to `~/.hermes/plugins/tps-counter/tps.db`

## Dependencies

- Python 3.11+ `sqlite3` (stdlib, no install needed)
- No blocking dependencies on other beads
- Complements: `her-session-lifecycle-cleanup-ot1` (LRU eviction should also prune DB)
- Complements: `her-test-suite-l0o` (persistence needs test coverage)

## Risk

- Low: sqlite3 is stdlib, battle-tested
- Medium: Thread-safety requires careful connection management (mitigated by WAL mode + single-writer pattern)
