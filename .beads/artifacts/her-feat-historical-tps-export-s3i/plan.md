---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-feat-historical-tps-export-s3i

**Goal:** Add a bounded, read-only `GET /api/v1/export/history` endpoint to the existing FastAPI app that exports persisted session TPS rows and per-call event rows for offline analysis and dashboard import, with enforced query bounds, JSON primary format, and optional CSV.

## Graph Context

- **Blast radius:** `store.py`, `api.py`, `tests/test_event_storage.py`, `tests/test_api.py`, `README.md` (5 files)
- **Unblocks:** None downstream (leaf feature)
- **Blocked by:** None (no blockers, no dependencies)
- **Critical path:** No (slack=1, parallel with her-feat-batch-session-stats-ojy on track-B)
- **Forecast:** ~85 minutes estimated, ETA 2026-07-08 at current velocity (confidence 0.35)
- **Capacity:** 2 open beads, 170 total minutes, 50% parallelizable, both on parallel tracks

## Observable Truths

1. A user can call `GET /api/v1/export/history` with bounded query parameters and receive a JSON envelope containing `sessions` and `events` arrays with stable metadata.
2. Requests without sufficient bounds, with invalid limits, or with unsupported formats are rejected with 400/422 rather than silently scanning unbounded data.
3. Store-unavailable requests return 503 consistently with existing API handlers.
4. All existing REST, diagnostics, metrics, and WebSocket endpoints retain current behavior (no regression).
5. README documents the endpoint path, parameters, JSON/CSV examples, bounds, and offline-analysis usage.

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Bounded store helper | Cross-session event/session queries with SQL bounds | `store.py` | Need |
| Export API endpoint | `GET /api/v1/export/history` with validation and response models | `api.py` | Need |
| Store helper tests | Bounded query, limit enforcement, empty results, cross-session | `tests/test_event_storage.py` | Need |
| API endpoint tests | JSON response, 503, 400/422, CSV, format negotiation, regression | `tests/test_api.py` | Need |
| README section | Endpoint docs, parameters, examples, bounds, usage guidance | `README.md` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | Store helper: bounded cross-session export methods | No | None — additive to store.py | `cd /home/ryan/repos/hermes-tps-counter && python -m pytest tests/test_event_storage.py -k export -v` |
| 2 | API endpoint: `GET /api/v1/export/history` with validation, response models, format support | No | Wave 1 complete — store helper exists | `cd /home/ryan/repos/hermes-tps-counter && python -m pytest tests/test_api.py -k export -v` |
| 3 | README documentation: endpoint docs, parameters, examples, bounds guidance | No | Wave 2 complete — endpoint is stable | README contains "export" section with JSON example |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter

# Focused export tests
python -m pytest tests/test_event_storage.py -k export -v
python -m pytest tests/test_api.py -k export -v

# Full regression — no existing tests break
python -m pytest tests/test_api.py tests/test_event_storage.py -v

# README contains export section
grep -c "export/history" README.md
```
