---
purpose: Task decomposition with dependency tracking
updated: 2026-06-16
---

# Tasks: her-websocket-tps-streaming-90p

## Task Metadata

```yaml
id: "1"
depends_on: []
parallel: false
conflicts_with: []
files: ["api.py"]
estimated_minutes: 25
```

## 1. ConnectionManager Class

### 1.1 Implement ConnectionManager in api.py

```yaml
depends_on: []
parallel: false
files: ["api.py"]
estimated_minutes: 25
```

- [ ] Add `ConnectionManager` class to `api.py` with:
  - `__init__`: `self._lock = threading.Lock()`, `self._clients: set[WebSocket] = set()`
  - `async connect(ws: WebSocket)`: accept + add to set (under lock)
  - `disconnect(ws: WebSocket)`: remove from set (under lock)
  - `async broadcast(message: dict)`: iterate clients, send JSON, catch/disconnect on error
  - `count` property: len of clients set (under lock)
- [ ] Use `threading.Lock` (same pattern as `_STATE_LOCK` in `__init__.py`) since hook calls come from threading context
- [ ] Use `asyncio.create_task` for individual sends in broadcast to prevent slow client blocking others
- [ ] Wrap each send in try/except — remove dead clients on `WebSocketDisconnect` or `ConnectionError`

**Verification:** `python -c "from api import ConnectionManager; cm = ConnectionManager(); print(cm.count)"`

## 2. WebSocket Endpoint

### 2.1 Add /ws/tps endpoint to FastAPI app

```yaml
depends_on: ["1.1"]
parallel: false
files: ["api.py"]
estimated_minutes: 15
```

- [ ] In `create_app(store)`, create a module-level `ConnectionManager` instance
- [ ] Add `@app.websocket("/ws/tps")` endpoint:
  - `await manager.connect(websocket)`
  - Try/finally loop: `while True: await websocket.receive_text()` (keeps connection alive, detects disconnect)
  - On `WebSocketDisconnect`: `manager.disconnect(websocket)`
- [ ] The receive_text loop is only for detecting disconnects — clients don't need to send anything

**Verification:** `python -c "from api import create_app; app = create_app(None); print('app created')"`

### 2.2 Add broadcast function and integrate with hook

```yaml
depends_on: ["2.1"]
parallel: false
files: ["api.py", "__init__.py"]
estimated_minutes: 20
```

- [ ] Add `async def broadcast_tps_update(manager: ConnectionManager, snapshot: dict)` function in `api.py`:
  - Build message: `{"type": "tps_update", "data": snapshot, "timestamp": <iso>}`
  - Call `await manager.broadcast(message)`
- [ ] In `__init__.py`, after `agent._tps_snapshot = snapshot` (line ~412), add broadcast trigger:
  - If `manager` is available, schedule broadcast via `asyncio.run_coroutine_threadsafe(broadcast_tps_update(manager, snapshot), loop)`
  - Store the event loop reference in `create_app` or module-level variable
  - Guard with try/except — broadcast failure must never crash the hook
- [ ] The broadcast is fire-and-forget — hook doesn't await the result

**Verification:** Import check + `pytest tests/test_api.py -x` (existing tests still pass)

## 3. WebSocket Tests

### 3.1 Unit tests for ConnectionManager

```yaml
depends_on: ["1.1"]
parallel: false
files: ["tests/test_websocket.py"]
estimated_minutes: 20
```

- [ ] Create `tests/test_websocket.py` with fixtures:
  - `store` fixture (same pattern as `test_api.py`)
  - `app` fixture from `create_app(store)`
  - `mock_hermes_cli` autouse fixture (same as `test_api.py`)
- [ ] `TestConnectionManager` class:
  - `test_connect_adds_client`: mock WebSocket, verify count increases
  - `test_disconnect_removes_client`: connect + disconnect, verify count decreases
  - `test_broadcast_sends_to_all`: connect 2 mock clients, broadcast, verify both received JSON
  - `test_broadcast_handles_dead_client`: connect 1 good + 1 dead client, verify good client still receives
  - `test_count_property`: verify count reflects active clients

**Verification:** `pytest tests/test_websocket.py::TestConnectionManager -x -v`

### 3.2 Integration test for WebSocket endpoint

```yaml
depends_on: ["2.1", "2.2", "3.1"]
parallel: false
files: ["tests/test_websocket.py"]
estimated_minutes: 15
```

- [ ] `TestWebSocketEndpoint` class:
  - `test_websocket_connect_disconnect`: use `TestClient.websocket_connect("/ws/tps")`, verify no errors
  - `test_websocket_receives_broadcast`: connect, trigger `_on_post_api_request` via hook, verify client receives `tps_update` JSON
  - `test_websocket_message_format`: verify message has `type`, `data`, `timestamp` fields
  - `test_multiple_clients_receive_broadcast`: connect 2 clients, trigger hook, verify both receive
  - `test_websocket_disconnect_cleanup`: connect/disconnect, verify manager count is 0
- [ ] Use `fastapi.testclient.TestClient` with `with client.websocket_connect("/ws/tps") as ws:` pattern

**Verification:** `pytest tests/test_websocket.py::TestWebSocketEndpoint -x -v`

## 4. Full Regression

### 4.1 Verify all tests pass

```yaml
depends_on: ["2.2", "3.2"]
parallel: false
files: []
estimated_minutes: 5
```

- [ ] `pytest tests/ -x` — all existing tests + new WebSocket tests pass
- [ ] Verify no import errors: `python -c "from api import ConnectionManager, create_app"`
- [ ] Verify no changes to `store.py`, `prometheus_metrics.py`, or test files outside `tests/test_websocket.py`

**Verification:** `pytest tests/ -x`
