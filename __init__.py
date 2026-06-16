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


def _get_session(session_id: str) -> _SessionTPS:
    with _STATE_LOCK:
        if session_id not in _SESSIONS:
            _SESSIONS[session_id] = _SessionTPS()
        return _SESSIONS[session_id]


def _evaluate_alert(session_id: str, state: _SessionTPS) -> None:
    """Evaluate TPS threshold alert state for a session.

    Must be called inside _STATE_LOCK. Updates alert_state, alert_threshold,
    and fires tps_alert hook on state transitions.
    """
    cfg = _ALERT_CONFIG
    current_tps = state.last_call_tps

    # Phase 1: Determine threshold
    if state.alert_threshold is None:
        # If user provided a fixed threshold via config, use it immediately
        if cfg["threshold"] is not None:
            state.alert_threshold = cfg["threshold"]
            logger.info(
                "tps-counter: TPS threshold for session %s = %.1f tok/s (from config)",
                session_id[:8], state.alert_threshold,
            )
        else:
            # Auto-calculate from cold-start samples
            cold_start_n = cfg["cold_start_calls"]
            state.cold_start_samples.append(current_tps)
            state.recent_tps_samples.append(current_tps)
            if len(state.cold_start_samples) < cold_start_n:
                return  # Not enough samples yet
            # Baseline established — calculate auto-threshold
            baseline = sum(state.cold_start_samples) / len(state.cold_start_samples)
            factor = cfg["cold_start_factor"]
            state.alert_threshold = baseline * factor
            logger.info(
                "tps-counter: auto-threshold for session %s = %.1f tok/s "
                "(baseline %.1f × %.0f%%)",
                session_id[:8], state.alert_threshold, baseline, factor * 100,
            )

    # Phase 2: Rolling window evaluation
    window_size = cfg["eval_window"]
    state.recent_tps_samples.append(current_tps)
    # Keep only the last N samples
    if len(state.recent_tps_samples) > window_size:
        state.recent_tps_samples = state.recent_tps_samples[-window_size:]

    rolling_avg = sum(state.recent_tps_samples) / len(state.recent_tps_samples)
    threshold = state.alert_threshold
    assert threshold is not None  # guaranteed after Phase 1

    # State transitions
    if rolling_avg < threshold and state.alert_state != "firing":
        state.alert_state = "firing"
        state.alert_fired_at = time.time()
        _emit_alert(session_id, state, rolling_avg, threshold)
    elif rolling_avg >= threshold and state.alert_state == "firing":
        state.alert_state = "resolved"
        state.alert_resolved_at = time.time()
        _emit_alert(session_id, state, rolling_avg, threshold)


def _emit_alert(
    session_id: str,
    state: _SessionTPS,
    tps: float,
    threshold: float,
) -> None:
    """Fire the tps_alert hook via the plugin manager."""
    global _ALERT_HOOK_MANAGER
    if _ALERT_HOOK_MANAGER is None:
        return
    try:
        _ALERT_HOOK_MANAGER.invoke_hook(
            "tps_alert",
            session_id=session_id,
            state=state.alert_state,
            tps=round(tps, 1),
            threshold=round(threshold, 1),
            timestamp=time.time(),
        )
    except Exception as exc:
        logger.debug("tps-counter: tps_alert hook emission failed: %s", exc)


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

    # Record TPS and evaluate alert under the state lock
    with _STATE_LOCK:
        state.record(output_tokens, duration, input_tokens)
        _evaluate_alert(session_id, state)

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
                # Alert state for status bar
                with _STATE_LOCK:
                    snapshot["alert_state"] = state.alert_state
                    snapshot["alert_threshold"] = state.alert_threshold
                    if state.alert_state == "firing":
                        snapshot["alert_indicator"] = "⚠ TPS ALERT"
                    else:
                        snapshot["alert_indicator"] = ""
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
    global _ALERT_HOOK_MANAGER

    # Read alert configuration from environment variables
    env_threshold = os.environ.get("TPS_THRESHOLD")
    if env_threshold is not None:
        try:
            _ALERT_CONFIG["threshold"] = float(env_threshold)
        except ValueError:
            logger.warning(
                "tps-counter: invalid TPS_THRESHOLD=%r, using auto-calculation",
                env_threshold,
            )

    env_window = os.environ.get("TPS_EVAL_WINDOW")
    if env_window is not None:
        try:
            _ALERT_CONFIG["eval_window"] = int(env_window)
        except ValueError:
            logger.warning(
                "tps-counter: invalid TPS_EVAL_WINDOW=%r, using default 5",
                env_window,
            )

    # If user set a fixed threshold, pre-populate it for all new sessions
    if _ALERT_CONFIG["threshold"] is not None:
        logger.info(
            "tps-counter: TPS threshold set to %.1f tok/s (from env)",
            _ALERT_CONFIG["threshold"],
        )

    # Register hooks
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
        return {
            "calls": 0, "avg_tps": 0, "last_tps": 0, "peak_tps": 0,
            "total_output_tokens": 0, "total_input_tokens": 0, "total_tokens": 0,
        }
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


def _cleanup_session(session_id: str) -> None:
    """Remove all in-memory state for a session."""
    with _STATE_LOCK:
        _SESSIONS.pop(session_id, None)
    logger.debug("tps-counter: cleaned up session %s", session_id[:8])
