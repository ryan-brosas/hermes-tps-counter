"""tps-counter — Hermes plugin that tracks tokens-per-second throughput.

Hooks into post_api_request to capture output_tokens and api_duration
after each LLM call. Maintains per-session stats and prints a compact
TPS summary after each turn.

No configuration required — works out of the box.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import threading
import time
from typing import Any, Dict, List, Mapping

logger = logging.getLogger(__name__)

# Per-session TPS state, keyed by session_id
_STATE_LOCK = threading.Lock()
_SESSIONS: Dict[str, "_SessionTPS"] = {}

_PLUGIN_NAME = "tps-counter"
_PLUGIN_VERSION = "1.0.0"
_OBSERVABILITY_CONTRACT_VERSION = "1.0.0"

_PRIVACY_MODE_ENV = "HERMES_TPS_PRIVACY_MODE"
_PRIVACY_SECRET_ENV = "HERMES_TPS_PRIVACY_SALT"
_PRIVACY_SCOPE_ENV = "HERMES_TPS_PRIVACY_SCOPE"
_PRIVACY_FIELDS_ENV = "HERMES_TPS_PRIVACY_FIELDS"
_PRIVACY_TREATMENTS_ENV = "HERMES_TPS_PRIVACY_TREATMENTS"
_PRIVACY_DEFAULT_SCOPE = "hermes-tps-counter"
_PRIVACY_DEFAULT_SECRET = "hermes-tps-counter-default-privacy-key"
_PRIVACY_IDENTIFIER_FIELDS = frozenset({"session_id", "model", "provider"})
_PRIVACY_VALID_TREATMENTS = frozenset({"raw", "pseudonymized", "redacted", "omitted"})


class _PrivacyPolicy:
    """Dependency-free redaction policy for outbound observability identifiers."""

    __slots__ = ("mode", "scope", "secret", "field_treatments")

    def __init__(
        self,
        mode: str = "disabled",
        *,
        secret: str | None = None,
        scope: str = _PRIVACY_DEFAULT_SCOPE,
        field_treatments: Mapping[str, str] | None = None,
    ) -> None:
        normalized_mode = (mode or "disabled").strip().lower()
        if normalized_mode in {"", "0", "false", "off", "disabled", "raw", "none"}:
            normalized_mode = "disabled"
        elif normalized_mode in {"1", "true", "on", "enabled", "pseudonym", "pseudonymized", "hash", "hashed"}:
            normalized_mode = "pseudonymized"
        elif normalized_mode == "redact":
            normalized_mode = "redacted"
        elif normalized_mode == "omit":
            normalized_mode = "omitted"
        elif normalized_mode not in {"pseudonymized", "redacted", "omitted"}:
            normalized_mode = "disabled"

        self.mode = normalized_mode
        self.scope = scope or _PRIVACY_DEFAULT_SCOPE
        self.secret = secret if secret is not None else _PRIVACY_DEFAULT_SECRET
        self.field_treatments = self._normalize_treatments(field_treatments)

    @staticmethod
    def _normalize_treatments(field_treatments: Mapping[str, str] | None) -> Dict[str, str]:
        treatments = {
            field: "raw" for field in _PRIVACY_IDENTIFIER_FIELDS
        }
        if field_treatments:
            for raw_field, raw_treatment in field_treatments.items():
                field = str(raw_field).strip()
                treatment = str(raw_treatment).strip().lower()
                if field and treatment in _PRIVACY_VALID_TREATMENTS:
                    treatments[field] = treatment
        return treatments

    @property
    def enabled(self) -> bool:
        return self.mode != "disabled"

    def treatment_for(self, field: str) -> str:
        if not self.enabled:
            return "raw"
        return self.field_treatments.get(field, "raw")

    def redact_value(self, field: str, value: Any) -> Any:
        treatment = self.treatment_for(field)
        if treatment == "raw" or value is None:
            return value
        if treatment == "omitted":
            return _OMITTED
        if treatment == "redacted":
            return "[redacted]"
        raw_value = str(value)
        digest = hmac.new(
            self.secret.encode("utf-8"),
            f"{self.scope}:{field}:{raw_value}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:16]
        return f"{field}:pseudonym:{digest}"

    def redact_payload(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        redacted: Dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, Mapping):
                redacted[key] = self.redact_payload(value)
                continue
            treated = self.redact_value(key, value)
            if treated is not _OMITTED:
                redacted[key] = treated
        return redacted

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "enabled": self.enabled,
            "scope": self.scope,
            "secret_configured": bool(os.environ.get(_PRIVACY_SECRET_ENV)),
            "algorithm": "hmac-sha256-truncated-16" if self.enabled else None,
            "identifier_fields": sorted(self.field_treatments.keys()),
            "field_treatments": {
                field: self.treatment_for(field)
                for field in sorted(self.field_treatments.keys())
            },
            "secret_material_exposed": False,
        }


class _OmittedValue:
    pass


_OMITTED = _OmittedValue()


def _parse_privacy_fields(raw_fields: str | None) -> set[str]:
    fields = set(_PRIVACY_IDENTIFIER_FIELDS)
    if raw_fields:
        fields.update(field.strip() for field in raw_fields.split(",") if field.strip())
    return fields


def _parse_privacy_treatments(raw_treatments: str | None, default_treatment: str) -> Dict[str, str]:
    fields = _parse_privacy_fields(os.environ.get(_PRIVACY_FIELDS_ENV))
    treatments = {field: default_treatment for field in fields}
    if raw_treatments:
        for item in raw_treatments.split(","):
            if "=" not in item:
                continue
            field, treatment = (part.strip() for part in item.split("=", 1))
            if field and treatment in _PRIVACY_VALID_TREATMENTS:
                treatments[field] = treatment
    return treatments


def _get_privacy_policy() -> _PrivacyPolicy:
    mode = os.environ.get(_PRIVACY_MODE_ENV, "disabled")
    normalized = (mode or "disabled").strip().lower()
    if normalized in {"", "0", "false", "off", "disabled", "raw", "none"}:
        default_treatment = "raw"
    elif normalized in {"redact", "redacted"}:
        default_treatment = "redacted"
    elif normalized in {"omit", "omitted"}:
        default_treatment = "omitted"
    else:
        default_treatment = "pseudonymized"
    return _PrivacyPolicy(
        mode,
        secret=os.environ.get(_PRIVACY_SECRET_ENV),
        scope=os.environ.get(_PRIVACY_SCOPE_ENV, _PRIVACY_DEFAULT_SCOPE),
        field_treatments=_parse_privacy_treatments(os.environ.get(_PRIVACY_TREATMENTS_ENV), default_treatment),
    )


def _redact_identifier(field: str, value: Any, policy: _PrivacyPolicy | None = None) -> Any:
    """Redact one outbound identifier field according to the shared TPS policy."""
    return (policy or _get_privacy_policy()).redact_value(field, value)


def _redact_payload(payload: Mapping[str, Any], policy: _PrivacyPolicy | None = None) -> Dict[str, Any]:
    """Redact identifier-like fields in an outbound mapping using the shared policy."""
    return (policy or _get_privacy_policy()).redact_payload(payload)


def get_privacy_diagnostics() -> Dict[str, Any]:
    """Return secret-safe privacy mode diagnostics for consumers and tests."""
    return _get_privacy_policy().diagnostics()


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
    privacy_policy = _get_privacy_policy()
    # Expose TPS snapshot for status bar integration
    try:
        from hermes_cli import _ACTIVE_CLI_INSTANCE
        cli = _ACTIVE_CLI_INSTANCE
        if cli is not None:
            agent = getattr(cli, "agent", None)
            if agent is not None:
                snapshot = {
                    "last_tps": state.last_call_tps,
                    "avg_tps": state.avg_tps,
                    "peak_tps": state.peak_tps,
                    "output_tokens": state.total_output_tokens,
                    # Freshness metadata for stale/cross-session detection
                    "updated_at": time.time(),
                    "updated_monotonic": time.monotonic(),
                    "session_id": session_id,
                }
                for identifier_field in ("model", "provider"):
                    if identifier_field in kwargs and kwargs[identifier_field] is not None:
                        snapshot[identifier_field] = kwargs[identifier_field]
                agent._tps_snapshot = _redact_payload(snapshot, privacy_policy)
    except Exception as exc:
        logger.debug("tps-counter: failed to inject status bar data: %s", exc)

    # Log at debug level so it doesn't spam
    log_session_id = _redact_identifier("session_id", session_id, privacy_policy)
    if log_session_id is _OMITTED:
        log_session_id = "[omitted]"
    elif not privacy_policy.enabled:
        log_session_id = str(log_session_id)[:8]
    logger.debug(
        "TPS: %.1f tok/s (%d tokens in %.2fs) [session %s]",
        state.last_call_tps,
        output_tokens,
        duration,
        log_session_id,
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
    privacy = get_privacy_diagnostics()
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
        "privacy": {
            "mode": privacy["mode"],
            "enabled": privacy["enabled"],
            "configuration": {
                "mode_env": _PRIVACY_MODE_ENV,
                "secret_env": _PRIVACY_SECRET_ENV,
                "scope_env": _PRIVACY_SCOPE_ENV,
                "fields_env": _PRIVACY_FIELDS_ENV,
                "field_treatments_env": _PRIVACY_TREATMENTS_ENV,
                "secret_configured": privacy["secret_configured"],
                "secret_material_exposed": False,
            },
            "identifier_fields": privacy["identifier_fields"],
            "field_treatments": privacy["field_treatments"],
            "treatment_values": {
                "raw": "Identifier is emitted unchanged; this is the default disabled/backward-compatible behavior.",
                "pseudonymized": "Identifier is replaced by a deterministic HMAC-SHA256 pseudonym scoped by field and configured scope.",
                "redacted": "Identifier is replaced by a constant [redacted] marker.",
                "omitted": "Identifier field is removed from outbound payloads when the surface can tolerate omission.",
            },
            "deterministic_grouping": {
                "available_when": "field_treatments[field] == 'pseudonymized'",
                "stable_for": "same raw value, field name, configured scope, and secret/salt",
                "changes_when": "the raw value, field, scope, or secret/salt changes",
                "raw_values_recoverable_from_output": False,
            },
            "trusted_state": "Raw identifiers remain internal for session lookup and TPS correctness; redaction is applied at outbound boundaries.",
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
                    "semantics": "Session that produced the snapshot; compare with the active session to prevent cross-session display leakage. In disabled mode this is the raw session id for backward compatibility; in enabled privacy mode this field follows privacy.field_treatments.session_id.",
                    "privacy_treatment": privacy["field_treatments"].get("session_id", "raw"),
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
