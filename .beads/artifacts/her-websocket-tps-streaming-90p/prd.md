---
purpose: Product Requirements Document for a bead
updated: 2026-06-16
---

# PRD: WebSocket real-time streaming endpoint for live TPS data updates

**Bead:** her-websocket-tps-streaming-90p | **Type:** feature | **Priority:** P2
**Created:** 2026-06-16 | **Estimate:** 90 minutes

## Problem

WHEN a user wants to monitor LLM performance in real-time THEN they must poll the REST API repeatedly BECAUSE there is no push-based mechanism to deliver TPS updates as they happen.

**Who is affected?** Dashboard consumers, monitoring integrations, any client needing live TPS data without polling overhead.

**Why now?** The REST API (her-rest-api-tps-endpoints-56b) and per-call event storage (her-per-call-event-storage-f1v) are built. WebSocket streaming is the next prerequisite for the frontend dashboard (Phase 4) and notification system (Phase 5). FastAPI was chosen partly for WebSocket support (Decision #4). Two existing PRDs explicitly list WebSocket as "future work."

## Scope

### In Scope
- WebSocket endpoint at `/ws/tps` in the existing FastAPI app
- ConnectionManager class for tracking connected clients
- Broadcasting TPS snapshots to all connected clients on each hook call
- JSON message format with `type` field for extensibility
- Graceful disconnect handling (no crashes on client drop)
- Thread-safe ConnectionManager for concurrent hook calls
- Tests for ConnectionManager and WebSocket endpoint

### Out of Scope
- Client authentication/authorization (future bead)
- Persistent WebSocket reconnection logic (client-side concern)
- Channel-based filtering (SHOULD, not MUST — nice-to-have)
- Dashboard frontend (Phase 4, separate bead)
- Server-Sent Events alternative (WebSocket chosen)

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | `/ws/tps` WebSocket endpoint in FastAPI app | MUST | Client can connect and receive JSON messages |
| 2 | ConnectionManager with connect/disconnect/broadcast | MUST | Tracks N clients, broadcasts to all, handles drops |
| 3 | Broadcast TPS snapshot on each hook call | MUST | Every `_on_post_api_request` triggers broadcast to all clients |
| 4 | JSON message format with `type` field | MUST | Messages are valid JSON with `type: "tps_update"` |
| 5 | Thread-safe ConnectionManager | MUST | Concurrent hook calls don't corrupt client set |
| 6 | Graceful disconnect handling | MUST | Client disconnect doesn't crash server or leak resources |
| 7 | Tests for ConnectionManager | MUST | Unit tests for connect, disconnect, broadcast, error handling |
| 8 | Tests for WebSocket endpoint | MUST | Integration test: connect, receive message, disconnect |
| 9 | Backward compatible with existing tests | MUST | All existing tests pass without modification |
| 10 | Optional channel filtering | SHOULD | Client can subscribe to specific session_id |
| 11 | Heartbeat/ping for stale connection detection | SHOULD | Dead connections are detected and removed |
| 12 | Rate-limit broadcasts | SHOULD | Slow clients don't cause memory buildup |

## Technical Context

**Key files:**
- `api.py` (162 lines) — FastAPI app factory with REST endpoints. WebSocket endpoint added here.
- `__init__.py` (586 lines) — Plugin hook `_on_post_api_request`. Broadcast trigger point.
- `store.py` (522 lines) — SQLite persistence. Read-only for WebSocket (no changes needed).
- `tests/test_api.py` — Existing API tests. New WebSocket tests follow same patterns.

**Existing patterns:**
- `create_app(store)` factory in `api.py` — WebSocket endpoint added to same app
- `_on_post_api_request(**kwargs)` in `__init__.py` — broadcast called after state update
- `_STATE_LOCK` threading.Lock — ConnectionManager uses same pattern
- `agent._tps_snapshot` dict — same structure broadcast over WebSocket

**Dependencies:**
- FastAPI (already installed) — native WebSocket support via Starlette
- No new packages needed

## Approach

Add a `ConnectionManager` class to `api.py` that maintains a set of connected WebSocket clients. In `_on_post_api_request`, after updating session state, call a broadcast function that sends the TPS snapshot to all connected clients.

The WebSocket endpoint `/ws/tps` accepts connections, registers them with the manager, and enters a receive loop (to detect disconnects). On disconnect, the client is removed from the manager.

**Alternatives considered:**

| Alternative | Why Rejected |
|-------------|-------------|
| Server-Sent Events (SSE) | WebSocket chosen for bidirectional future use (client commands) |
| Separate WebSocket server | FastAPI already supports WebSocket, no need for separate process |
| Redis pub/sub for broadcast | Single-process plugin, no need for message broker |
| Polling via REST API | Defeats the purpose — high latency, wasted requests |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Memory leak from disconnected clients | Medium | Medium | ConnectionManager removes on disconnect, periodic cleanup |
| Thread safety race conditions | Low | High | Use _STATE_LOCK pattern, asyncio-safe broadcast |
| Slow client blocks broadcast | Low | Medium | Use asyncio.create_task for send, timeout on slow clients |
| Breaking existing API tests | Low | High | Add WebSocket tests separately, don't modify existing endpoints |

## Success Criteria

- [ ] Client can connect to `ws://host:port/ws/tps` and receive JSON TPS updates
- [ ] Multiple concurrent clients receive the same broadcast
- [ ] Client disconnect doesn't crash the server
- [ ] All existing tests pass: `pytest tests/ -x`
- [ ] New WebSocket tests pass: `pytest tests/test_websocket.py -x`
- [ ] Thread-safe: concurrent hook calls with multiple clients don't corrupt state
