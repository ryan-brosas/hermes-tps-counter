---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-feat-batch-session-stats-ojy

## Task Metadata

```yaml
id: "1.1"
depends_on: []
parallel: false
conflicts_with: []
files: ["tests/test_api.py"]
estimated_minutes: 5
```

## 1. Setup

### 1.1 Verify existing tests pass

```yaml
depends_on: []
parallel: false
files: ["tests/test_api.py"]
```

- [ ] Run `pytest tests/test_api.py -v` to confirm baseline passes
- [ ] Document any pre-existing failures (if any) for context

## 2. Core Implementation

### 2.1 Add Pydantic request/response models

```yaml
depends_on: ["1.1"]
parallel: false
files: ["api.py"]
estimated_minutes: 15
```

- [ ] Add `BatchSessionTPSRequest` model with `session_ids: List[str]` field
  - Field validation: min_items=1 (reject empty lists via Pydantic)
  - Use `Field(..., min_items=1)` for validation
- [ ] Add `BatchSessionTPSResponse` model with:
  - `sessions: List[SessionTPSResponse]` — found sessions
  - `missing_session_ids: List[str]` — IDs not found
- [ ] Place models near existing `SessionTPSResponse` and `SessionListResponse` in `api.py`

### 2.2 Implement batch endpoint

```yaml
depends_on: ["2.1"]
parallel: false
files: ["api.py"]
estimated_minutes: 25
```

- [ ] Add `POST /api/v1/sessions/batch/tps` endpoint
  - **IMPORTANT:** Declare this route BEFORE `/api/v1/sessions/{session_id}/tps` to avoid route ambiguity (static path before dynamic path parameter)
- [ ] Accept `BatchSessionTPSRequest` as request body
- [ ] Implement logic:
  1. Check `store` is not `None`; return 503 if unavailable
  2. Deduplicate `session_ids` preserving first-seen order
  3. For each unique session ID, call `store.load(session_id)`
  4. Separate found sessions from missing IDs
  5. Return `BatchSessionTPSResponse(sessions=found, missing_session_ids=missing)`
- [ ] Ensure response uses same `SessionTPSResponse` fields as single-session endpoint
- [ ] Handle edge cases:
  - All sessions found → `missing_session_ids` is empty list
  - No sessions found → `sessions` is empty list, all IDs in `missing_session_ids`
  - Empty request body → Pydantic validation error (422)
  - Non-list input → Pydantic validation error (422)

### 2.3 (Optional) Add store-level batch loader

```yaml
depends_on: ["1.1"]
parallel: true  # Can run in parallel with 2.1
files: ["store.py"]
estimated_minutes: 15
```

- [ ] Add `load_many(session_ids: List[str]) -> Dict[str, Optional[dict]]` method to `PersistentSessionStore`
  - Reuse existing `_row_to_dict` and thread lock
  - Return mapping of session_id → data (or None if not found)
  - Keep read-only; do not alter schema
- [ ] **Decision point:** If repeated `load()` calls are acceptable for expected batch sizes (small local API), skip this task and use direct `load()` calls in endpoint

## 3. Testing

### 3.1 Write batch endpoint tests

```yaml
depends_on: ["2.2"]
parallel: false
files: ["tests/test_api.py"]
estimated_minutes: 20
```

- [ ] **Test: Full hit** — Request with 2+ existing session IDs returns all in `sessions`, empty `missing_session_ids`
- [ ] **Test: Partial miss** — Request with mix of existing and non-existing IDs returns found in `sessions`, missing in `missing_session_ids`
- [ ] **Test: All miss** — Request with only non-existing IDs returns empty `sessions`, all IDs in `missing_session_ids`
- [ ] **Test: Duplicate IDs** — Request with duplicate session IDs returns deduplicated results (no duplicate response rows)
- [ ] **Test: Empty input** — Request with `{ "session_ids": [] }` returns 422 validation error
- [ ] **Test: Invalid input** — Request with `{ "session_ids": "not-a-list" }` returns 422 validation error
- [ ] **Test: Store unavailable** — When `store` is `None`, returns 503
- [ ] **Test: Existing endpoints unchanged** — Run existing tests to verify no regression

## 4. Documentation

### 4.1 Update README

```yaml
depends_on: ["3.1"]
parallel: false
files: ["README.md"]
estimated_minutes: 10
```

- [ ] Add batch endpoint to REST API endpoint table
- [ ] Add request/response JSON examples including:
  - Full hit example
  - Partial miss example with `missing_session_ids`
- [ ] Note that duplicate IDs are normalized
- [ ] Document 422 validation behavior for empty/invalid input

## 5. Verification

### 5.1 Full verification

```yaml
depends_on: ["4.1"]
parallel: false
files: ["tests/test_api.py", "README.md"]
estimated_minutes: 5
```

- [ ] Run `pytest tests/test_api.py -v` — all tests pass
- [ ] Run `pytest tests/test_api.py -v -k batch` — batch tests pass
- [ ] Verify README contains batch endpoint documentation
- [ ] Verify no existing endpoint behavior changed
