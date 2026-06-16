---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-feat-batch-session-stats-ojy

## Objective

Add a `POST /api/v1/sessions/batch/tps` endpoint that accepts multiple session IDs in one request, returns TPS stats for found sessions, and explicitly reports missing session IDs without failing the entire batch.

## Key Patterns

- **Existing session models** — Reuse `SessionTPSResponse` and `SessionListResponse` patterns from `api.py`. New models should follow same field naming and structure conventions.
- **Single-session endpoint pattern** — Reference `GET /api/v1/sessions/{session_id}/tps` implementation: calls `store.load(session_id)`, returns 404 when absent. Batch endpoint adapts this pattern for multiple IDs with partial-success semantics.
- **Store access pattern** — `PersistentSessionStore` uses thread lock and `_row_to_dict` for safe concurrent access. New code must preserve this pattern.
- **Pydantic validation** — Use FastAPI/Pydantic for request validation (empty lists, non-list input). Let framework handle 422 errors naturally.
- **Route ordering** — FastAPI matches routes in declaration order. Static paths like `/sessions/batch/tps` MUST be declared BEFORE dynamic paths like `/sessions/{session_id}/tps` to avoid ambiguity.

## Constraints

1. **Do not modify existing endpoints** — `GET /api/v1/sessions`, `GET /api/v1/sessions/{session_id}/tps`, and all other endpoints must remain unchanged. All existing tests must continue to pass.
2. **Do not alter SQLite schema** — Use existing `PersistentSessionStore` data access; no schema changes. If a `load_many()` helper is added, it must be read-only and reuse existing lock and `_row_to_dict`.
3. **Partial success semantics** — Missing sessions return 200 with `missing_session_ids` list, NOT 404. This is intentional for batch operations.
4. **Deduplication** — Duplicate session IDs in request must not produce duplicate response rows. Preserve first-seen order.
5. **Store-unavailable returns 503** — When `store` is `None`, return HTTP 503 matching existing database-unavailable semantics.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Add models + endpoint | `api.py` — add models near existing session models, add endpoint route | `api.py` — do not modify existing endpoint logic or models |
| (Optional) Add store helper | `store.py` — add `load_many()` method | `store.py` — do not alter schema, lock, or `_row_to_dict` |
| Write tests | `tests/test_api.py` — add batch endpoint tests | `tests/test_api.py` — do not modify existing test cases |
| Update docs | `README.md` — add batch endpoint to REST API section | `README.md` — do not remove or alter existing endpoint docs |

## Graph Context

- **Blast radius:** `api.py`, `store.py` (optional), `tests/test_api.py`, `README.md`
- **Related beads:** `her-feat-historical-tps-export-s3i` (similar pattern, no dependency)
- **File history:** `README.md` and `tests/test_api.py` are hotspots (3 beads each, all closed) — handle with care, preserve existing content

## Implementation Notes

**Endpoint shape:**
```
POST /api/v1/sessions/batch/tps
Request:  { "session_ids": ["session-a", "session-b"] }
Response: { "sessions": [<SessionTPSResponse>, ...], "missing_session_ids": ["session-b"] }
```

**Critical ordering:** Declare the batch route before the dynamic `{session_id}` route in `api.py`. If route conflicts appear, test with FastAPI's route resolution.

**Test strategy:** Write tests BEFORE or ALONGSIDE implementation to lock down behavior. Use FastAPI TestClient pattern from existing tests.
