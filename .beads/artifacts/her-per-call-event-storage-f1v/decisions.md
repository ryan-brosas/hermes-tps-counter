---
purpose: Decision log for a bead
updated: 2026-06-16
---

# Decisions: her-per-call-event-storage-f1v

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Use append-only event log (not aggregate-only) | Per-call granularity needed for degradation detection. Aggregates can be added later as optimization. | High |
| 2 | Add call_events to existing SQLite DB (not separate file) | Simplifies deployment, shares connection/lock, no new config. Scale is small enough that one DB handles both tables. | High |
| 3 | Use lazy expiry on write (not background thread) | Simpler implementation. No new daemon thread. Every N writes, delete rows older than retention. | High |
| 4 | Schema migration bumps version to 3 | Follows existing pattern (v1→v2 added total_input_tokens column). try/except for ALTER TABLE handles existing DBs. | High |
| 5 | REST API returns raw events + aggregated trends as separate endpoints | Events endpoint for detailed inspection, trends endpoint for dashboard consumption. Clean separation. | Medium |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Separate time-series DB file | Adds complexity for marginal query perf gain at this scale. Two connections, two locks, two files to manage. | Low — could optimize later if single-DB becomes bottleneck |
| 2 | Hourly/daily rollup tables only | Loses per-call granularity. Can't detect short-lived degradation spikes within a rollup window. | Medium — would need to add per-call events anyway |
| 3 | In-memory ring buffer with periodic flush | Data loss risk on crash. Added complexity for flush logic. Current SQLite INSERT is already sub-millisecond. | Medium — persistence is a core requirement |
| 4 | Background thread for expiry | Extra thread management, shutdown coordination. Lazy check on write is simpler and sufficient for 7-day retention at normal call rates. | Low — can add background cleanup later if needed |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | Call volume is < 1000 calls/day per session | Validated by typical Hermes usage patterns | Would need batch inserts or async writes if exceeded |
| 2 | 7-day retention is sufficient for trend analysis | Unknown — user hasn't specified | May need configurable retention (included as SHOULD) |
| 3 | Existing _STATE_LOCK doesn't contended on event INSERT | Validated — SQLite WAL mode supports concurrent reads, single-writer with fast commits | Would need separate lock or connection pooling |
| 4 | Pydantic models for event response are straightforward | Validated by existing api.py patterns | None — standard pattern |
