---
purpose: Product Requirements Document for a bead
updated: 2026-06-17
---

# PRD: Add bounded historical TPS export endpoint for offline analysis and dashboard import

**Bead:** her-feat-historical-tps-export-s3i | **Type:** feature | **Priority:** P2
**Created:** 2026-06-17 | **Estimate:** 90 minutes

## Problem

WHEN users want to analyze historical TPS behavior outside the live Hermes session THEN they must scrape multiple narrow API endpoints or query SQLite directly BECAUSE the current FastAPI surface exposes session summaries, per-session events, and per-session trends but no bounded export endpoint designed for offline analysis or dashboard import.

**Who is affected?** Hermes users, operators, and dashboard builders running the optional tps-counter API who need to move stored `call_events` and `session_tps` data into notebooks, spreadsheets, BI tools, or dashboard import flows.
**Why now?** The project already persists per-call events and session-level TPS state in SQLite, exposes local-only REST APIs, and has enough historical data to export; a bounded export surface makes that data usable without unsafe direct DB access or ad hoc multi-endpoint scraping.

## Scope

### In Scope
- Add a read-only historical export endpoint to the existing FastAPI app in `api.create_app` under the versioned API namespace.
- Export persisted session TPS rows and per-call event rows from `PersistentSessionStore` for explicit session and/or time windows.
- Require bounded query parameters such as `session_id`, `since`, `until`, and/or `limit` so exports cannot accidentally scan or serialize unbounded SQLite data.
- Return JSON as the primary export format with a stable machine-readable shape suitable for notebooks, scripts, and dashboard import.
- Optionally support CSV through an explicit `format=csv` query parameter or response negotiation if this can be done without extra dependencies.
- Reuse existing store methods and indexed event access where practical, adding narrowly scoped store helpers only if existing APIs cannot produce a bounded export safely.
- Preserve existing endpoint response contracts and status codes for `/api/v1/health`, `/api/v1/sessions`, `/api/v1/sessions/{session_id}/tps`, `/api/v1/summary`, `/api/v1/events/{session_id}`, `/api/v1/trends/{session_id}`, `/api/v1/health/diagnostics`, `/metrics`, and `/ws/tps`.
- Add focused tests for bounded export behavior, error handling, response shape, format handling, and no regression to existing API routes.
- Document the endpoint, query parameters, response examples, limits, and intended offline-analysis usage in `README.md`.

### Out of Scope
- Changing retention policy, schema version, or how events are recorded unless a small read helper is strictly required.
- Adding authentication, remote exposure, public hosting guidance, or multi-user access control.
- Exporting directly to S3, files on disk, cloud storage, or third-party dashboard services.
- Adding new dependencies, build steps, background jobs, queues, or streaming export workers.
- Changing existing REST/WebSocket/Prometheus payload shapes.
- Implementing dashboard import UI, notebook templates, or analytics visualizations.
- Creating implementation plan artifacts, tasks, PRs, commits, or code in this repair pass.

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Provide a versioned historical export endpoint. | MUST | A new endpoint such as `GET /api/v1/export/history` is registered by `api.create_app` and returns persisted historical TPS data without altering existing endpoints. |
| 2 | Keep every export explicitly bounded. | MUST | Requests must specify safe bounds through `session_id`, `since`, `until`, and/or `limit`; default and maximum limits prevent unbounded SQLite reads or large in-memory responses. |
| 3 | Include both session summary and per-call event data when requested. | MUST | JSON responses can contain `sessions` data from `session_tps` and `events` data from `call_events`, with fields matching existing API semantics. |
| 4 | Preserve local-only/default API behavior and existing contracts. | MUST | All existing API, diagnostics, metrics, and WebSocket tests continue to pass; no existing response model or status code is intentionally changed. |
| 5 | Handle empty results and unavailable stores predictably. | MUST | Store unavailability returns 503; valid bounded queries with no matching data return a documented empty export response or documented 404 behavior, consistently covered by tests. |
| 6 | Support JSON as the primary offline-analysis format. | MUST | JSON response contains stable metadata such as bounds, counts, generated timestamp, and arrays/objects suitable for direct notebook or dashboard import. |
| 7 | Optionally support CSV without new dependencies. | SHOULD | If implemented, `format=csv` or equivalent returns `text/csv` with documented columns and bounded row count; unsupported formats return 400. |
| 8 | Reuse indexed store access patterns. | MUST | Implementation uses the existing `(session_id, created_at)` event index or similarly bounded SQL; it does not call `load_all()` for large exports unless the query is safely constrained. |
| 9 | Validate and normalize query parameters. | MUST | Invalid limits, unsupported formats, malformed time bounds, or contradictory filters return 400/422 with useful details rather than silently exporting unexpected data. |
| 10 | Document and test the feature. | MUST | README documents endpoint path, parameters, JSON/CSV examples if applicable, bounds, empty-result behavior, and representative tests cover the expected behavior. |

## Technical Context

Key files:
- `api.py`: `create_app(store, get_diagnostics=None, *, config=None, rate_limit_time_fn=None)` creates the FastAPI app, installs rate limiting, and registers current REST endpoints, `/metrics`, and WebSocket `/ws/tps`.
- `store.py`: `PersistentSessionStore` manages SQLite with WAL mode. It stores session-level rows in `session_tps` and per-call rows in `call_events`; `call_events` has an index on `(session_id, created_at)`.
- `store.py`: existing read helpers include `load(session_id)`, `load_all()`, `load_events(session_id, since=None, until=None, limit=100)`, `aggregate_by_model(session_id, since=None)`, `aggregate_by_provider(session_id, since=None)`, `count()`, and `event_count()`.
- `tests/test_api.py`: covers health, session TPS, sessions list, summary, API startup, and current error behavior.
- `tests/test_event_storage.py`: covers call event schema, recording, bounded loading by time and limit, aggregation, expiry, and event counts.
- `README.md`: documents API enablement, endpoint list, event/trend query parameters, WebSocket format, Prometheus behavior, and local-only CORS note.

Current endpoint constraints:
- `GET /api/v1/events/{session_id}` already supports `since`, `until`, and `limit` but only for one session and only returns events.
- `GET /api/v1/trends/{session_id}` aggregates by model/provider for one session.
- `GET /api/v1/sessions` loads all session summaries and is not framed as an export API.
- `GET /api/v1/summary` returns only global aggregate counts.

Existing bead context constrains implementation to `api.py`, `store.py`, `README.md`, `tests/test_api.py`, and `tests/test_event_storage.py`, while forbidding `.beads/beads.db`, `.env.local`, credentials, and plan/task artifacts. This repair pass writes only create-phase artifacts under `.beads/artifacts/her-feat-historical-tps-export-s3i/`.

## Approach

Add a bounded, read-only export route in `api.py` that composes existing persisted data into a stable export envelope. Prefer an endpoint under `/api/v1/export/history` or a similarly versioned path so the feature is additive. The JSON envelope should include metadata (`generated_at`, `filters`, `counts`, `format`) plus `sessions` and `events` sections. The route should require or enforce safe bounds: a caller can export one session with optional time bounds, a time window with an explicit limit, or another documented bounded combination, but there should be no unbounded all-history export.

Use `PersistentSessionStore.load_events()` for session-scoped event reads when it satisfies the endpoint contract. If cross-session or combined summary/event export is required, add a narrowly scoped store helper that accepts `since`, `until`, and `limit`, orders deterministically, and uses bounded SQL rather than loading everything into Python. Keep CSV support optional and dependency-free via Python standard library `csv` if selected; JSON remains the required format.

Testing should instantiate the FastAPI app with a temporary `PersistentSessionStore`, seed session rows and call events, and verify bounded JSON output, limit enforcement, time filtering, empty result behavior, store-unavailable behavior, unsupported format handling, and route compatibility with existing endpoints. Documentation should explain that the endpoint is for offline analysis and dashboard import, not remote public exposure.

**Alternatives considered:** Direct SQLite access by users was rejected because it bypasses API contracts and requires knowledge of internal schema. Extending `/api/v1/events/{session_id}` alone was rejected because offline workflows need a documented export envelope and may need session summary metadata alongside events. Adding a background export job or file writer was rejected because it adds state and operational complexity beyond a bounded local read API. A fully unbounded all-history endpoint was rejected because it could load too much data into memory and block the local API process.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Export requests accidentally perform unbounded reads or serialize too much data. | Med | High | Require explicit bounds, enforce sane default/max limits, and test large-limit rejection or clamping. |
| New endpoint duplicates or conflicts with existing event/trend routes. | Low | Med | Use an additive `/api/v1/export/*` route and preserve existing route behavior through regression tests. |
| Empty result semantics are confusing for import clients. | Med | Med | Document whether empty bounded exports return 200 with empty arrays or 404, and test the chosen behavior. |
| CSV support creates inconsistent field coverage between sessions and events. | Med | Low | Treat CSV as optional; if included, document columns and possibly restrict CSV to event rows plus metadata headers omitted or flattened. |
| Time filtering relies on lexicographic ISO timestamp comparisons. | Low | Med | Continue using existing ISO 8601 storage convention, validate timestamp inputs, and prefer UTC examples in docs. |
| Cross-session export requires new SQL not covered by existing helper methods. | Med | Med | Add a minimal bounded store helper with targeted tests instead of reusing `load_all()` for events. |
| Dashboard/import users expose the local API beyond localhost. | Low | High | Preserve current local defaults and README warning that the API is not suitable for public exposure without a reverse proxy/security layer. |

## Tasks (for epics)

| Task | Depends On | Parallel | Files |
|------|-----------|----------|-------|
| N/A — single feature bead. | N/A | N/A | N/A |

## Acceptance Criteria

- Bounded historical export endpoint is additive and versioned under `/api/v1/`.
- Valid bounded requests return stable JSON metadata plus requested session/event data.
- Invalid or unsafe requests fail with documented 400/422 behavior instead of exporting unbounded data.
- Store-unavailable requests return 503 consistently with existing API handlers.
- Existing REST, diagnostics, metrics, and WebSocket routes retain current behavior.
- README and tests describe and verify export usage, bounds, and empty-result behavior.

## Success Criteria

- [ ] Historical export endpoint returns bounded JSON for seeded session and event data.
    - Verify: `python -m pytest tests/test_api.py tests/test_event_storage.py -k export`
- [ ] Export requests cannot perform unbounded reads.
    - Verify: tests cover missing bounds, default limit behavior, max limit behavior, and invalid limit handling.
- [ ] Existing REST, diagnostics, metrics, and WebSocket endpoints are not regressed.
    - Verify: `python -m pytest tests/test_api.py tests/test_event_storage.py`
- [ ] Store-unavailable and empty-result behavior is documented and tested.
    - Verify: focused API tests assert 503 and chosen empty-result response semantics.
- [ ] README documents endpoint path, parameters, response shape, examples, bounds, and offline-analysis/dashboard-import usage.
    - Verify: README contains a historical export section with JSON example and CSV details if CSV is implemented.
