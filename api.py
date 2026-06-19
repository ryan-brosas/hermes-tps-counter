"""FastAPI REST API for exposing TPS metrics over HTTP.

Provides endpoints for session-level TPS stats, aggregated summaries,
and health checks. Reads from PersistentSessionStore (SQLite) and is
started as a background thread from the plugin's register() entry point.
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from math import ceil
from typing import Any, Callable, Deque, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WebSocket ConnectionManager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Thread-safe manager for WebSocket connections.

    Tracks connected clients and broadcasts JSON messages to all.
    Uses asyncio.create_task for non-blocking sends so a slow client
    cannot block broadcasts to others.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        """Accept a WebSocket connection and add it to the client set."""
        await ws.accept()
        with self._lock:
            self._clients.add(ws)
        try:
            from prometheus_metrics import set_ws_active_connections
            set_ws_active_connections(self.count)
        except Exception:
            pass

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket from the client set (idempotent)."""
        with self._lock:
            self._clients.discard(ws)
        try:
            from prometheus_metrics import set_ws_active_connections
            set_ws_active_connections(self.count)
        except Exception:
            pass

    @property
    def count(self) -> int:
        """Number of currently connected clients."""
        with self._lock:
            return len(self._clients)

    async def broadcast(self, message: dict) -> None:
        """Send a JSON message to all connected clients.

        Dead clients (WebSocketDisconnect, ConnectionError) are silently
        removed. Individual sends are dispatched as tasks so one slow
        client cannot block others.
        """
        with self._lock:
            clients = list(self._clients)
        if not clients:
            return
        tasks = [asyncio.create_task(self._safe_send(ws, message)) for ws in clients]
        await asyncio.gather(*tasks)

    async def _safe_send(self, ws: WebSocket, message: dict) -> None:
        """Send JSON to one client; remove on failure."""
        try:
            await ws.send_json(message)
        except (WebSocketDisconnect, ConnectionError, RuntimeError):
            try:
                from prometheus_metrics import increment_ws_broadcast_failure, increment_ws_dead_client
                increment_ws_broadcast_failure()
                increment_ws_dead_client()
            except Exception:
                pass
            self.disconnect(ws)


async def broadcast_tps_update(manager: ConnectionManager, snapshot: dict) -> None:
    """Broadcast a TPS snapshot wrapped in a typed message envelope."""
    message = {
        "type": "tps_update",
        "data": snapshot,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast(message)


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    db: str


class SessionTPSResponse(BaseModel):
    session_id: str
    call_count: int
    total_output_tokens: int
    total_input_tokens: int
    total_duration: float
    peak_tps: float
    last_call_tps: float
    avg_tps: float
    updated_at: str


class SessionListResponse(BaseModel):
    sessions: List[SessionTPSResponse]


class BatchSessionTPSRequest(BaseModel):
    session_ids: List[str] = Field(..., min_length=1, max_length=1000)


class BatchSessionTPSResponse(BaseModel):
    sessions: List[SessionTPSResponse]
    missing_session_ids: List[str]


class SummaryResponse(BaseModel):
    total_sessions: int
    total_calls: int
    total_tokens: int
    average_tps: float


class EventResponse(BaseModel):
    id: int
    session_id: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    duration: float
    tps: float
    created_at: str


class EventListResponse(BaseModel):
    events: List[EventResponse]


class TrendResponse(BaseModel):
    session_id: str
    models: Dict[str, Dict[str, Any]]
    providers: Dict[str, Dict[str, Any]]


class ExportMetadata(BaseModel):
    generated_at: str
    filters: Dict[str, Any]
    session_count: int
    event_count: int
    format: str


class ExportResponse(BaseModel):
    metadata: ExportMetadata
    sessions: List[Dict[str, Any]]
    events: List[Dict[str, Any]]


_DEFAULT_EXPORT_LIMIT = 100
_HARD_EXPORT_LIMIT = 1000
_DEFAULT_EVENT_LIMIT = 100
_HARD_EVENT_LIMIT = 1000


def _validate_limit(limit: int, *, name: str, hard_limit: int) -> int:
    """Validate a positive bounded query limit."""
    if limit <= 0:
        raise HTTPException(status_code=422, detail=f"{name} must be a positive integer")
    if limit > hard_limit:
        raise HTTPException(
            status_code=422,
            detail=f"{name} {limit} exceeds maximum {hard_limit}",
        )
    return limit


def _normalize_timestamp_filter(value: str, *, name: str) -> str:
    """Normalize a client-provided ISO 8601 timestamp for SQLite text comparisons."""
    candidate = value.strip()
    if not candidate:
        raise HTTPException(status_code=422, detail=f"{name} must not be empty")
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{name} must be a valid ISO 8601 timestamp",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _normalize_time_range(
    since: Optional[str],
    until: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Normalize optional time-range filters and validate ordering."""
    normalized_since = (
        _normalize_timestamp_filter(since, name="since") if since is not None else None
    )
    normalized_until = (
        _normalize_timestamp_filter(until, name="until") if until is not None else None
    )
    if (
        normalized_since is not None
        and normalized_until is not None
        and normalized_since > normalized_until
    ):
        raise HTTPException(status_code=422, detail="since must be less than or equal to until")
    return normalized_since, normalized_until


def _build_session_summaries_from_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate returned events into per-session summaries for filtered exports."""
    summaries: Dict[str, Dict[str, Any]] = {}
    for event in events:
        session_id = event["session_id"]
        summary = summaries.setdefault(
            session_id,
            {
                "session_id": session_id,
                "call_count": 0,
                "total_output_tokens": 0,
                "total_input_tokens": 0,
                "total_duration": 0.0,
                "peak_tps": 0.0,
                "last_call_tps": 0.0,
                "avg_tps": 0.0,
                "updated_at": event["created_at"],
            },
        )
        summary["call_count"] += 1
        summary["total_output_tokens"] += event["output_tokens"]
        summary["total_input_tokens"] += event["input_tokens"]
        summary["total_duration"] += event["duration"]
        summary["peak_tps"] = max(summary["peak_tps"], event["tps"])
        if event["created_at"] >= summary["updated_at"]:
            summary["updated_at"] = event["created_at"]
            summary["last_call_tps"] = event["tps"]

    for summary in summaries.values():
        total_duration = summary["total_duration"]
        summary["avg_tps"] = (
            summary["total_output_tokens"] / total_duration if total_duration > 0 else 0.0
        )

    return sorted(summaries.values(), key=lambda row: row["updated_at"], reverse=True)


# ---------------------------------------------------------------------------
# Rate limiting middleware
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-process per-IP sliding-window rate limiter for HTTP endpoints."""

    window_seconds = 60.0
    exempt_paths = {"/api/v1/health"}

    def __init__(
        self,
        app: Any,
        *,
        requests_per_minute: int,
        burst_size: int,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(app)
        self.requests_per_minute = max(1, int(requests_per_minute))
        self.burst_size = max(1, int(burst_size))
        self.limit = self.requests_per_minute + self.burst_size
        self._time_fn = time_fn or time.time
        self._requests: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Apply the rate limit before protected handlers run."""
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        client_host = request.client.host if request.client is not None else None
        client_key = client_host or "unknown"
        now = float(self._time_fn())

        retry_after: int | None = None
        with self._lock:
            self._prune(now)
            timestamps = self._requests.setdefault(client_key, deque())
            self._prune_deque(timestamps, now)

            if len(timestamps) >= self.limit:
                oldest = timestamps[0]
                retry_after = max(1, ceil((oldest + self.window_seconds) - now))
            else:
                timestamps.append(now)

        if retry_after is not None:
            logger.debug(
                "Rate limit exceeded for client=%s retry_after=%s",
                client_key,
                retry_after,
            )
            try:
                from prometheus_metrics import increment_rate_limited
                increment_rate_limited()
            except Exception:
                pass
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "retry_after": retry_after},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    def _prune(self, now: float) -> None:
        """Remove stale timestamps and empty client entries."""
        empty_clients = []
        for client_key, timestamps in self._requests.items():
            self._prune_deque(timestamps, now)
            if not timestamps:
                empty_clients.append(client_key)
        for client_key in empty_clients:
            self._requests.pop(client_key, None)

    def _prune_deque(self, timestamps: Deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(
    store: Any,
    get_diagnostics: Any = None,
    *,
    config: Any = None,
    rate_limit_time_fn: Callable[[], float] | None = None,
) -> FastAPI:
    """Build and return a configured FastAPI application.

    Args:
        store: A ``PersistentSessionStore`` instance used as the data source.
        get_diagnostics: Optional callable that returns in-memory state snapshot
            for the diagnostics endpoint. Signature: ``() -> dict`` returning
            ``{sessions: list, models: dict, providers: dict, max_sessions: int}``.
        config: Optional TPSConfig override. Defaults to ``get_config()``.
        rate_limit_time_fn: Optional monotonic-ish time source for deterministic tests.
    """
    app = FastAPI(
        title="TPS Counter API",
        description="REST API for LLM tokens-per-second monitoring",
        version="1.0.0",
    )

    # CORS — wide-open for local dashboard development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if config is None:
        from config import get_config
        config = get_config()
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=config.requests_per_minute,
        burst_size=config.burst_size,
        time_fn=rate_limit_time_fn,
    )

    # ConnectionManager instance for WebSocket broadcasting
    manager = ConnectionManager()
    app.state.ws_manager = manager

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Health check — verify the API and DB are reachable."""
        db_status = "connected"
        if store is None:
            db_status = "disconnected"
        else:
            try:
                # Lightweight probe: load_all returns {} if empty but doesn't fail
                store.load_all()
            except Exception:
                db_status = "disconnected"
        return HealthResponse(status="ok", db=db_status)

    @app.post("/api/v1/sessions/batch/tps", response_model=BatchSessionTPSResponse)
    def batch_session_tps(request: BatchSessionTPSRequest) -> BatchSessionTPSResponse:
        """Return TPS stats for a bounded batch of session IDs.

        Missing sessions are reported in ``missing_session_ids`` instead of
        failing the entire batch, and duplicate input IDs are normalized while
        preserving first-seen order.
        """
        if store is None:
            raise HTTPException(status_code=503, detail="Database not available")

        unique_ids = list(dict.fromkeys(request.session_ids))
        sessions: List[SessionTPSResponse] = []
        missing_session_ids: List[str] = []
        for session_id in unique_ids:
            data = store.load(session_id)
            if data is None:
                missing_session_ids.append(session_id)
            else:
                sessions.append(SessionTPSResponse(**data))

        return BatchSessionTPSResponse(
            sessions=sessions,
            missing_session_ids=missing_session_ids,
        )

    @app.get("/api/v1/sessions/{session_id}/tps", response_model=SessionTPSResponse)
    def session_tps(session_id: str) -> SessionTPSResponse:
        """Return TPS stats for a single session."""
        if store is None:
            raise HTTPException(status_code=503, detail="Database not available")
        data = store.load(session_id)
        if data is None:
            raise HTTPException(
                status_code=404, detail=f"Session '{session_id}' not found"
            )
        return SessionTPSResponse(**data)

    @app.get("/api/v1/sessions", response_model=SessionListResponse)
    def all_sessions() -> SessionListResponse:
        """Return all sessions with their TPS stats."""
        if store is None:
            raise HTTPException(status_code=503, detail="Database not available")
        sessions_map = store.load_all()
        return SessionListResponse(
            sessions=[SessionTPSResponse(**v) for v in sessions_map.values()]
        )

    @app.get("/api/v1/summary", response_model=SummaryResponse)
    def summary() -> SummaryResponse:
        """Return aggregated TPS summary across all sessions."""
        if store is None:
            raise HTTPException(status_code=503, detail="Database not available")
        sessions_map = store.load_all()
        total_sessions = len(sessions_map)
        total_calls = 0
        total_tokens = 0
        total_output = 0
        total_duration = 0.0
        for s in sessions_map.values():
            total_calls += s["call_count"]
            total_tokens += s["total_output_tokens"] + s["total_input_tokens"]
            total_output += s["total_output_tokens"]
            total_duration += s["total_duration"]
        avg_tps = (total_output / total_duration) if total_duration > 0 else 0.0
        return SummaryResponse(
            total_sessions=total_sessions,
            total_calls=total_calls,
            total_tokens=total_tokens,
            average_tps=round(avg_tps, 2),
        )

    @app.get("/api/v1/events/{session_id}", response_model=EventListResponse)
    def events(
        session_id: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = _DEFAULT_EVENT_LIMIT,
    ) -> EventListResponse:
        """Return per-call events for a session with optional time-range filter."""
        if store is None:
            raise HTTPException(status_code=503, detail="Database not available")
        normalized_since, normalized_until = _normalize_time_range(since, until)
        validated_limit = _validate_limit(limit, name="limit", hard_limit=_HARD_EVENT_LIMIT)
        event_list = store.load_events(
            session_id,
            since=normalized_since,
            until=normalized_until,
            limit=validated_limit,
        )
        if not event_list:
            raise HTTPException(
                status_code=404, detail=f"No events found for session '{session_id}'"
            )
        return EventListResponse(events=[EventResponse(**e) for e in event_list])

    @app.get("/api/v1/trends/{session_id}", response_model=TrendResponse)
    def trends(
        session_id: str,
        since: Optional[str] = None,
    ) -> TrendResponse:
        """Return per-model and per-provider aggregated trends for a session."""
        if store is None:
            raise HTTPException(status_code=503, detail="Database not available")
        models = store.aggregate_by_model(session_id, since=since)
        providers = store.aggregate_by_provider(session_id, since=since)
        if not models and not providers:
            raise HTTPException(
                status_code=404, detail=f"No events found for session '{session_id}'"
            )
        return TrendResponse(session_id=session_id, models=models, providers=providers)

    @app.get("/api/v1/export/history", response_model=ExportResponse)
    def export_history(
        session_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = _DEFAULT_EXPORT_LIMIT,
        format: str = "json",
    ) -> Any:
        """Bounded historical export for offline analysis and dashboard import.

        Returns session TPS summaries and per-call events within explicit bounds.
        Every request is bounded by limit (default 100, max 1000).
        """
        if store is None:
            raise HTTPException(status_code=503, detail="Database not available")

        normalized_since, normalized_until = _normalize_time_range(since, until)
        validated_limit = _validate_limit(limit, name="limit", hard_limit=_HARD_EXPORT_LIMIT)

        # Validate format
        if format not in ("json", "csv"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format '{format}'. Use 'json' or 'csv'.",
            )

        effective_limit = validated_limit
        filters: Dict[str, Any] = {"limit": effective_limit}
        if session_id:
            filters["session_id"] = session_id
        if normalized_since:
            filters["since"] = normalized_since
        if normalized_until:
            filters["until"] = normalized_until

        events = store.export_events(
            session_id=session_id,
            since=normalized_since,
            until=normalized_until,
            limit=effective_limit,
        )
        if session_id or normalized_since or normalized_until:
            sessions = _build_session_summaries_from_events(events)
        else:
            sessions = store.export_sessions(limit=effective_limit)

        metadata = ExportMetadata(
            generated_at=datetime.now(timezone.utc).isoformat(),
            filters=filters,
            session_count=len(sessions),
            event_count=len(events),
            format=format,
        )

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            # Write events as CSV (flatten metadata into header comments)
            if events:
                fieldnames = list(events[0].keys())
                writer.writerow(fieldnames)
                for row in events:
                    writer.writerow([row.get(f, "") for f in fieldnames])
            else:
                writer.writerow(["id", "session_id", "model", "provider",
                                 "input_tokens", "output_tokens", "duration",
                                 "tps", "created_at"])
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=export_history.csv"},
            )

        return ExportResponse(
            metadata=metadata,
            sessions=sessions,
            events=events,
        )

    @app.get("/metrics")
    def metrics():
        """Prometheus metrics endpoint — returns text exposition format."""
        from prometheus_metrics import generate_metrics, metrics_available as _ma
        if not _ma():
            raise HTTPException(503, "prometheus_client not installed")
        return Response(
            content=generate_metrics(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    # ------------------------------------------------------------------
    # WebSocket endpoint
    # ------------------------------------------------------------------

    @app.websocket("/ws/tps")
    async def websocket_tps(websocket: WebSocket) -> None:
        """WebSocket endpoint that streams real-time TPS snapshots."""
        await manager.connect(websocket)
        try:
            # Keep connection alive; receive_text detects disconnect
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            manager.disconnect(websocket)

    # ------------------------------------------------------------------
    # Diagnostics helper functions
    # ------------------------------------------------------------------

    def _collect_memory_status() -> Dict[str, Any]:
        """Collect in-memory session state via the diagnostics callback."""
        if get_diagnostics is None:
            return {"status": "unavailable", "sessions": 0, "max_sessions": 0,
                    "models": 0, "providers": 0}
        try:
            snapshot = get_diagnostics()
            return {
                "status": "ok",
                "sessions": len(snapshot.get("sessions", [])),
                "max_sessions": snapshot.get("max_sessions", 0),
                "models": len(snapshot.get("models", {})),
                "providers": len(snapshot.get("providers", {})),
            }
        except Exception:
            return {"status": "degraded", "sessions": 0, "max_sessions": 0,
                    "models": 0, "providers": 0}

    def _collect_sqlite_status() -> Dict[str, Any]:
        """Collect SQLite store connectivity and counts."""
        if store is None:
            return {"status": "unavailable", "connected": False,
                    "session_count": 0, "event_count": 0, "retention_days": 0}
        try:
            session_count = store.count()
            # Event count via a lightweight query
            event_count = 0
            try:
                with store._lock:
                    cur = store._conn.execute("SELECT COUNT(*) FROM call_events")
                    row = cur.fetchone()
                    event_count = row[0] if row else 0
            except Exception:
                pass
            return {
                "status": "ok",
                "connected": True,
                "session_count": session_count,
                "event_count": event_count,
                "retention_days": store._retention_days,
            }
        except Exception:
            return {"status": "degraded", "connected": False,
                    "session_count": 0, "event_count": 0, "retention_days": 0}

    def _collect_prometheus_status() -> Dict[str, Any]:
        """Collect Prometheus metrics registry status."""
        try:
            from prometheus_metrics import metrics_available as _ma, REGISTRY as _reg
            enabled = _ma()
            collector_count = 0
            if enabled and _reg is not None:
                try:
                    collector_count = len(list(_reg.collect()))
                except Exception:
                    pass
            return {
                "status": "ok" if enabled else "unavailable",
                "enabled": enabled,
                "available": enabled,
                "registered_collectors": collector_count,
            }
        except ImportError:
            return {"status": "unavailable", "enabled": False,
                    "available": False, "registered_collectors": 0}
        except Exception:
            return {"status": "degraded", "enabled": False,
                    "available": False, "registered_collectors": 0}

    def _collect_websocket_status() -> Dict[str, Any]:
        """Collect WebSocket connection manager status."""
        try:
            ws_manager = getattr(app.state, "ws_manager", None)
            if ws_manager is None:
                return {"status": "degraded", "enabled": False,
                        "active_connections": 0}
            return {
                "status": "ok",
                "enabled": True,
                "active_connections": ws_manager.count,
            }
        except Exception:
            return {"status": "degraded", "enabled": False,
                    "active_connections": 0}

    def _collect_health_counters() -> Dict[str, Any]:
        """Collect operational health counter values from Prometheus."""
        try:
            from prometheus_metrics import (
                metrics_available as _ma,
                _usage_extraction_failures as _uef,
                _db_write_errors as _dwe,
                _db_read_errors as _dre,
                _ws_broadcast_failures as _wbf,
                _ws_dead_clients as _wdc,
            )
            if not _ma():
                return {"status": "unavailable", "usage_extraction_failures": 0,
                        "db_write_errors": 0, "db_read_errors": 0,
                        "ws_broadcast_failures": 0, "ws_dead_clients": 0}

            def _get_counter_value(counter: Any) -> int:
                """Safely get the current value of a Prometheus counter."""
                if counter is None:
                    return 0
                try:
                    # Method 1: _value attribute (prometheus_client >= 0.14)
                    val = getattr(counter, "_value", None)
                    if val is not None and hasattr(val, "get"):
                        return int(val.get())
                except Exception:
                    pass
                try:
                    # Method 2: collect and extract from samples
                    for family in counter.collect():
                        for sample in family.samples:
                            return int(sample.value)
                except Exception:
                    pass
                return 0

            return {
                "status": "ok",
                "usage_extraction_failures": _get_counter_value(_uef),
                "db_write_errors": _get_counter_value(_dwe),
                "db_read_errors": _get_counter_value(_dre),
                "ws_broadcast_failures": _get_counter_value(_wbf),
                "ws_dead_clients": _get_counter_value(_wdc),
            }
        except ImportError:
            return {"status": "unavailable", "usage_extraction_failures": 0,
                    "db_write_errors": 0, "db_read_errors": 0,
                    "ws_broadcast_failures": 0, "ws_dead_clients": 0}
        except Exception:
            return {"status": "degraded", "usage_extraction_failures": 0,
                    "db_write_errors": 0, "db_read_errors": 0,
                    "ws_broadcast_failures": 0, "ws_dead_clients": 0}

    # ------------------------------------------------------------------
    # Health diagnostics endpoint
    # ------------------------------------------------------------------

    @app.get("/api/v1/health/diagnostics")
    def health_diagnostics() -> Dict[str, Any]:
        """Comprehensive health diagnostics for all plugin components.

        Returns JSON with component-level status for memory, SQLite,
        Prometheus, WebSocket, and operational health counters.
        """
        components = {
            "memory": _collect_memory_status(),
            "sqlite": _collect_sqlite_status(),
            "prometheus": _collect_prometheus_status(),
            "websocket": _collect_websocket_status(),
            "health_counters": _collect_health_counters(),
        }

        # Determine overall status
        statuses = [c["status"] for c in components.values()]
        if all(s == "ok" for s in statuses):
            overall = "ok"
        elif any(s == "unavailable" for s in statuses):
            # Check if majority are unavailable
            unavail_count = sum(1 for s in statuses if s == "unavailable")
            overall = "unavailable" if unavail_count > len(statuses) / 2 else "degraded"
        else:
            overall = "degraded"

        return {
            "status": overall,
            "components": components,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Built-in dashboard (serves at root path)
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        """Serve the built-in TPS monitoring dashboard."""
        from dashboard import DASHBOARD_HTML
        return HTMLResponse(content=DASHBOARD_HTML)

    return app
