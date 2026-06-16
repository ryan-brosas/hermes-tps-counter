## Summary

Adds a batch session TPS endpoint so dashboard, automation, and observability clients can request stats for a bounded set of known session IDs in one HTTP request, avoiding all-session fetches or N single-session calls.

## What Changed

- Added `BatchSessionTPSRequest` and `BatchSessionTPSResponse` models in `api.py`.
- Added `POST /api/v1/sessions/batch/tps` under the existing `/api/v1` namespace.
- Deduplicates requested session IDs in first-seen order before lookup.
- Returns found sessions using the same fields as `SessionTPSResponse` and missing IDs in `missing_session_ids`.
- Preserves existing 503 database-unavailable semantics when the persistence store is unavailable.
- Added batch endpoint tests covering full hit, partial miss, all miss, duplicates, validation, and store-unavailable behavior.
- Updated README REST API documentation with request and response examples.

## Acceptance Criteria

- [x] Provide a batch session TPS endpoint under `/api/v1` — `POST /api/v1/sessions/batch/tps` implemented and covered by tests.
- [x] Preserve existing endpoint contracts — `pytest tests/test_api.py -v` passed (35 passed).
- [x] Handle missing sessions deterministically — partial-miss and all-miss tests assert `missing_session_ids` with HTTP 200.
- [x] Validate request input — empty and non-list `session_ids` tests return 422; duplicates are normalized.
- [x] Fail cleanly when persistence is unavailable — store-None batch test returns HTTP 503.
- [x] Avoid unnecessary database fan-out where practical — endpoint deduplicates before lookup, bounding calls to unique requested IDs.
- [x] Document API usage — README endpoint table and examples include `/api/v1/sessions/batch/tps`.

## Review

**Verdict:** APPROVE
**Findings:** 0 critical, 0 high, 0 medium, 0 low

## Changed Files

| File | Change |
|---|---|
| `api.py` | Added batch request/response models and endpoint handler. |
| `tests/test_api.py` | Added batch endpoint coverage. |
| `README.md` | Documented endpoint and examples. |
| `.beads/issues.jsonl` | Bead claim/close metadata. |
| `.beads/artifacts/her-feat-batch-session-stats-ojy/*` | PRD, plan, evidence, review, and progress artifacts. |

## Verification

- `pytest tests/test_api.py -v -k batch` — passed (7 passed)
- `pytest tests/test_api.py -v` — passed (35 passed)
- `git diff --check origin/feat/her-feat-builtin-dashboard-ov3...HEAD` — passed
- `br lint her-feat-batch-session-stats-ojy --json` — passed (0 issues)

## Artifacts

- PRD: `.beads/artifacts/her-feat-batch-session-stats-ojy/prd.md`
- Plan: `.beads/artifacts/her-feat-batch-session-stats-ojy/plan.md`
- Evidence: `.beads/artifacts/her-feat-batch-session-stats-ojy/completion-evidence.json`
- Review: `.beads/artifacts/her-feat-batch-session-stats-ojy/review-report.md`

## Br Bead

- Bead: `her-feat-batch-session-stats-ojy`
- Status: closed
- Priority: P2
