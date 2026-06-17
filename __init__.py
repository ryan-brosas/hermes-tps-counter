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

_RETENTION_MAX_SESSIONS_ENV = "HERMES_TPS_MAX_SESSIONS"
_RETENTION_SESSION_TTL_SECONDS_ENV = "HERMES_TPS_SESSION_TTL_SECONDS"


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


class _RetentionPolicy:
    """Opt-in retention policy for bounded in-memory session state."""

    __slots__ = ("max_sessions", "session_ttl_seconds", "max_sessions_status", "session_ttl_status")

    def __init__(
        self,
        *,
        max_sessions: int | None,
        session_ttl_seconds: float | None,
        max_sessions_status: str,
        session_ttl_status: str,
    ) -> None:
        self.max_sessions = max_sessions
        self.session_ttl_seconds = session_ttl_seconds
        self.max_sessions_status = max_sessions_status
        self.session_ttl_status = session_ttl_status

    @property
    def enabled(self) -> bool:
        return self.max_sessions is not None or self.session_ttl_seconds is not None

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": "opportunistic_in_memory" if self.enabled else "disabled",
            "configuration": {
                "max_sessions_env": _RETENTION_MAX_SESSIONS_ENV,
                "session_ttl_seconds_env": _RETENTION_SESSION_TTL_SECONDS_ENV,
            },
            "max_sessions": {
                "enabled": self.max_sessions is not None,
                "value": self.max_sessions,
                "status": self.max_sessions_status,
            },
            "session_ttl_seconds": {
                "enabled": self.session_ttl_seconds is not None,
                "value": self.session_ttl_seconds,
                "status": self.session_ttl_status,
            },
            "scope": "process-local _SESSIONS only",
            "pruning": "opportunistic after successful API request records; no background threads, timers, or external dependencies",
            "identifier_material_exposed": False,
        }


def _parse_positive_int_env(name: str) -> tuple[int | None, str]:
    raw = os.environ.get(name)
    if raw is None:
        return None, "unset"
    value = raw.strip()
    if not value:
        return None, "blank_disabled"
    try:
        parsed = int(value, 10)
    except ValueError:
        return None, "invalid_disabled"
    if parsed <= 0:
        return None, "non_positive_disabled"
    return parsed, "enabled"


def _parse_positive_float_env(name: str) -> tuple[float | None, str]:
    raw = os.environ.get(name)
    if raw is None:
        return None, "unset"
    value = raw.strip()
    if not value:
        return None, "blank_disabled"
    try:
        parsed = float(value)
    except ValueError:
        return None, "invalid_disabled"
    if parsed <= 0:
        return None, "non_positive_disabled"
    return parsed, "enabled"


def _get_retention_policy() -> _RetentionPolicy:
    max_sessions, max_sessions_status = _parse_positive_int_env(_RETENTION_MAX_SESSIONS_ENV)
    session_ttl_seconds, session_ttl_status = _parse_positive_float_env(_RETENTION_SESSION_TTL_SECONDS_ENV)
    return _RetentionPolicy(
        max_sessions=max_sessions,
        session_ttl_seconds=session_ttl_seconds,
        max_sessions_status=max_sessions_status,
        session_ttl_status=session_ttl_status,
    )


def get_retention_diagnostics() -> Dict[str, Any]:
    """Return identifier-safe diagnostics for in-memory session retention policy."""
    return _get_retention_policy().diagnostics()


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
        self.last_updated_monotonic = time.monotonic()

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
        tps_val = output_tokens / duration if duration > 0 else 0.0
        if _STORE is not None:
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
                from prometheus_metrics import (
                    observe_latency as _observe_latency,
                    observe_tps as _observe_tps,
                    update_metrics as _update_prom,
                )
                session_models = _MODELS.get(session_id, {})
                session_providers = _PROVIDERS.get(session_id, {})
                _update_prom(session_id, state, session_models, session_providers)
                _observe_tps(tps_val, model)
                _observe_latency(duration, model)
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


_API_SERVER: Optional[Any] = None  # uvicorn.Server reference for shutdown


def _get_diagnostics_snapshot() -> Dict[str, Any]:
    """Return a snapshot of in-memory state for the diagnostics endpoint.

    Thread-safe: acquires _STATE_LOCK for consistent reads.
    Returns dict with keys: sessions, models, providers, max_sessions.
    """
    with _STATE_LOCK:
        return {
            "sessions": list(_SESSIONS.keys()),
            "models": {sid: list(models.keys()) for sid, models in _MODELS.items()},
            "providers": {sid: list(provs.keys()) for sid, provs in _PROVIDERS.items()},
            "max_sessions": get_config().max_sessions,
        }


def _start_api_server(store: Any, host: str, port: int) -> None:
    """Start the FastAPI TPS API in a daemon thread."""
    global _API_SERVER, _WS_MANAGER, _EVENT_LOOP
    try:
        import asyncio
        import uvicorn
        from api import create_app

        app = create_app(store, get_diagnostics=_get_diagnostics_snapshot)
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
    logger.info("tps-counter plugin registered")

    # Optionally start the REST API server
    if cfg.api_enabled:
        _start_api_server(_STORE, cfg.api_host, cfg.api_port)

    # Optionally enable Prometheus metrics
    if cfg.prometheus_enabled:
        from prometheus_metrics import metrics_available, configure as configure_metrics
        if metrics_available():
            configure_metrics(
                legacy_session_labels=cfg.prometheus_legacy_session_labels,
                label_cardinality_cap=cfg.prometheus_label_cardinality_cap,
            )
            _prometheus_enabled = True
            logger.info("tps-counter: Prometheus metrics enabled at /metrics")
        else:
            logger.warning(
                "tps-counter: prometheus.enabled=true but prometheus_client not installed"
            )


def get_observability_contract() -> Dict[str, Any]:
    """Return a static, machine-readable contract for TPS observability surfaces.

    The contract is intentionally dependency-free and does not inspect live
    session state. It describes the stable fields external consumers may read
    from this plugin and marks optional surfaces that are not present in this
    branch as unavailable.
    """
    privacy = get_privacy_diagnostics()
    retention = get_retention_diagnostics()
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
        "retention": retention,
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
    oldest_id = None
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
    # Remove from persistent store (outside lock to avoid deadlock)
    if oldest_id is not None and _STORE is not None:
        try:
            _STORE.delete(oldest_id)
        except Exception as exc:
            logger.debug("tps-counter: DB eviction failed for %s: %s", oldest_id[:8], exc)
