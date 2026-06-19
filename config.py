"""Centralized configuration for the TPS counter plugin.

Merge precedence: defaults < TOML file < environment variables < ctx overrides.

Environment variables use the ``TPS_COUNTER_`` prefix and map to field names
with ``MAX_SESSIONS`` → ``TPS_COUNTER_MAX_SESSIONS``, etc.

Optional TOML config file: ``~/.hermes/plugins/tps-counter/config.toml``
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Module-level singleton state
_CONFIG_LOCK = threading.Lock()
_CONFIG_SINGLETON: Optional["TPSConfig"] = None

# Default config file path
_DEFAULT_CONFIG_DIR = Path.home() / ".hermes" / "plugins" / "tps-counter"
_DEFAULT_CONFIG_FILE = _DEFAULT_CONFIG_DIR / "config.toml"

# Env var prefix
_ENV_PREFIX = "TPS_COUNTER_"

# Mapping from env var suffix to dataclass field name
_ENV_FIELD_MAP: Dict[str, str] = {
    "MAX_SESSIONS": "max_sessions",
    "DB_PATH": "db_path",
    "RETENTION_DAYS": "retention_days",
    "API_HOST": "api_host",
    "API_PORT": "api_port",
    "PROMETHEUS_ENABLED": "prometheus_enabled",
    "PROMETHEUS_LEGACY_SESSION_LABELS": "prometheus_legacy_session_labels",
    "PROMETHEUS_LABEL_CARDINALITY_CAP": "prometheus_label_cardinality_cap",
    "API_ENABLED": "api_enabled",
    "REQUESTS_PER_MINUTE": "requests_per_minute",
    "BURST_SIZE": "burst_size",
}


@dataclass
class TPSConfig:
    """Typed configuration for the TPS counter plugin.

    All current hardcoded defaults are preserved here as field defaults.
    """

    max_sessions: int = 50
    """LRU eviction threshold for in-memory session tracking."""

    db_path: str = field(default_factory=lambda: str(Path.home() / ".hermes" / "plugins" / "tps-counter" / "tps.db"))
    """Path to the SQLite database file."""

    retention_days: int = 7
    """Number of days to retain call events before expiry cleanup."""

    api_host: str = "127.0.0.1"
    """Host address for the REST API server."""

    api_port: int = 9127
    """Port for the REST API server."""

    prometheus_enabled: bool = False
    """Whether Prometheus metrics endpoint is enabled."""

    prometheus_legacy_session_labels: bool = False
    """Whether to emit legacy Prometheus series labeled by raw session_id."""

    prometheus_label_cardinality_cap: int = 50
    """Max distinct model/provider label values admitted before overflow handling."""

    api_enabled: bool = False
    """Whether the REST API server is enabled."""

    requests_per_minute: int = 60
    """Allowed sustained REST API requests per client IP per minute."""

    burst_size: int = 10
    """Additional burst allowance per client IP above the sustained rate."""


def _coerce_value(field_name: str, raw: str, expected_type: type) -> Any:
    """Coerce a string value to the expected type.

    Returns the coerced value, or raises ValueError/TypeError on failure.
    """
    if expected_type is bool:
        return raw.lower() in ("1", "true", "yes", "on")
    if expected_type is int:
        return int(raw)
    if expected_type is float:
        return float(raw)
    return raw  # str


def _load_from_toml(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration values from a TOML file.

    Args:
        path: Path to the TOML file. Defaults to
              ``~/.hermes/plugins/tps-counter/config.toml``.

    Returns:
        Dict of field name → value, or empty dict if file is missing.
    """
    if path is None:
        path = _DEFAULT_CONFIG_FILE

    try:
        import tomllib
    except ImportError:
        # Python < 3.11 fallback
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            logger.debug("tps-counter config: tomllib not available, skipping TOML config")
            return {}

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.warning("tps-counter config: failed to read TOML file %s: %s", path, exc)
        return {}

    # Flatten: map TOML keys to dataclass field names
    # Supports both flat keys (max_sessions = 50) and nested [api] section
    result: Dict[str, Any] = {}

    # Flat keys (direct field names)
    for fld in fields(TPSConfig):
        if fld.name in data:
            result[fld.name] = data[fld.name]

    # Nested [api] section
    api_section = data.get("api", {})
    if isinstance(api_section, dict):
        if "host" in api_section:
            result.setdefault("api_host", api_section["host"])
        if "port" in api_section:
            result.setdefault("api_port", api_section["port"])
        if "enabled" in api_section:
            result.setdefault("api_enabled", api_section["enabled"])
        rate_limit_section = api_section.get("rate_limit", {})
        if isinstance(rate_limit_section, dict):
            if "requests_per_minute" in rate_limit_section:
                result.setdefault("requests_per_minute", rate_limit_section["requests_per_minute"])
            if "burst_size" in rate_limit_section:
                result.setdefault("burst_size", rate_limit_section["burst_size"])

    # Nested [prometheus] section
    prom_section = data.get("prometheus", {})
    if isinstance(prom_section, dict):
        if "enabled" in prom_section:
            result.setdefault("prometheus_enabled", prom_section["enabled"])
        if "legacy_session_labels" in prom_section:
            result.setdefault("prometheus_legacy_session_labels", prom_section["legacy_session_labels"])
        if "label_cardinality_cap" in prom_section:
            result.setdefault("prometheus_label_cardinality_cap", prom_section["label_cardinality_cap"])

    return result


def _load_from_env() -> Dict[str, Any]:
    """Load configuration values from ``TPS_COUNTER_*`` environment variables.

    Returns:
        Dict of field name → value for any set env vars.
    """
    import typing
    result: Dict[str, Any] = {}
    type_hints = typing.get_type_hints(TPSConfig)
    type_map = {f.name: type_hints.get(f.name, str) for f in fields(TPSConfig)}

    for env_suffix, field_name in _ENV_FIELD_MAP.items():
        env_key = _ENV_PREFIX + env_suffix
        raw = os.environ.get(env_key)
        if raw is None:
            continue
        expected_type = type_map.get(field_name, str)
        try:
            result[field_name] = _coerce_value(field_name, raw, expected_type)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "tps-counter config: invalid value for %s=%r: %s (using default)",
                env_key, raw, exc,
            )
    return result


def _load_from_ctx(ctx: Any) -> Dict[str, Any]:
    """Extract config overrides from a Hermes plugin context.

    Supports ``ctx.get_config("tps_counter", {})`` and nested
    ``api`` / ``prometheus`` sub-dicts.

    Returns:
        Dict of field name → value for any ctx-provided overrides.
    """
    if ctx is None:
        return {}

    try:
        if hasattr(ctx, "get_config"):
            raw = ctx.get_config("tps_counter", {}) or {}
        elif hasattr(ctx, "config"):
            raw = getattr(ctx, "config", {}).get("tps_counter", {}) or {}
        else:
            return {}
    except Exception:
        return {}

    result: Dict[str, Any] = {}

    # Direct field mappings
    direct_keys = {
        "db_path": "db_path",
        "max_sessions": "max_sessions",
        "retention_days": "retention_days",
        "requests_per_minute": "requests_per_minute",
        "burst_size": "burst_size",
        "prometheus_enabled": "prometheus_enabled",
        "prometheus_legacy_session_labels": "prometheus_legacy_session_labels",
        "prometheus_label_cardinality_cap": "prometheus_label_cardinality_cap",
    }
    for ctx_key, field_name in direct_keys.items():
        if ctx_key in raw:
            result[field_name] = raw[ctx_key]

    # Nested api section
    api_section = raw.get("api", {})
    if isinstance(api_section, dict):
        if "host" in api_section:
            result["api_host"] = api_section["host"]
        if "port" in api_section:
            result["api_port"] = api_section["port"]
        if "enabled" in api_section:
            result["api_enabled"] = api_section["enabled"]
        rate_limit_section = api_section.get("rate_limit", {})
        if isinstance(rate_limit_section, dict):
            if "requests_per_minute" in rate_limit_section:
                result["requests_per_minute"] = rate_limit_section["requests_per_minute"]
            if "burst_size" in rate_limit_section:
                result["burst_size"] = rate_limit_section["burst_size"]

    # Nested prometheus section
    prom_section = raw.get("prometheus", {})
    if isinstance(prom_section, dict):
        if "enabled" in prom_section:
            result["prometheus_enabled"] = prom_section["enabled"]
        if "legacy_session_labels" in prom_section:
            result["prometheus_legacy_session_labels"] = prom_section["legacy_session_labels"]
        if "label_cardinality_cap" in prom_section:
            result["prometheus_label_cardinality_cap"] = prom_section["label_cardinality_cap"]

    return result


def _validate(config: TPSConfig) -> None:
    """Validate config values and log warnings for out-of-range values."""
    if config.max_sessions < 1:
        logger.warning("tps-counter config: max_sessions=%d is < 1, clamping to 1", config.max_sessions)
        config.max_sessions = 1
    if config.retention_days < 1:
        logger.warning("tps-counter config: retention_days=%d is < 1, clamping to 1", config.retention_days)
        config.retention_days = 1
    if config.api_port < 1 or config.api_port > 65535:
        logger.warning("tps-counter config: api_port=%d is out of range 1-65535, using default 9127", config.api_port)
        config.api_port = 9127
    if config.requests_per_minute < 1:
        logger.warning(
            "tps-counter config: requests_per_minute=%d is < 1, clamping to 1",
            config.requests_per_minute,
        )
        config.requests_per_minute = 1
    if config.burst_size < 1:
        logger.warning("tps-counter config: burst_size=%d is < 1, clamping to 1", config.burst_size)
        config.burst_size = 1
    if config.prometheus_label_cardinality_cap < 1:
        logger.warning(
            "tps-counter config: prometheus_label_cardinality_cap=%d is < 1, clamping to 1",
            config.prometheus_label_cardinality_cap,
        )
        config.prometheus_label_cardinality_cap = 1


def get_config(ctx: Any = None, *, config_path: Optional[Path] = None) -> TPSConfig:
    """Return the merged TPS configuration singleton.

    Merge order (lowest to highest priority):
    1. Dataclass defaults
    2. TOML config file
    3. Environment variables (``TPS_COUNTER_*``)
    4. Hermes context overrides (``ctx.get_config()``)

    Args:
        ctx: Optional Hermes plugin context for runtime overrides.
        config_path: Optional explicit path to TOML config file (for testing).

    Returns:
        The merged ``TPSConfig`` instance (singleton after first call).
    """
    global _CONFIG_SINGLETON

    # Fast path: already initialized and no ctx override requested
    if _CONFIG_SINGLETON is not None and ctx is None:
        return _CONFIG_SINGLETON

    with _CONFIG_LOCK:
        # Double-check after acquiring lock
        if _CONFIG_SINGLETON is not None and ctx is None:
            return _CONFIG_SINGLETON

        # Layer 1: defaults
        merged: Dict[str, Any] = {}

        # Layer 2: TOML file
        merged.update(_load_from_toml(config_path))

        # Layer 3: environment variables
        merged.update(_load_from_env())

        # Layer 4: ctx overrides (highest priority)
        if ctx is not None:
            merged.update(_load_from_ctx(ctx))

        # Build config object
        config = TPSConfig(**{k: v for k, v in merged.items() if k in {f.name for f in fields(TPSConfig)}})

        # Validate
        _validate(config)

        # Store singleton so runtime paths see the same resolved registration config.
        _CONFIG_SINGLETON = config

        return config


def reset_config() -> None:
    """Reset the singleton config. Used in tests to re-initialize with fresh env/TOML state."""
    global _CONFIG_SINGLETON
    with _CONFIG_LOCK:
        _CONFIG_SINGLETON = None
