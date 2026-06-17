---
purpose: Task decomposition with dependency tracking
updated: 2026-06-16
---

# Tasks: her-her-plugin-shutdown-cleanup-rmx

## Task Metadata

```yaml
id: "1.1"
depends_on: []
parallel: false
conflicts_with: []
files: ["__init__.py"]
estimated_minutes: 20
```

## 1. Core Implementation

### 1.1 Add unregister(ctx) function

```yaml
depends_on: []
parallel: false
files: ["__init__.py"]
estimated_minutes: 15
```

- [ ] Add `def unregister(ctx: Any) -> None:` after the `_stop_api_server()` function (around line 518)
- [ ] Guard: call `_stop_api_server()` (already handles `_API_SERVER is None` internally)
- [ ] Guard: if `_STORE is not None`, call `_STORE.close()`
- [ ] With `_STATE_LOCK`: clear `_SESSIONS`, `_MODELS`, `_PROVIDERS`
- [ ] Reset `_prometheus_enabled = False`
- [ ] Reset `_WS_MANAGER = None`, `_EVENT_LOOP = None`
- [ ] Add docstring explaining this is the Hermes shutdown hook

### 1.2 Wire shutdown hook in register()

```yaml
depends_on: ["1.1"]
parallel: false
files: ["__init__.py"]
estimated_minutes: 5
```

- [ ] In `register()` (line 529), add after existing hook registrations (after line 549):
  `ctx.register_hook("on_shutdown", unregister)`
- [ ] This brings total hooks to 3: post_api_request, on_session_end, on_shutdown

## 2. Testing

### 2.1 Write TestUnregister test class

```yaml
depends_on: ["1.2"]
parallel: false
files: ["tests/test_core.py"]
estimated_minutes: 25
```

- [ ] Add new class `TestUnregister` in `tests/test_core.py`
- [ ] `test_unregister_closes_store`: Set `_STORE` to a mock, call `unregister(mock_ctx)`, assert `_STORE.close()` was called
- [ ] `test_unregister_stops_api_server`: Set `_API_SERVER` to a mock with `should_exit=False`, call `unregister`, assert `should_exit is True`
- [ ] `test_unregister_clears_state`: Populate `_SESSIONS`, `_MODELS`, `_PROVIDERS`, call `unregister`, assert all empty
- [ ] `test_unregister_noop_when_no_store`: Set `_STORE = None`, call `unregister`, no crash
- [ ] `test_unregister_noop_when_no_server`: Set `_API_SERVER = None`, call `unregister`, no crash
- [ ] `test_register_wires_shutdown_hook`: Mock `ctx`, call `register(ctx)`, assert `ctx.register_hook` called with `"on_shutdown"` and `unregister` function

## 3. Verification

### 3.1 Full regression test

```yaml
depends_on: ["2.1"]
parallel: false
files: []
estimated_minutes: 10
```

- [ ] `pytest tests/ -v` — all tests pass, no regressions
