---
purpose: Wave-sequenced implementation plan
updated: 2026-06-16
---

# Plan: her-websocket-tps-streaming-90p

**Goal:** Add a WebSocket endpoint at `/ws/tps` that streams real-time TPS snapshots to connected clients after each LLM API call.

## Graph Context

- **Blast radius:** `api.py`, `__init__.py`, `tests/test_websocket.py` (new), `conftest.py` (minor)
- **Unblocks:** Future dashboard frontend (Phase 4), notification system (Phase 5)
- **Blocked by:** None (REST API, event storage, persistence all closed)
- **Critical path:** No (leaf node, no downstream dependents)
- **Forecast:** ~85 min estimated (feature type, single agent)

## Observable Truths

1. A client can connect to `ws://host:port/ws/tps` and receive valid JSON messages
2. Every `_on_post_api_request` hook call broadcasts a TPS snapshot to all connected WebSocket clients
3. Client disconnect does not crash the server or leak resources
4. All existing tests (`pytest tests/ -x`) pass without modification
5. New WebSocket tests (`pytest tests/test_websocket.py -x`) verify connect/broadcast/disconnect

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| ConnectionManager class | Thread-safe client tracking + broadcast | `api.py` | Need |
| `/ws/tps` endpoint | WebSocket endpoint in FastAPI app | `api.py` | Need |
| Broadcast integration | Hook triggers broadcast after state update | `__init__.py` | Need |
| WebSocket tests | Unit + integration test coverage | `tests/test_websocket.py` | Need |
| Existing tests pass | Backward compatibility proof | `pytest tests/ -x` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | ConnectionManager class, broadcast integration | No (same file) | None | `python -c "from api import ConnectionManager"` |
| 2 | WebSocket endpoint + hook integration | No | Wave 1 complete | `python -c "from api import create_app; app = create_app(None)"` |
| 3 | WebSocket tests | No | Wave 2 complete | `pytest tests/test_websocket.py -x` |
| 4 | Full regression | No | Wave 3 complete | `pytest tests/ -x` |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
pytest tests/test_websocket.py -x -v    # New WebSocket tests
pytest tests/ -x                         # Full regression
python -c "from api import ConnectionManager, create_app; print('imports ok')"  # Smoke
```
