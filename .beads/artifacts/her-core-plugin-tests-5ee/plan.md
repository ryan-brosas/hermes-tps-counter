---
purpose: Wave-sequenced implementation plan
updated: 2026-06-16
---

# Plan: her-core-plugin-tests-5ee

**Goal:** Add comprehensive pytest coverage for the core plugin behavior — TPS calculation, session management, per-model tracking, lifecycle cleanup, and status bar integration.

## Graph Context

- **Blast radius:** `tests/test_core.py` (new file only — no existing files modified)
- **Unblocks:** None (leaf node)
- **Blocked by:** None
- **Critical path:** No
- **Forecast:** ~66 minutes (estimate 60m, depth 1)

## Observable Truths

1. `pytest tests/test_core.py -v` passes with 0 failures and 20+ test methods
2. All existing tests still pass: `pytest tests/ -v` returns 0 failures
3. Every requirement in the PRD has at least one corresponding test method
4. Global state (`_SESSIONS`, `_MODELS`, `_PROVIDERS`) is clean after each test

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| test_core.py | Core plugin test coverage | `tests/test_core.py` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | Test fixtures + _SessionTPS tests | Yes (within wave) | None | `pytest tests/test_core.py::TestSessionTPS -v` |
| 2 | _ModelTPS + get_model_stats + get_tps_stats | Yes (within wave) | Wave 1 fixtures | `pytest tests/test_core.py::TestModelTPS -v` |
| 3 | Session lifecycle (get_session, eviction, cleanup) | Yes (within wave) | Wave 1 fixtures | `pytest tests/test_core.py::TestEviction -v` |
| 4 | Status bar snapshot + persistence integration | Yes (within wave) | Wave 1 fixtures | `pytest tests/test_core.py::TestStatusBarSnapshot -v` |
| 5 | Full suite verification | No | Waves 1-4 | `pytest tests/ -v` |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
pytest tests/test_core.py -v
pytest tests/ -v
```
