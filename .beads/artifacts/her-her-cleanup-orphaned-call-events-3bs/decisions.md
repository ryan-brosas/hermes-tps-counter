---
purpose: Decision log for a bead
updated: 2026-06-16
---

# Decisions: her-her-cleanup-orphaned-call-events-3bs

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Delete call_events inline within existing `delete()` method | Keeps transaction atomic; no new methods needed; consistent with existing pattern | High |
| 2 | Clean orphaned call_events in `delete_expired()` via NOT IN subquery | After purging expired sessions, remaining call_events with missing session_ids are orphans; NOT IN is simple and correct | High |
| 3 | Add `_STORE.delete()` call to `_evict_if_needed()` | Eviction currently only clears memory — DB rows persist as orphans; this is the root cause of the leak | High |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | FOREIGN KEY with CASCADE DELETE | Requires schema migration, table rebuild; existing deployments would need careful migration | Low risk but high effort for minimal gain |
| 2 | Background cleanup task | Adds complexity; cleanup-on-delete is immediate and simpler | Would delay cleanup, still leak between runs |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | No FK constraint exists between call_events and session_tps | Verified in store.py DDL — no FOREIGN KEY clause | If FK exists, CASCADE may already handle this (contradicts observed behavior) |
| 2 | `_evict_if_needed()` is called from `_on_post_api_request` hot path | Need to verify call site | If eviction is rare, DB leak is slower but still present |
