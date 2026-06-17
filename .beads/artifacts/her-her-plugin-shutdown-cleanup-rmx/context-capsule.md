---
purpose: Agent spawn context for a bead
updated: 2026-06-16
---

# Context Capsule: her-her-plugin-shutdown-cleanup-rmx

## Objective

Add `unregister(ctx)` function to `__init__.py` that cleanly releases all plugin resources (SQLite store, API server thread, in-memory state) and wire it as an `on_shutdown` hook in `register()`.

## Key Patterns

- `register()` hook pattern — `ctx.register_hook("name", callback)` is how Hermes plugins wire lifecycle hooks. Two hooks already registered: `post_api_request` and `on_session_end`. Reference: `__init__.py:548-549`
- `_stop_api_server()` — Already exists and handles `_API_SERVER is None` guard internally. Just call it. Reference: `__init__.py:508-517`
- `_STORE.close()` — PersistentSessionStore has a `.close()` method. Must guard with `if _STORE is not None`. Reference: `__init__.py:539-546`
- Global state pattern — `_SESSIONS`, `_MODELS`, `_PROVIDERS` are module-level dicts protected by `_STATE_LOCK`. Clear them inside the lock. Reference: `__init__.py:74-77`
- `_prometheus_enabled` — Module-level bool flag. Reset to `False`. Reference: `__init__.py:86`
- `_WS_MANAGER`, `_EVENT_LOOP` — Module-level state set during API server start. Reset to `None`. Reference: `__init__.py:89-90`

## Constraints

1. `unregister(ctx)` must never raise — all cleanup must be try/except guarded
2. Must be a no-op when resources were never initialized (store=None, server=None)
3. Must not break existing tests — `pytest tests/ -v` must pass after changes
4. Only modify `__init__.py` and `tests/test_core.py` — no other files
5. Do not change existing function signatures or behavior

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Implement unregister + wire hook | `__init__.py` — add function + one line in register() | Any other .py files |
| Write tests | `tests/test_core.py` — add TestUnregister class | `__init__.py` or other test files |

## Graph Context

- **Blast radius:** `__init__.py`, `tests/test_core.py` only
- **Related beads:** None (isolated node in dependency graph)
- **File history:** No prior beads touch these files yet
