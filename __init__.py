"""tps-counter — Hermes plugin that tracks tokens-per-second throughput.

Hooks into post_api_request to capture output_tokens and api_duration
after each LLM call. Maintains per-session stats and prints a compact
TPS summary after each turn.

No configuration required — works out of the box.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Per-session TPS state, keyed by session_id
_STATE_LOCK = threading.Lock()
_SESSIONS: Dict[str, "_SessionTPS"] = {}


class _SessionTPS:
    """Tracks TPS metrics for a single session."""

    __slots__ = (
        "call_count",
        "total_output_tokens",
        "total_duration",
        "last_call_tps",
        "last_call_output_tokens",
        "last_call_duration",
        "peak_tps",
        "turn_start_tokens",
        "turn_start_time",
    )

    def __init__(self) -> None:
        self.call_count: int = 0
        self.total_output_tokens: int = 0
        self.total_duration: float = 0.0
        self.last_call_tps: float = 0.0
        self.last_call_output_tokens: int = 0
        self.last_call_duration: float = 0.0
        self.peak_tps: float = 0.0
        self.turn_start_tokens: int = 0
        self.turn_start_time: float = time.time()

    def record(self, output_tokens: int, duration: float) -> None:
        self.call_count += 1
        self.total_output_tokens += output_tokens
        self.total_duration += duration
        self.last_call_output_tokens = output_tokens
        self.last_call_duration = duration
        if duration > 0:
            self.last_call_tps = output_tokens / duration
            if self.last_call_tps > self.peak_tps:
                self.peak_tps = self.last_call_tps

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
        if self.total_output_tokens > 0:
            parts.append(f"out {self._fmt_tokens(self.total_output_tokens)}")
        return " │ ".join(parts) if parts else ""

    @staticmethod
    def _fmt_tokens(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)


def _get_session(session_id: str) -> _SessionTPS:
    with _STATE_LOCK:
        if session_id not in _SESSIONS:
            _SESSIONS[session_id] = _SessionTPS()
        return _SESSIONS[session_id]


def _on_post_api_request(**kwargs: Any) -> None:
    """Hook callback: record TPS after each LLM API call."""
    session_id = kwargs.get("session_id", "")
    if not session_id:
        return

    usage = kwargs.get("usage", {})
    output_tokens = usage.get("output_tokens", 0) if isinstance(usage, dict) else 0
    duration = kwargs.get("api_duration", 0.0) or 0.0

    if output_tokens <= 0 or duration <= 0:
        return

    state = _get_session(session_id)
    state.record(output_tokens, duration)
    # Expose TPS snapshot for status bar integration
    try:
        from hermes_cli import _ACTIVE_CLI_INSTANCE
        cli = _ACTIVE_CLI_INSTANCE
        if cli is not None:
            agent = getattr(cli, "agent", None)
            if agent is not None:
                agent._tps_snapshot = {
                    "last_tps": state.last_call_tps,
                    "avg_tps": state.avg_tps,
                    "peak_tps": state.peak_tps,
                    "output_tokens": state.total_output_tokens,
                    # Freshness metadata for stale/cross-session detection
                    "updated_at": time.time(),
                    "updated_monotonic": time.monotonic(),
                    "session_id": session_id,
                }
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
    ctx.register_hook("post_api_request", _on_post_api_request)
    logger.info("tps-counter plugin registered")


# Expose state for /usage integration or external queries
def get_tps_stats(session_id: str) -> Dict[str, Any]:
    """Return current TPS stats for a session (callable from /usage)."""
    with _STATE_LOCK:
        state = _SESSIONS.get(session_id)
    if state is None:
        return {"calls": 0, "avg_tps": 0, "last_tps": 0, "peak_tps": 0, "total_output_tokens": 0}
    return {
        "calls": state.call_count,
        "avg_tps": round(state.avg_tps, 1),
        "last_tps": round(state.last_call_tps, 1),
        "peak_tps": round(state.peak_tps, 1),
        "total_output_tokens": state.total_output_tokens,
        "total_duration": round(state.total_duration, 2),
    }
