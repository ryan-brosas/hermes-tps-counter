"""tps-counter — Hermes plugin that tracks tokens-per-second throughput.

Hooks into post_api_request to capture output_tokens and api_duration
after each LLM call. Maintains per-session stats and prints a compact
TPS summary after each turn.

No configuration required — works out of the box.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

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

# Persistent store (set during register, may remain None on failure)
_STORE: Optional[Any] = None  # PersistentSessionStore | None

# Alert configuration (set during register())
_ALERT_CONFIG: Dict[str, Any] = {
    "threshold": None,       # TPS_THRESHOLD env var (None = auto-calculate)
    "eval_window": 5,        # TPS_EVAL_WINDOW env var
    "cold_start_calls": 10,  # First N calls establish baseline
    "cold_start_factor": 0.5, # threshold = baseline * factor
}

# Hook manager reference for emitting tps_alert events (set during register())
_ALERT_HOOK_MANAGER: Optional[Any] = None


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
        # Alert fields
        "alert_state",
        "alert_threshold",
        "alert_fired_at",
        "alert_resolved_at",
        "cold_start_samples",
        "recent_tps_samples",
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
        # Alert state
        self.alert_state: str = "idle"  # idle | firing | resolved
        self.alert_threshold: Optional[float] = None
        self.alert_fired_at: Optional[float] = None
        self.alert_resolved_at: Optional[float] = None
        self.cold_start_samples: List[float] = []
        self.recent_tps_samples: List[float] = []

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
        return None


def _persist_state(session_id: str, state: _SessionTPS) -> None:
    """Write-through to persistent store if available."""
    if _STORE is None:
        return
    try:
        _STORE.save(session_id, state)
    except Exception as exc:
        logger.warning("tps-counter: DB write failed, disabling store: %s", exc)


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

    if output_tokens <= 0 or duration <= 0:
        return

    state = _get_session(session_id)
    model = kwargs.get("model", "") or ""
    with _STATE_LOCK:
        state.record(output_tokens, duration, input_tokens)
        # Write-through to SQLite
        _persist_state(session_id, state)
        # Per-model tracking
        if model:
            model_state = _get_model(session_id, model)
            model_state.record(output_tokens, duration)
        # Per-provider tracking
        provider = _extract_provider(model)
        provider_state = _get_provider(session_id, provider)
        provider_state.record(output_tokens, duration)

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

    # Log at debug level so it doesn't spam
    logger.debug(
        "TPS: %.1f tok/s (%d tokens in %.2fs) [session %s]",
        state.last_call_tps,
        output_tokens,
        duration,
        session_id[:8],
    )


def register(ctx: Any) -> None:
    """Plugin entry point — called by Hermes plugin loader."""
    global _STORE

    # Read DB path from plugin config, with sensible default
    default_path = os.path.expanduser("~/.hermes/plugins/tps-counter/tps.db")
    try:
        config = {}
        if hasattr(ctx, "get_config"):
            config = ctx.get_config("tps_counter", {}) or {}
        elif hasattr(ctx, "config"):
            config = getattr(ctx, "config", {}).get("tps_counter", {}) or {}
    except Exception:
        config = {}

    db_path = config.get("db_path", default_path)

    # Initialize persistent store
    try:
        from store import PersistentSessionStore

        _STORE = PersistentSessionStore(db_path)
        logger.info("tps-counter: persistent store at %s", db_path)
    except Exception as exc:
        logger.warning("tps-counter: persistence unavailable, using in-memory only: %s", exc)
        _STORE = None

    ctx.register_hook("post_api_request", _on_post_api_request)

    # Register tps_alert hook (no-op default so emission doesn't error)
    ctx.register_hook("tps_alert", lambda **kw: None)

    # Capture manager reference for hook emission
    _ALERT_HOOK_MANAGER = ctx._manager

    logger.info("tps-counter plugin registered")


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
        "alert_state": state.alert_state,
        "alert_threshold": round(state.alert_threshold, 1) if state.alert_threshold is not None else None,
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
