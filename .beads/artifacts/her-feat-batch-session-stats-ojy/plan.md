---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-feat-batch-session-stats-ojy

**Goal:** Add a batch session TPS endpoint that accepts multiple session IDs in one request and returns per-session TPS stats for the sessions found, with explicit missing session reporting.

## Graph Context

- **Blast radius:** `api.py`, `store.py`, `tests/test_api.py`, `README.md` — 4 files affected
- **Unblocks:** No downstream beads (standalone feature)
- **Blocked by:** None (no upstream dependencies)
- **Critical path:** No (parallel-safe with other work)
- **Forecast:** 85 minutes estimated (0.35 days at current velocity)

## Observable Truths

What must be TRUE for the goal to be achieved:

1. **POST /api/v1/sessions/batch/tps returns 200 with valid JSON** — Client can send `{ "session_ids": ["id1", "id2"] }` and receive `{ "sessions": [...], "missing_session_ids": [...] }`.
2. **Partial hits work correctly** — When some session IDs exist and some don't, found sessions are returned in `sessions` array and missing IDs appear in `missing_session_ids` array; no 404 for partial misses.
3. **Duplicate session IDs are normalized** — Duplicate IDs in request do not produce duplicate response rows; first-seen order preserved.
4. **Validation rejects empty/invalid input** — Empty `session_ids` list or non-list input returns FastAPI/Pydantic validation error (422).
5. **Store-unavailable returns 503** — When `store` is `None`, endpoint returns HTTP 503 with database-unavailable semantics matching existing endpoints.
6. **Existing endpoints unchanged** — All existing tests pass without regression; no response-shape changes to `/api/v1/sessions`, `/api/v1/sessions/{session_id}/tps`, etc.
7. **README documents the endpoint** — REST API section includes batch endpoint with request/response examples.

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Batch request model | Pydantic validation for `session_ids` input | `api.py` | Need |
| Batch response model | Structured response with sessions + missing IDs | `api.py` | Need |
| Batch endpoint | `POST /api/v1/sessions/batch/tps` handler | `api.py` | Need |
| Store helper (optional) | `load_many()` for efficient batch loading | `store.py` | Optional |
| API tests | Full coverage of batch endpoint behavior | `tests/test_api.py` | Need |
| README documentation | Endpoint table + example JSON | `README.md` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | 1.1 Verify existing tests pass | No | PRD complete, codebase accessible | `pytest tests/test_api.py` passes |
| 2 | 2.1 Add Pydantic models, 2.2 Implement batch endpoint, 2.3 (Optional) Add store helper | Yes (2.1 + 2.3 parallel, 2.2 after 2.1) | Wave 1 verified | Models defined, endpoint registered |
| 3 | 3.1 Write batch endpoint tests | No | Wave 2 complete | `pytest tests/test_api.py -k batch` passes |
| 4 | 4.1 Update README documentation | No | Wave 3 complete | README contains batch endpoint docs |
| 5 | 5.1 Full verification | No | All waves complete | `pytest tests/test_api.py` passes, README updated |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter/
# Verify existing tests pass (no regression)
pytest tests/test_api.py -v
# Verify batch-specific tests pass
pytest tests/test_api.py -v -k batch
# Verify README contains batch endpoint documentation
grep -A 10 "batch/tps" README.md
```
