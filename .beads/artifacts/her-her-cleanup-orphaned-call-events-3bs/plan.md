---
purpose: Wave-sequenced implementation plan
updated: 2026-06-16
---

# Plan: her-her-cleanup-orphaned-call-events-3bs

**Goal:** Ensure session cleanup (delete, delete_expired, eviction) removes corresponding call_events rows, preventing indefinite orphaned-row accumulation.

## Graph Context

- **Blast radius:** `store.py` (delete path + SQL constants), `__init__.py` (_evict_if_needed), `tests/test_store_delete.py` (new tests)
- **Unblocks:** None directly — this is a standalone bug fix
- **Blocked by:** None
- **Critical path:** No
- **Forecast:** ~45 min

## Observable Truths

1. After `store.delete("s1")`, zero `call_events` rows exist for session `s1`
2. After `store.delete_expired()`, zero `call_events` rows reference sessions absent from `session_tps`
3. After `_evict_if_needed()` evicts a session, `store.load(evicted_id)` returns None and call_events are gone
4. All existing tests continue to pass alongside new cleanup tests

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| PRD | Problem/scope/requirements | `prd.md` | Done |
| Plan | This file | `plan.md` | Done |
| Tasks | Task decomposition | `tasks.md` | Done |
| Context Capsule | Agent spawn context | `context-capsule.md` | Done |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | Add SQL constants + fix `delete()` | No | None | `pytest tests/test_store_delete.py -v` |
| 2 | Fix `delete_expired()` orphan cleanup | No | Wave 1 done | `pytest tests/test_store_delete.py -v` |
| 3 | Fix `_evict_if_needed()` DB cleanup | No | Wave 1 done | `pytest tests/test_core.py -v` |
| 4 | Add tests for all three paths | Yes (parallel) | Waves 1-3 done | `pytest tests/ -v` |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
pytest tests/test_store_delete.py -v
pytest tests/test_event_storage.py -v
pytest tests/test_core.py -v
pytest tests/ -v
```
