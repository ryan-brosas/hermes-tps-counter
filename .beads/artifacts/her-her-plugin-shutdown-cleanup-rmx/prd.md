# PRD: Plugin Shutdown Cleanup (`unregister()`)

## Problem

The `register()` function in `__init__.py` creates resources that are never cleaned up:

1. **SQLite connection leak**: `PersistentSessionStore` opens a SQLite connection with WAL journal mode. `_STORE.close()` is never called on shutdown. This means WAL checkpointing is not finalized, and the connection leaks on plugin reload.

2. **API server thread leak**: `_start_api_server()` spawns a daemon thread running uvicorn. `_stop_api_server()` exists and sets `server.should_exit = True`, but is never wired to any lifecycle hook. On plugin reload, a new server thread is started while the old one may still be running (briefly, until process exit).

3. **No Hermes lifecycle integration**: Hermes supports an `on_shutdown` or `unregister` hook pattern, but the plugin does not register one. This is the root cause of both issues above.

## Proposed Solution

Add an `unregister(ctx)` function to `__init__.py` that:

1. Calls `_stop_api_server()` if the API server is running
2. Calls `_STORE.close()` if the persistent store is initialized
3. Clears all in-memory state (`_SESSIONS`, `_MODELS`, `_PROVIDERS`)
4. Resets the `_prometheus_enabled` flag
5. Registers itself as an `on_shutdown` hook in `register()`

### Code Changes

**`__init__.py`**:
- Add `def unregister(ctx: Any) -> None:` function
- In `register()`, add: `ctx.register_hook("on_shutdown", unregister)`

### Tests

**`tests/test_core.py`** — New test class `TestUnregister`:
- `test_unregister_closes_store`: Verify `_STORE.close()` is called
- `test_unregister_stops_api_server`: Verify `_API_SERVER.should_exit` is set to `True`
- `test_unregister_clears_state`: Verify `_SESSIONS`, `_MODELS`, `_PROVIDERS` are emptied
- `test_unregister_noop_when_no_store`: Verify no crash when `_STORE` is None
- `test_unregister_noop_when_no_server`: Verify no crash when `_API_SERVER` is None
- `test_register_wires_shutdown_hook`: Verify `register()` calls `ctx.register_hook("on_shutdown", ...)` with 3 total hooks

## Acceptance Criteria

1. `unregister(ctx)` exists and cleanly releases all resources
2. `register()` hooks `unregister` via `ctx.register_hook("on_shutdown", unregister)`
3. All new behavior is covered by tests in `test_core.py`
4. No regressions in existing tests: `pytest tests/ -v` passes

## Out of Scope

- Graceful drain of in-flight API requests (the server is local-only, low risk)
- Persisting `_MODELS`/`_PROVIDERS` state before clearing (that's a separate gap)
