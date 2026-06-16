"""FastAPI REST API for exposing TPS metrics over HTTP.

Provides endpoints for session-level TPS stats, aggregated summaries,
and health checks. Reads from PersistentSessionStore (SQLite) and is
started as a background thread from the plugin's register() entry point.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(store: Any) -> FastAPI:
    """Build and return a configured FastAPI application.

    Args:
        store: A ``PersistentSessionStore`` instance used as the data source.
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
        limit: int = 100,
    ) -> EventListResponse:
        """Return per-call events for a session with optional time-range filter."""
        if store is None:
            raise HTTPException(status_code=503, detail="Database not available")
        event_list = store.load_events(session_id, since=since, until=until, limit=limit)
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

    return app
