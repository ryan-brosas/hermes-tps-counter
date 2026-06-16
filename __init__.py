"""tps-counter — Hermes plugin that tracks tokens-per-second throughput.

Hooks into post_api_request to capture output_tokens and api_duration
after each LLM call. Maintains per-session stats and prints a compact
TPS summary after each turn.

No configuration required — works out of the box.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from config import get_config

logger = logging.getLogger(__name__)

# Ordered fallback key paths for usage extraction
_OUTPUT_TOKEN_KEYS = ("output_tokens", "completion_tokens", "completionTokens")
_INPUT_TOKEN_KEYS = ("input_tokens", "prompt_tokens", "promptTokens")


def _extract_usage(usage_dict: Any) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from a usage dict.

    Tries multiple key paths to support different LLM providers:
    - Anthropic: usage.output_tokens, usage.input_tokens
    - OpenAI: usage.completion_tokens, usage.prompt_tokens
    - Google/other: usage.completionTokens, usage.promptTokens

    Returns (0, 0) for missing or invalid input.
    """
    if not isinstance(usage_dict, dict):
        return (0, 0)

    # Output tokens — try primary, then fallbacks
    output_tokens = 0
    for key in _OUTPUT_TOKEN_KEYS:
        val = usage_dict.get(key)
        if val is not None:
            try:
                output_tokens = int(val)
                if key != _OUTPUT_TOKEN_KEYS[0]:
                    logger.debug(
                        "tps-counter: used fallback key %r for output_tokens", key
                    )
                break
            except (TypeError, ValueError):
                continue

    # Input tokens — try primary, then fallbacks
    input_tokens = 0
    for key in _INPUT_TOKEN_KEYS:
        val = usage_dict.get(key)
        if val is not None:
            try:
                input_tokens = int(val)
                if key != _INPUT_TOKEN_KEYS[0]:
                    logger.debug(
                        "tps-counter: used fallback key %r for input_tokens", key
                    )
                break
            except (TypeError, ValueError):
                continue

    return (input_tokens, max(output_tokens, 0))


# Per-session TPS state, keyed by session_id
_STATE_LOCK = threading.Lock()
_SESSIONS: Dict[str, "_SessionTPS"] = {}
_MODELS: Dict[str, Dict[str, "_ModelTPS"]] = {}  # session_id → model_name → _ModelTPS
_PROVIDERS: Dict[str, Dict[str, "_ProviderTPS"]] = {}  # session_id → provider → _ProviderTPS

# Session lifecycle limits (from config module, defaults to 50)
MAX_SESSIONS = 50  # backward compat constant; actual eviction uses get_config().max_sessions

# Persistent store (set during register, may remain None on failure)
_STORE: Optional[Any] = None  # PersistentSessionStore | None

# Prometheus metrics flag (set in register(), defaults to disabled)
_prometheus_enabled: bool = False

# WebSocket streaming state (set when API server starts)
_WS_MANAGER: Optional[Any] = None  # ConnectionManager | None
_EVENT_LOOP: Optional[Any] = None  # asyncio.AbstractEventLoop | None


class _SessionTPS:
    """Tracks TPS metrics for a single session."""

    __slots__ = (
        "call_count",
        "total_output_tokens",
        "total_input_tokens",
        "total_duration",
        "last_call_tps",
        "last_call_output_tokens",
        "last_call_input_tokens",
        "last_call_duration",
        "peak_tps",
        "turn_start_tokens",
        "turn_start_input_tokens",
        "turn_start_time",
        "created_at",
    )

    def __init__(self) -> None:
        self.call_count: int = 0
        self.total_output_tokens: int = 0
        self.total_input_tokens: int = 0
        self.total_duration: float = 0.0
        self.last_call_tps: float = 0.0
        self.last_call_output_tokens: int = 0
        self.last_call_input_tokens: int = 0
        self.last_call_duration: float = 0.0
        self.peak_tps: float = 0.0
        self.turn_start_tokens: int = 0
        self.turn_start_input_tokens: int = 0
        self.turn_start_time: float = time.time()
        self.created_at: float = time.time()

    def record(self, output_tokens: int, duration: float, input_tokens: int = 0) -> None:
        self.call_count += 1
        self.total_output_tokens += output_tokens
        self.total_input_tokens += input_tokens
        self.total_duration += duration
        self.last_call_output_tokens = output_tokens
        self.last_call_input_tokens = input_tokens
        self.last_call_duration = duration
        if duration > 0:
            self.last_call_tps = output_tokens / duration
            if self.last_call_tps > self.peak_tps:
                self.peak_tps = self.last_call_tps

    @property
    def total_tokens(self) -> int:
        """Total tokens processed (input + output)."""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def avg_tps(self) -> float:
        if self.total_duration > 0:
            return self.total_output_tokens / self.total_duration
        return 0.0

    @property
    def turn_tps(self) -> float:
        """TPS for the current turn (since last reset_turn)."""
        elapsed = time.time() - self.turn_start_time
        tokens = self.total_output_tokens - self.turn_start_tokens
        if elapsed > 0 and tokens > 0:
            return tokens / elapsed
        return 0.0

    def reset_turn(self) -> None:
        self.turn_start_tokens = self.total_output_tokens
        self.turn_start_input_tokens = self.total_input_tokens
        self.turn_start_time = time.time()

    def summary_line(self) -> str:
        """Compact one-line summary for post-turn display."""
        parts = []
        if self.last_call_tps > 0:
            parts.append(f"⚡ {self.last_call_tps:.1f} tok/s")
        if self.call_count > 1 and self.avg_tps > 0:
            parts.append(f"avg {self.avg_tps:.1f}")
        if self.peak_tps > 0:
            parts.append(f"peak {self.peak_tps:.1f}")
        if self.total_tokens > 0:
            parts.append(f"total {self._fmt_tokens(self.total_tokens)}")
        if self.total_output_tokens > 0:
            parts.append(f"out {self._fmt_tokens(self.total_output_tokens)}")
        if self.total_input_tokens > 0:
            parts.append(f"in {self._fmt_tokens(self.total_input_tokens)}")
        return " │ ".join(parts) if parts else ""

    @staticmethod
    def _fmt_tokens(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)


def _extract_provider(model: str) -> str:
    """Extract provider name from a LiteLLM-style model string.

    Examples:
        'openai/gpt-4o' → 'openai'
        'anthropic/claude-sonnet-4' → 'anthropic'
        'gpt-4' → 'default'
        '' → 'default'
    """
    if not model or "/" not in model:
        return "default"
    return model.split("/", 1)[0]


class _ProviderTPS:
    """Tracks aggregate TPS metrics for a provider within a session."""

    __slots__ = (
        "call_count",
        "total_output_tokens",
        "total_duration",
        "peak_tps",
    )

    def __init__(self) -> None:
        self.call_count: int = 0
        self.total_output_tokens: int = 0
        self.total_duration: float = 0.0
        self.peak_tps: float = 0.0

    def record(self, output_tokens: int, duration: float) -> None:
        self.call_count += 1
        self.total_output_tokens += output_tokens
        self.total_duration += duration
        if duration > 0:
            tps = output_tokens / duration
            if tps > self.peak_tps:
                self.peak_tps = tps

    @property
    def avg_tps(self) -> float:
        if self.total_duration > 0:
            return self.total_output_tokens / self.total_duration
        return 0.0


class _ModelTPS:
    """Tracks TPS metrics for a single model within a session."""

    __slots__ = (
        "call_count",
        "total_output_tokens",
        "total_duration",
        "peak_tps",
    )

    def __init__(self) -> None:
        self.call_count: int = 0
        self.total_output_tokens: int = 0
        self.total_duration: float = 0.0
        self.peak_tps: float = 0.0

    def record(self, output_tokens: int, duration: float) -> None:
        self.call_count += 1
        self.total_output_tokens += output_tokens
        self.total_duration += duration
        if duration > 0:
            tps = output_tokens / duration
            if tps > self.peak_tps:
                self.peak_tps = tps

    @property
    def avg_tps(self) -> float:
        if self.total_duration > 0:
            return self.total_output_tokens / self.total_duration
        return 0.0


def _hydrate_from_db(session_id: str) -> Optional[_SessionTPS]:
    """Try to load a session from the persistent store."""
    if _STORE is None:
        return None
    try:
        data = _STORE.load(session_id)
        if data is None:
            return None
        s = _SessionTPS()
        s.call_count = data["call_count"]
        s.total_output_tokens = data["total_output_tokens"]
        s.total_input_tokens = data.get("total_input_tokens", 0)
        s.total_duration = data["total_duration"]
        s.peak_tps = data["peak_tps"]
        s.last_call_tps = data["last_call_tps"]
        s.last_call_output_tokens = 0
        s.last_call_input_tokens = 0
        s.last_call_duration = 0.0
        return s
    except Exception as exc:
        logger.warning("tps-counter: DB read failed, disabling store: %s", exc)
        try:
            from prometheus_metrics import increment_db_read_error
            increment_db_read_error()
        except Exception:
            pass
        return None


def _persist_state(session_id: str, state: _SessionTPS) -> None:
    """Write-through to persistent store if available."""
    if _STORE is None:
        return
    try:
        _STORE.save(session_id, state)
    except Exception as exc:
        logger.warning("tps-counter: DB write failed, disabling store: %s", exc)
        try:
            from prometheus_metrics import increment_db_write_error
            increment_db_write_error()
        except Exception:
            pass


def _get_session(session_id: str) -> _SessionTPS:
    with _STATE_LOCK:
        if session_id not in _SESSIONS:
            # Try loading from DB first
            loaded = _hydrate_from_db(session_id)
            _SESSIONS[session_id] = loaded if loaded is not None else _SessionTPS()
        return _SESSIONS[session_id]


def _get_model(session_id: str, model: str) -> _ModelTPS:
    """Get or create a _ModelTPS for a session+model pair. Caller must hold _STATE_LOCK."""
    if session_id not in _MODELS:
        _MODELS[session_id] = {}
    if model not in _MODELS[session_id]:
        _MODELS[session_id][model] = _ModelTPS()
    return _MODELS[session_id][model]


def _get_provider(session_id: str, provider: str) -> _ProviderTPS:
    """Get or create a _ProviderTPS for a session+provider pair. Caller must hold _STATE_LOCK."""
    if session_id not in _PROVIDERS:
        _PROVIDERS[session_id] = {}
    if provider not in _PROVIDERS[session_id]:
        _PROVIDERS[session_id][provider] = _ProviderTPS()
    return _PROVIDERS[session_id][provider]


def _on_post_api_request(**kwargs: Any) -> None:
    """Hook callback: record TPS after each LLM API call."""
    session_id = kwargs.get("session_id", "")
    if not session_id:
        return

    usage = kwargs.get("usage", {})
    input_tokens, output_tokens = _extract_usage(usage)
    duration = kwargs.get("api_duration", 0.0) or 0.0

    # Track extraction failures: non-empty usage dict but zero tokens extracted
    if usage and isinstance(usage, dict) and input_tokens == 0 and output_tokens == 0:
        try:
            from prometheus_metrics import increment_usage_extraction_failure
            increment_usage_extraction_failure()
        except Exception:
            pass

    if output_tokens <= 0 or duration <= 0:
        return

    state = _get_session(session_id)
    model = kwargs.get("model", "") or ""
    with _STATE_LOCK:
        state.record(output_tokens, duration, input_tokens)
        # Write-through to SQLite
        _persist_state(session_id, state)
        # Record per-call event
        if _STORE is not None:
            tps_val = output_tokens / duration if duration > 0 else 0.0
            provider_val = _extract_provider(model)
            try:
                _STORE.record_event(session_id, model, provider_val, input_tokens, output_tokens, duration, tps_val)
            except Exception as exc:
                logger.debug("tps-counter: event recording failed: %s", exc)
        # Per-model tracking
        if model:
            model_state = _get_model(session_id, model)
            model_state.record(output_tokens, duration)
        # Per-provider tracking
        provider = _extract_provider(model)
        provider_state = _get_provider(session_id, provider)
        provider_state.record(output_tokens, duration)
        # Update Prometheus metrics (inside lock for consistent snapshot)
        if _prometheus_enabled:
            try:
                from prometheus_metrics import update_metrics as _update_prom
                session_models = _MODELS.get(session_id, {})
                session_providers = _PROVIDERS.get(session_id, {})
                _update_prom(session_id, state, session_models, session_providers)
            except Exception:
                pass

    # LRU eviction safety net
    _evict_if_needed()

    # Expose TPS snapshot for status bar integration
    try:
        from hermes_cli import _ACTIVE_CLI_INSTANCE
        cli = _ACTIVE_CLI_INSTANCE
        if cli is not None:
            agent = getattr(cli, "agent", None)
            if agent is not None:
                snapshot: Dict[str, Any] = {
                    "last_tps": state.last_call_tps,
                    "avg_tps": state.avg_tps,
                    "peak_tps": state.peak_tps,
                    "output_tokens": state.total_output_tokens,
                    "input_tokens": state.total_input_tokens,
                    "total_tokens": state.total_tokens,
                }
                # Include per-model breakdown if available
                with _STATE_LOCK:
                    session_models = _MODELS.get(session_id, {})
                    if session_models:
                        snapshot["models"] = {
                            m: {
                                "avg_tps": ms.avg_tps,
                                "peak_tps": ms.peak_tps,
                                "calls": ms.call_count,
                                "total_output_tokens": ms.total_output_tokens,
                            }
                            for m, ms in session_models.items()
                        }
                    # Include per-provider breakdown if available
                    session_providers = _PROVIDERS.get(session_id, {})
                    if session_providers:
                        snapshot["providers"] = {
                            p: {
                                "avg_tps": ps.avg_tps,
                                "peak_tps": ps.peak_tps,
                                "calls": ps.call_count,
                                "total_output_tokens": ps.total_output_tokens,
                                "total_duration": ps.total_duration,
                            }
                            for p, ps in session_providers.items()
                        }
                agent._tps_snapshot = snapshot
    except Exception as exc:
        logger.debug("tps-counter: failed to inject status bar data: %s", exc)

    # Broadcast TPS snapshot to WebSocket clients (fire-and-forget)
    try:
        if _WS_MANAGER is not None and _EVENT_LOOP is not None:
            from api import broadcast_tps_update
            # Build a snapshot dict from the current state
            ws_snapshot = {
                "session_id": session_id,
                "last_tps": state.last_call_tps,
                "avg_tps": state.avg_tps,
                "peak_tps": state.peak_tps,
                "output_tokens": state.total_output_tokens,
                "input_tokens": state.total_input_tokens,
                "total_tokens": state.total_tokens,
                "call_count": state.call_count,
            }
            asyncio.run_coroutine_threadsafe(
                broadcast_tps_update(_WS_MANAGER, ws_snapshot), _EVENT_LOOP
            )
    except Exception as exc:
        logger.debug("tps-counter: WebSocket broadcast failed: %s", exc)

    # Log at debug level so it doesn't spam
    logger.debug(
        "TPS: %.1f tok/s (%d tokens in %.2fs) [session %s]",
        state.last_call_tps,
        output_tokens,
        duration,
        session_id[:8],
    )


_API_SERVER: Optional[Any] = None  # uvicorn.Server reference for shutdown


def _start_api_server(store: Any, host: str, port: int) -> None:
    """Start the FastAPI TPS API in a daemon thread."""
    global _API_SERVER, _WS_MANAGER, _EVENT_LOOP
    try:
        import asyncio
        import uvicorn
        from api import create_app

        app = create_app(store)
        # Capture the ConnectionManager for hook-triggered broadcasts
        _WS_MANAGER = getattr(app.state, "ws_manager", None)

        config = uvicorn.Config(
            app, host=host, port=port, log_level="warning", access_log=False,
        )
        server = uvicorn.Server(config)
        _API_SERVER = server

        def _run_server() -> None:
            """Thread target — captures the event loop for cross-thread scheduling."""
            global _EVENT_LOOP
            _EVENT_LOOP = asyncio.new_event_loop()
            asyncio.set_event_loop(_EVENT_LOOP)
            # Run uvicorn on this loop
            _EVENT_LOOP.run_until_complete(server.serve())

        thread = threading.Thread(target=_run_server, daemon=True, name="tps-api")
        thread.start()
        logger.info("tps-counter: API server started on %s:%d", host, port)
    except Exception as exc:
        logger.warning("tps-counter: failed to start API server: %s", exc)


def _stop_api_server() -> None:
    """Signal the API server to shut down."""
    global _API_SERVER
    if _API_SERVER is not None:
        try:
            _API_SERVER.should_exit = True
            logger.info("tps-counter: API server shutting down")
        except Exception:
            pass
        _API_SERVER = None


def unregister(ctx: Any) -> None:
    """Hermes shutdown hook — release all plugin resources cleanly."""
    global _STORE, _prometheus_enabled, _WS_MANAGER, _EVENT_LOOP

    # Stop the API server if running
    try:
        _stop_api_server()
    except Exception:
        pass

    # Close the persistent store
    if _STORE is not None:
        try:
            _STORE.close()
            logger.info("tps-counter: persistent store closed")
        except Exception:
            pass
        _STORE = None

    # Clear all in-memory state
    with _STATE_LOCK:
        _SESSIONS.clear()
        _MODELS.clear()
        _PROVIDERS.clear()

    # Reset flags and async state
    _prometheus_enabled = False
    _WS_MANAGER = None
    _EVENT_LOOP = None


def _on_session_end(**kwargs: Any) -> None:
    """Hook callback: clean up session state when a session ends."""
    session_id = kwargs.get("session_id", "")
    if not session_id:
        logger.debug("tps-counter: on_session_end called without session_id")
        return
    _cleanup_session(session_id)


def register(ctx: Any) -> None:
    """Plugin entry point — called by Hermes plugin loader."""
    global _STORE, _prometheus_enabled

    # Load merged config (defaults < TOML < env vars < ctx overrides)
    cfg = get_config(ctx)

    db_path = cfg.db_path

    # Initialize persistent store
    try:
        from store import PersistentSessionStore

        _STORE = PersistentSessionStore(db_path, retention_days=cfg.retention_days)
        logger.info("tps-counter: persistent store at %s", db_path)
    except Exception as exc:
        logger.warning("tps-counter: persistence unavailable, using in-memory only: %s", exc)
        _STORE = None

    ctx.register_hook("post_api_request", _on_post_api_request)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_hook("on_shutdown", unregister)
    logger.info("tps-counter plugin registered")

    # Optionally start the REST API server
    if cfg.api_enabled:
        _start_api_server(_STORE, cfg.api_host, cfg.api_port)

    # Optionally enable Prometheus metrics
    if cfg.prometheus_enabled:
        from prometheus_metrics import metrics_available
        if metrics_available():
            _prometheus_enabled = True
            logger.info("tps-counter: Prometheus metrics enabled at /metrics")
        else:
            logger.warning(
                "tps-counter: prometheus.enabled=true but prometheus_client not installed"
            )


# Expose state for /usage integration or external queries
def get_tps_stats(session_id: str) -> Dict[str, Any]:
    """Return current TPS stats for a session (callable from /usage)."""
    with _STATE_LOCK:
        state = _SESSIONS.get(session_id)
    if state is None:
        return {"calls": 0, "avg_tps": 0, "last_tps": 0, "peak_tps": 0, "total_output_tokens": 0, "total_input_tokens": 0, "total_tokens": 0}
    return {
        "calls": state.call_count,
        "avg_tps": round(state.avg_tps, 1),
        "last_tps": round(state.last_call_tps, 1),
        "peak_tps": round(state.peak_tps, 1),
        "total_output_tokens": state.total_output_tokens,
        "total_input_tokens": state.total_input_tokens,
        "total_tokens": state.total_tokens,
        "total_duration": round(state.total_duration, 2),
        "session_duration": round(time.time() - state.created_at, 2),
    }


def get_model_stats(session_id: str) -> Dict[str, Dict[str, Any]]:
    """Return per-model TPS stats for a session.

    Returns:
        Dict mapping model_name → {avg_tps, peak_tps, calls, total_output_tokens, total_duration}
    """
    with _STATE_LOCK:
        session_models = _MODELS.get(session_id, {})
        return {
            model: {
                "avg_tps": round(ms.avg_tps, 1),
                "peak_tps": round(ms.peak_tps, 1),
                "calls": ms.call_count,
                "total_output_tokens": ms.total_output_tokens,
                "total_duration": round(ms.total_duration, 2),
            }
            for model, ms in session_models.items()
        }


def get_provider_stats(session_id: str) -> Dict[str, Dict[str, Any]]:
    """Return per-provider TPS stats for a session.

    Returns:
        Dict mapping provider_name → {avg_tps, peak_tps, calls, total_output_tokens, total_duration}
    """
    with _STATE_LOCK:
        session_providers = _PROVIDERS.get(session_id, {})
        return {
            provider: {
                "avg_tps": round(ps.avg_tps, 1),
                "peak_tps": round(ps.peak_tps, 1),
                "calls": ps.call_count,
                "total_output_tokens": ps.total_output_tokens,
                "total_duration": round(ps.total_duration, 2),
            }
            for provider, ps in session_providers.items()
        }


def _cleanup_session(session_id: str) -> None:
    """Remove all in-memory state for a session (session + model + provider data)."""
    with _STATE_LOCK:
        _SESSIONS.pop(session_id, None)
        _MODELS.pop(session_id, None)
        _PROVIDERS.pop(session_id, None)
    # Also remove from persistent store
    if _STORE is not None:
        try:
            _STORE.delete(session_id)
        except Exception as exc:
            logger.debug("tps-counter: DB cleanup failed for %s: %s", session_id, exc)
    logger.debug("tps-counter: cleaned up session %s", session_id[:8])


def _evict_if_needed() -> None:
    """Evict the session with the oldest turn_start_time if over max_sessions."""
    max_sessions = get_config().max_sessions
    with _STATE_LOCK:
        if len(_SESSIONS) <= max_sessions:
            return
        # Find session with oldest turn_start_time (least recently active)
        oldest_id = min(_SESSIONS, key=lambda sid: _SESSIONS[sid].turn_start_time)
        _SESSIONS.pop(oldest_id, None)
        _MODELS.pop(oldest_id, None)
        _PROVIDERS.pop(oldest_id, None)
        logger.debug(
            "tps-counter: LRU evicted session %s (over %d limit)",
            oldest_id[:8],
            max_sessions,
        )
