---
purpose: Decision log for a bead
updated: 2026-06-16
---

# Decisions: her-websocket-tps-streaming-90p

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | WebSocket over SSE | Bidirectional capability for future client commands (subscribe, filter) | High |
| 2 | ConnectionManager in api.py | Co-located with FastAPI app, follows existing factory pattern | High |
| 3 | Broadcast from _on_post_api_request | Single trigger point, after state is updated, before logging | High |
| 4 | JSON messages with type field | Extensible format for future message types (health, alerts) | High |
| 5 | Threading.Lock for ConnectionManager | Same pattern as _STATE_LOCK in __init__.py, proven thread-safe | High |
| 6 | asyncio.create_task for send | Non-blocking broadcast — slow client doesn't block others | Medium |
| 7 | No new dependencies | FastAPI/Starlette already have WebSocket support | High |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Server-Sent Events (SSE) | No bidirectional capability, harder to add subscribe/filter later | Would need rewrite for Phase 5 notifications |
| 2 | Separate WebSocket server (websockets lib) | Adds complexity, another process to manage | Unnecessary for single-instance plugin |
| 3 | Redis pub/sub | Single-process plugin, no need for message broker | Premature optimization |
| 4 | Polling via REST API | High latency, wasted bandwidth, defeats real-time purpose | Poor UX for dashboard |
| 5 | Socket.IO | Extra dependency, overkill for simple broadcast | Adds install complexity |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | Single-process deployment (Hermes plugin) | Validated — plugin runs in Hermes process | Would need Redis/multiprocess broadcast |
| 2 | Low client count (< 20 concurrent) | Validated — local dashboard use case | Would need connection pooling |
| 3 | FastAPI uvicorn supports WebSocket | Validated — Starlette native support | Would need separate WS server |
| 4 | TPS snapshot dict is JSON-serializable | Validated — all values are int/float/str/dict | Would need custom serializer |
| 5 | Hook calls are thread-safe via _STATE_LOCK | Validated — existing pattern in __init__.py | Would need asyncio lock |
