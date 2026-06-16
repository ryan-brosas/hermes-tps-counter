---
purpose: Product Requirements Document for a bead
updated: 2026-06-17
---

# PRD: Add batch session stats endpoint for multi-session queries in single request

**Bead:** her-feat-batch-session-stats-ojy | **Type:** feature | **Priority:** P2
**Created:** 2026-06-17 | **Estimate:** 45 minutes

## Problem

WHEN dashboard, automation, or external observability clients need TPS stats for a selected set of sessions THEN they must either call `GET /api/v1/sessions` and filter client-side or issue many `GET /api/v1/sessions/{session_id}/tps` requests BECAUSE the REST API only exposes all-session listing and single-session lookup.

**Who is affected?** Local dashboard/API consumers, monitoring scripts, and any integrations that need stats for multiple known session IDs without fetching unrelated sessions.
**Why now?** The existing API has single-session and all-session endpoints, but no middle-ground batch query; this creates unnecessary request overhead and can leak more session data than needed to clients that only need a bounded subset.

## Scope

### In Scope
- Add a REST endpoint that accepts multiple session IDs in one request and returns per-session TPS stats for the sessions found.
- Define Pydantic request/response models in `api.py` consistent with existing `SessionTPSResponse` conventions.
- Use existing `PersistentSessionStore` data and locking patterns; avoid schema changes unless implementation discovers an unavoidable need.
- Report missing session IDs explicitly without failing the entire batch when at least one requested session is absent.
- Cover success, partial-miss, empty/invalid input, duplicate input, and unavailable-store behavior in API tests.
- Document the endpoint shape in the README REST API section.

### Out of Scope
- Replacing or changing `GET /api/v1/sessions` or `GET /api/v1/sessions/{session_id}/tps` behavior.
- Adding authentication, authorization, pagination, or public internet hardening.
- Implementing batch event or trend queries for `/api/v1/events/{session_id}` or `/api/v1/trends/{session_id}`.
- Changing SQLite schema, retention behavior, WebSocket payloads, or Prometheus metrics.
- Updating dashboard UI to consume the new endpoint unless required by tests/documentation.

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Provide a batch session TPS endpoint under the existing `/api/v1` namespace. | MUST | A client can request stats for multiple session IDs in one HTTP request and receive a 200 response using the same per-session fields as `SessionTPSResponse`. |
| 2 | Preserve existing endpoint contracts. | MUST | Existing tests for health, all sessions, single-session TPS, summary, events, trends, WebSocket, and metrics continue to pass without response-shape regressions. |
| 3 | Handle missing sessions deterministically. | MUST | Response includes found sessions and a `missing_session_ids` list for IDs not present; missing IDs do not cause a 404 for the whole batch. |
| 4 | Validate request input. | MUST | Empty `session_ids` or non-list input is rejected with FastAPI/Pydantic validation semantics; excessive duplicates are normalized or handled without duplicate response rows. |
| 5 | Fail cleanly when persistence is unavailable. | MUST | If `store` is `None`, the batch endpoint returns HTTP 503 with the same database-unavailable semantics as other session endpoints. |
| 6 | Avoid unnecessary database fan-out where practical. | SHOULD | Implementation either adds a store-level batch loader or otherwise keeps the number of DB operations bounded and simple for the expected small local batch size. |
| 7 | Document API usage. | SHOULD | README lists the new endpoint and includes request/response JSON examples including missing sessions. |

## Technical Context

Relevant code:
- `api.py` defines the FastAPI app, Pydantic response models, and current REST endpoints.
- Existing session models: `SessionTPSResponse` and `SessionListResponse`.
- Current single-session endpoint: `GET /api/v1/sessions/{session_id}/tps` calls `store.load(session_id)` and returns 404 when absent.
- Current all-session endpoint: `GET /api/v1/sessions` calls `store.load_all()` and returns `{ "sessions": [...] }`.
- `store.py` implements `PersistentSessionStore.load(session_id)` and `load_all()` over SQLite with a thread lock and row-to-dict mapping.
- `tests/test_api.py` contains FastAPI TestClient tests for existing endpoint behavior and is the natural home for endpoint coverage.
- `README.md` REST API section documents endpoints and example JSON response shapes.

Likely endpoint shape:
- `POST /api/v1/sessions/batch/tps`
- Request: `{ "session_ids": ["session-a", "session-b"] }`
- Response: `{ "sessions": [<SessionTPSResponse>, ...], "missing_session_ids": ["session-b"] }`

Route ordering must avoid treating a static batch path as the `{session_id}` path segment. In FastAPI, declare the static batch route before dynamic `/api/v1/sessions/{session_id}/tps` if route ambiguity appears.

## Approach

Add request/response models in `api.py` near the existing session models. Implement a batch endpoint that validates the requested session IDs, preserves first-seen order, removes duplicates for lookup/response stability, loads session data through the persistence layer, and returns found sessions plus missing IDs. Prefer a small `PersistentSessionStore.load_many(session_ids)` helper if it keeps API code simple and avoids repeated `load()` calls; otherwise, for the expected local API use case, repeated `load()` calls are acceptable if tests demonstrate correct behavior.

Update API tests before or alongside implementation to lock down full-hit, partial-miss, duplicate, validation, and store-unavailable cases. Update README endpoint table and add a concise example.

**Alternatives considered:**
- Use `GET /api/v1/sessions?session_ids=a,b`: rejected because the existing endpoint already means list all sessions and query parameter semantics would complicate backward compatibility.
- Require clients to use `GET /api/v1/sessions` and filter: rejected because it returns unrelated sessions and does not reduce payload size for known subsets.
- Return HTTP 404 when any requested session is missing: rejected because it forces retry/splitting and makes partial results less useful.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Static route conflicts with `/api/v1/sessions/{session_id}/tps`. | Med | Med | Declare static batch route before the dynamic route and cover with tests. |
| Large batch payloads cause heavy DB work or large responses. | Low | Med | Document/use reasonable input validation; consider a max item count if implementation scope allows. |
| Missing-session semantics surprise clients expecting all-or-nothing. | Low | Low | Include explicit `missing_session_ids` and document partial success behavior. |
| Response model drifts from single-session fields. | Low | Med | Reuse `SessionTPSResponse` inside the batch response model. |
| Store helper adds unnecessary schema/locking complexity. | Low | Low | Keep helper read-only and reuse `_row_to_dict` and existing lock; do not alter schema. |

## Tasks (for epics)

| Task | Depends On | Parallel | Files |
|------|-----------|----------|-------|
| N/A — single feature bead | N/A | N/A | N/A |

## Success Criteria

- [ ] `POST /api/v1/sessions/batch/tps` returns TPS stats for multiple existing session IDs in one request.
    - Verify: `pytest tests/test_api.py -k batch`
- [ ] Response includes missing IDs while returning found sessions for partial hits.
    - Verify: API test asserts `sessions` and `missing_session_ids` contents.
- [ ] Duplicate session IDs do not produce duplicate response rows.
    - Verify: API test submits duplicate IDs and checks stable, de-duplicated output.
- [ ] Existing API behavior remains unchanged.
    - Verify: `pytest tests/test_api.py`
- [ ] README documents the new endpoint request and response examples.
    - Verify: README REST API endpoint table includes the batch endpoint.
