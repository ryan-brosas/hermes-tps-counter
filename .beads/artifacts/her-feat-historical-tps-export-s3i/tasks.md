---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-feat-historical-tps-export-s3i

## Task Metadata

```yaml
id: "1.1"
depends_on: []
parallel: true
conflicts_with: []
files: ["store.py", "tests/test_event_storage.py"]
estimated_minutes: 25
```

## 1. Store Layer — Bounded Cross-Session Export

### 1.1 Add bounded export helpers to PersistentSessionStore

```yaml
depends_on: []
parallel: false
files: ["store.py", "tests/test_event_storage.py"]
```

- [ ] Add `export_events(since=None, until=None, limit=100, max_limit=1000)` to `PersistentSessionStore`
  - Returns `List[Dict[str, Any]]` of call_events rows across all sessions
  - Enforces `min(limit, max_limit)` to prevent unbounded reads
  - Uses bounded SQL: `SELECT * FROM call_events WHERE 1=1 [AND created_at >= ?] [AND created_at <= ?] ORDER BY created_at DESC LIMIT ?`
  - Does NOT call `load_all()` — uses direct bounded SQL query
  - Returns empty list on error (consistent with existing `load_events` pattern)
- [ ] Add `export_sessions(session_ids=None, since=None, until=None, limit=100, max_limit=1000)` to `PersistentSessionStore`
  - Returns `List[Dict[str, Any]]` of session_tps rows
  - If `session_ids` provided, filters to those sessions via `IN (?)` clause
  - If `since`/`until` provided, filters by `updated_at` range
  - Enforces `min(limit, max_limit)` to prevent unbounded reads
  - Returns empty list on error
- [ ] Add SQL constants for the new queries (follow existing `_LOAD_EVENTS`, `_AGGREGATE_BY_MODEL` pattern)
- [ ] Write tests in `tests/test_event_storage.py`:
  - `test_export_events_empty` — returns empty list on fresh DB
  - `test_export_events_returns_seeded_data` — records events, exports, verifies fields
  - `test_export_events_with_since_filter` — only events after timestamp returned
  - `test_export_events_with_until_filter` — only events before timestamp returned
  - `test_export_events_respects_limit` — limit caps returned rows
  - `test_export_events_max_limit_clamped` — max_limit overrides excessive limit
  - `test_export_events_cross_session` — exports events from multiple sessions
  - `test_export_sessions_empty` — returns empty list on fresh DB
  - `test_export_sessions_returns_seeded_data` — saves sessions, exports, verifies fields
  - `test_export_sessions_with_session_ids_filter` — filters to requested sessions only
  - `test_export_sessions_respects_limit` — limit caps returned rows

## 2. API Layer — Export Endpoint

### 2.1 Add response models and export endpoint to api.py

```yaml
depends_on: ["1.1"]
parallel: false
files: ["api.py", "tests/test_api.py"]
```

- [ ] Add Pydantic response models:
  - `ExportQueryParams` — Query parameter model with `session_id: Optional[str]`, `since: Optional[str]`, `until: Optional[str]`, `limit: int = 100`, `max int = 1000`, `format: str = "json"`
  - `ExportMetadata` — `generated_at: str`, `filters: Dict[str, Any]`, `session_count: int`, `event_count: int`, `format: str`
  - `ExportResponse` — `metadata: ExportMetadata`, `sessions: List[Dict[str, Any]]`, `events: List[Dict[str, Any]]`
- [ ] Add `GET /api/v1/export/history` endpoint to `create_app`:
  - Accepts query params: `session_id`, `since`, `until`, `limit` (default 100, max 1000), `format` (default "json")
  - Validates: limit > 0, limit <= max_limit, format in ("json", "csv"), timestamp format if provided
  - Returns 503 if store is None (consistent with existing endpoints)
  - Returns 400/422 for invalid parameters with descriptive error message
  - Calls `store.export_sessions(...)` and `store.export_events(...)` with bounded params
  - If `session_id` provided, passes it to session export; events are always cross-session unless filtered
  - For `format=json`: returns `ExportResponse` with metadata + data
  - For `format=csv`: returns `text/csv` response with flattened event rows (optional, dependency-free via stdlib `csv`)
  - For unsupported format: returns 400
  - Returns 200 with empty arrays when no data matches (documented behavior)
- [ ] Write tests in `tests/test_api.py`:
  - `test_export_history_returns_200_with_json` — basic JSON export with seeded data
  - `test_export_history_503_when_store_none` — store unavailable returns 503
  - `test_export_history_with_session_id_filter` — filters to specific session
  - `test_export_history_with_time_bounds` — since/until filters work
  - `test_export_history_respects_limit` — limit parameter caps results
  - `test_export_history_rejects_invalid_limit` — limit <= 0 or > max returns 400/422
  - `test_export_history_rejects_unsupported_format` — format=xml returns 400
  - `test_export_history_empty_result` — no matching data returns 200 with empty arrays
  - `test_export_history_csv_format` — format=csv returns text/csv with correct columns (if CSV implemented)
  - `test_export_history_metadata_fields` — response contains generated_at, filters, counts
  - `test_existing_endpoints_not_regressed` — health, sessions, summary, events, trends all still work

## 3. Documentation — README Export Section

### 3.1 Add historical export documentation to README.md

```yaml
depends_on: ["2.1"]
parallel: false
files: ["README.md"]
```

- [ ] Add "Historical Export" section to README.md after existing API documentation:
  - Endpoint path: `GET /api/v1/export/history`
  - Description: bounded export for offline analysis and dashboard import
  - Query parameters table: `session_id`, `since`, `until`, `limit`, `format`
  - JSON response example with metadata + sessions + events
  - CSV response example (if CSV implemented)
  - Bounds explanation: default limit, max limit, required or enforced bounds
  - Empty result behavior documentation
  - Error responses: 400 (invalid params), 503 (store unavailable)
  - Usage guidance: intended for notebooks, spreadsheets, BI tools, dashboard import — not for remote public exposure
  - Local-only API reminder with security warning

## 4. Verification

### 4.1 Full regression test suite

```yaml
depends_on: ["1.1", "2.1", "3.1"]
parallel: false
```

- [ ] `python -m pytest tests/test_api.py tests/test_event_storage.py -v` — all tests pass
- [ ] `python -m pytest tests/test_api.py -k export -v` — export-specific tests pass
- [ ] `python -m pytest tests/test_event_storage.py -k export -v` — export store tests pass
- [ ] `grep -c "export/history" README.md` — README contains export section
