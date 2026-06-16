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

_PLUGIN_NAME = "tps-counter"
_PLUGIN_VERSION = "1.0.0"
_OBSERVABILITY_CONTRACT_VERSION = "1.0.0"


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


def get_observability_contract() -> Dict[str, Any]:
    """Return a static, machine-readable contract for TPS observability surfaces.

    The contract is intentionally dependency-free and does not inspect live
    session state. It describes the stable fields external consumers may read
    from this plugin and marks optional surfaces that are not present in this
    branch as unavailable.
    """
    return {
        "contract": {
            "name": "hermes-tps-counter-observability",
            "contract_version": _OBSERVABILITY_CONTRACT_VERSION,
            "plugin": {
                "name": _PLUGIN_NAME,
                "version": _PLUGIN_VERSION,
            },
            "generated": "static",
            "stability": "additive",
            "notes": [
                "Consumers should select behavior by contract_version.",
                "Unknown fields and sections are additive and must be ignored by compatible consumers.",
                "Reading this contract does not inspect sessions, mutate plugin state, or require optional API/Prometheus dependencies.",
            ],
        },
        "compatibility": {
            "backward_compatible": True,
            "additive_only": True,
            "unknown_fields": "ignore",
            "breaking_changes": "require a new major contract_version",
            "runtime_overhead": "static metadata only; no session scans, SQLite queries, network calls, timers, or background work",
        },
        "status_snapshot": {
            "available": True,
            "surface": "agent._tps_snapshot",
            "producer": "post_api_request hook",
            "description": "Latest per-session TPS snapshot injected into the active Hermes agent for status-bar consumers.",
            "freshness_guidance": {
                "age_calculation": "time.monotonic() - snapshot['updated_monotonic']",
                "recommended_stale_threshold_seconds": "consumer-defined, commonly 30-120",
                "stale_behavior": "suppress or gray-out stale TPS display when the snapshot age exceeds the consumer threshold",
                "session_mismatch_behavior": "ignore or reset TPS display when snapshot['session_id'] differs from the active session id",
            },
            "fields": {
                "last_tps": {
                    "type": "number",
                    "unit": "tokens_per_second",
                    "source": "output_tokens / api_duration for the most recent successful API call in the session",
                    "semantics": "Unrounded float; zero or absent means no usable recent TPS value.",
                },
                "avg_tps": {
                    "type": "number",
                    "unit": "tokens_per_second",
                    "source": "total output tokens divided by total API duration for the session",
                    "semantics": "Unrounded rolling session average.",
                },
                "peak_tps": {
                    "type": "number",
                    "unit": "tokens_per_second",
                    "source": "maximum last_tps observed for the session",
                    "semantics": "Unrounded peak call throughput.",
                },
                "output_tokens": {
                    "type": "integer",
                    "unit": "tokens",
                    "source": "cumulative output tokens recorded for the session",
                    "semantics": "Total output tokens observed by this plugin for the current session.",
                },
                "updated_at": {
                    "type": "number",
                    "unit": "unix_timestamp_seconds",
                    "source": "time.time() at snapshot creation",
                    "semantics": "Wall-clock timestamp for logging and diagnostics; do not use for robust age calculations.",
                },
                "updated_monotonic": {
                    "type": "number",
                    "unit": "monotonic_seconds",
                    "source": "time.monotonic() at snapshot creation",
                    "semantics": "Use for stale-threshold age checks because it is robust to system clock changes.",
                },
                "session_id": {
                    "type": "string",
                    "unit": None,
                    "source": "post_api_request session_id",
                    "semantics": "Session that produced the snapshot; compare with the active session to prevent cross-session display leakage.",
                },
            },
        },
        "api": {
            "available": True,
            "kind": "in_process_python_helper",
            "surfaces": {
                "get_tps_stats": {
                    "available": True,
                    "call": "get_tps_stats(session_id)",
                    "read_only": True,
                    "description": "Returns rounded current TPS counters for one session without starting an API server.",
                    "absent_session_behavior": {
                        "returns": {
                            "calls": 0,
                            "avg_tps": 0,
                            "last_tps": 0,
                            "peak_tps": 0,
                            "total_output_tokens": 0,
                        },
                        "total_duration": "omitted when the session has not been observed",
                    },
                    "fields": {
                        "calls": {"type": "integer", "unit": "calls", "semantics": "Number of recorded API calls for the session."},
                        "avg_tps": {"type": "number", "unit": "tokens_per_second", "semantics": "Session average TPS rounded to one decimal place."},
                        "last_tps": {"type": "number", "unit": "tokens_per_second", "semantics": "Most recent call TPS rounded to one decimal place."},
                        "peak_tps": {"type": "number", "unit": "tokens_per_second", "semantics": "Peak call TPS rounded to one decimal place."},
                        "total_output_tokens": {"type": "integer", "unit": "tokens", "semantics": "Cumulative output tokens recorded for the session."},
                        "total_duration": {"type": "number", "unit": "seconds", "semantics": "Cumulative recorded API duration rounded to two decimal places; present only for observed sessions."},
                    },
                }
            },
            "routes": {
                "observability_contract": {
                    "available": False,
                    "path": None,
                    "reason": "No REST API routing module is present in this branch.",
                    "consumer_guidance": "Use the get_observability_contract() Python helper as the stable machine-readable surface.",
                }
            },
        },
        "websocket": {
            "available": False,
            "reason": "No WebSocket route or streaming module is present in this branch.",
            "events": {},
            "consumer_guidance": "Do not assume WebSocket TPS events are emitted by this branch; rely on status_snapshot or get_tps_stats metadata instead.",
        },
        "prometheus": {
            "available": False,
            "reason": "No prometheus_metrics.py exporter module is present in this branch.",
            "metrics": {},
            "label_cardinality": {
                "guidance": "Every unique label set creates a time series; avoid unbounded labels such as raw session ids, prompts, user ids, or request ids unless a future contract marks them bounded.",
                "bounded_dimensions": [],
                "high_cardinality_dimensions": [],
            },
            "consumer_guidance": "Do not scrape plugin-specific Prometheus metrics from this branch unless a future contract version marks them available and lists metric names, types, units, and labels.",
        },
    }


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
