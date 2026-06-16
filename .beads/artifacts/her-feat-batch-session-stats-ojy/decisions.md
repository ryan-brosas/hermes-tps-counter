---
purpose: Decision log for a bead
updated: 2026-06-17
---

# Decisions: her-feat-batch-session-stats-ojy

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Add a new batch endpoint instead of changing existing session endpoints. | Preserves compatibility for `GET /api/v1/sessions` and `GET /api/v1/sessions/{session_id}/tps` while adding the requested multi-session capability. | High |
| 2 | Use `POST /api/v1/sessions/batch/tps` with a JSON body containing `session_ids`. | Multiple IDs can exceed comfortable query-string usage, and POST avoids overloading the existing list endpoint query semantics. | Med |
| 3 | Return partial success with `sessions` plus `missing_session_ids`. | Batch consumers can use available data immediately and distinguish absent sessions without splitting requests. | High |
| 4 | Reuse `SessionTPSResponse` fields inside the batch response. | Keeps the batch contract aligned with current single-session and all-session API shapes. | High |
| 5 | Keep the implementation read-only against the current SQLite schema. | Existing `session_tps` data already contains the required fields; schema migration is unnecessary for this endpoint. | High |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Add query filtering to `GET /api/v1/sessions`. | The endpoint already means list all sessions; adding filter semantics risks confusing callers and documentation. | Backward-compatible behavior becomes harder to reason about and test. |
| 2 | Require one `GET /api/v1/sessions/{session_id}/tps` call per session. | This is the existing limitation the bead is intended to remove. | Clients continue to perform N requests for N sessions. |
| 3 | Return 404 if any requested session is missing. | All-or-nothing failure prevents clients from using found session stats and makes batch calls brittle. | Partial data becomes unavailable even when most requested sessions exist. |
| 4 | Add new database tables or schema migrations. | The endpoint only reads existing `session_tps` rows and does not need new persisted data. | Unnecessary migration risk for a small read-only API feature. |
| 5 | Include events/trends in the batch response. | The bead title and scope target session stats, not event history or aggregate trend expansion. | Larger response payloads and unclear endpoint responsibility. |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | Batch callers know the session IDs they want before making the request. | Validated by bead title: multi-session queries in a single request. | If callers need discovery, `GET /api/v1/sessions` remains the correct endpoint. |
| 2 | Returning found sessions plus missing IDs is acceptable product behavior. | Unknown until implementation/review; documented as the proposed contract. | If all-or-nothing is required, response status and tests must change. |
| 3 | Typical batch sizes are small enough for local FastAPI and SQLite use. | Inferred from plugin/local dashboard context. | If large batches are expected, add explicit max-size validation and/or optimized SQL `IN` loading. |
| 4 | Existing rate limiting applies uniformly to the new endpoint. | Validated by `RateLimitMiddleware` wrapping the app, not individual endpoints. | If route-specific limits are required, config/middleware work would be needed. |
| 5 | README is the primary user-facing API documentation. | Validated by existing REST API examples in `README.md`. | If docs live elsewhere, update the additional docs as part of implementation. |
