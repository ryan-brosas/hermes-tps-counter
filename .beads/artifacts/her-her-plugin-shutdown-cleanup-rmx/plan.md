---
purpose: Wave-sequenced implementation plan
updated: 2026-06-16
---

# Plan: her-her-plugin-shutdown-cleanup-rmx

**Goal:** Add `unregister(ctx)` shutdown hook to cleanly release all plugin resources (SQLite store, API server, in-memory state) and wire it into the Hermes lifecycle via `ctx.register_hook("on_shutdown", unregister)`.

## Graph Context

- **Blast radius:** `__init__.py`, `tests/test_core.py` (low — no other beads touch these files yet)
- **Unblocks:** None (no downstream dependencies)
- **Blocked by:** None (fully independent)
- **Critical path:** No — parallel track alongside histogram metrics bead
- **Forecast:** ~85 minutes (feature type, depth 1, single agent)

## Observable Truths

1. `unregister(ctx)` exists and is importable from `__init__`
2. Calling `unregister(ctx)` closes the SQLite store (`_STORE.close()`), stops the API server (`_API_SERVER.should_exit = True`), and clears `_SESSIONS`, `_MODELS`, `_PROVIDERS`
3. `register()` calls `ctx.register_hook("on_shutdown", unregister)` — 3 hooks total registered (post_api_request, on_session_end, on_shutdown)
4. `unregister()` is a no-op (no crash) when `_STORE` is None or `_API_SERVER` is None
5. All new tests pass and no existing tests regress

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| `__init__.py` | `unregister()` function + shutdown hook registration | `__init__.py` | Need |
| `test_core.py` | 6 new tests covering unregister behavior | `tests/test_core.py` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | Task 1: Implement unregister() | No | None | Function exists, handles None guards |
| 2 | Task 2: Wire shutdown hook in register() | No | Wave 1 complete | `register()` calls `ctx.register_hook("on_shutdown", unregister)` |
| 3 | Task 3: Write tests | No | Wave 2 complete | `pytest tests/test_core.py::TestUnregister -v` passes |
| 4 | Task 4: Full regression check | No | Wave 3 complete | `pytest tests/ -v` passes |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
pytest tests/test_core.py::TestUnregister -v
pytest tests/ -v
```
