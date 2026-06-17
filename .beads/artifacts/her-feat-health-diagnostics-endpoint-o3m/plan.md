---
purpose: Wave-sequenced implementation plan
updated: 2026-06-16
---

# Plan: her-feat-health-diagnostics-endpoint-o3m

**Goal:** Add `GET /api/v1/health/diagnostics` endpoint returning JSON with component-level status for memory, SQLite, Prometheus, WebSocket, and health counters.

## Graph Context

- **Blast radius:** Low — no existing beads touch the target files. `bv --robot-impact` reports risk_score=0, no affected beads.
- **Unblocks:** None downstream (out_degree=0). This is a leaf feature.
- **Blocked by:** None (is_blocked=false, chain_length=0).
- **Critical path:** No — slack=1, not an articulation point. Parallel-safe with track-B (histogram metrics bead).
- **Forecast:** 85 min estimated (45 min base × feature multiplier). Confidence: 0.35 (low velocity history for health label).
- **File hotspots:** No files flagged — fresh territory with no multi-bead contention.

## Observable Truths

What must be TRUE for the goal to be achieved:

1. `GET /api/v1/health/diagnostics` returns HTTP 200 with JSON containing 5 component sections (`memory`, `sqlite`, `prometheus`, `websocket`, `health_counters`)
2. Each component section includes a `status` field (`ok` / `degraded` / `unavailable`) and component-specific detail fields
3. Existing `GET /api/v1/health` endpoint is completely unchanged — all prior tests pass with identical behavior
4. A failing component (e.g., broken store) reports `degraded`/`unavailable` status without crashing the endpoint (graceful degradation)
5. `pytest tests/ -x` passes with zero regressions and `pytest tests/test_api.py -k diagnostics -v` passes all new tests

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Endpoint handler | Diagnostics JSON response | `api.py` | Need |
| Callback interface | In-memory state access without circular import | `api.py` + `__init__.py` | Need |
| Tests | All component states + degradation | `tests/test_api.py` | Need |
| Documentation | Operator-facing endpoint docs | `README.md` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | 1.1 (endpoint), 1.2 (README) | Yes — different files | PRD complete | Endpoint returns 200 with expected JSON shape |
| 2 | 2.1 (wiring), 2.2 (tests) | Yes — different files | Wave 1 complete | `pytest tests/test_api.py -k diagnostics -v` passes |
| 3 | 3.1 (full verification) | No | Wave 2 complete | `pytest tests/ -x` — zero regressions |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
pytest tests/ -x                          # All existing tests pass (no regressions)
pytest tests/test_api.py -k diagnostics -v  # New diagnostic tests pass
```
