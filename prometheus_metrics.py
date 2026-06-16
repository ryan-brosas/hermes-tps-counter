"""Prometheus metrics exporter for TPS counter plugin.

Provides a ``/metrics`` endpoint in Prometheus text exposition format,
enabling Grafana, Prometheus, and other monitoring tools to scrape TPS data.

All metrics use a custom CollectorRegistry to avoid collisions with
other plugins or applications using prometheus_client.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency — graceful degradation when prometheus_client absent
# ---------------------------------------------------------------------------
try:
    from prometheus_client import CollectorRegistry, Gauge, Counter, Histogram, generate_latest
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.info("prometheus_metrics: prometheus_client not installed, /metrics disabled")

# ---------------------------------------------------------------------------
# Registry (isolated from global default)
# ---------------------------------------------------------------------------
REGISTRY: Any = None

# Session-level gauges
_tps_last_call: Any = None
_tps_avg: Any = None
_tps_peak: Any = None

# Counters
_tps_tokens_total: Any = None
_tps_api_calls_total: Any = None

# Per-model gauges
_tps_model_avg: Any = None
_tps_model_peak: Any = None

# Per-provider gauges
_tps_provider_avg: Any = None
_tps_provider_peak: Any = None

# Operational health counters
_usage_extraction_failures: Any = None
_db_write_errors: Any = None
_db_read_errors: Any = None
_ws_broadcast_failures: Any = None
_ws_dead_clients: Any = None
_rate_limited_total: Any = None

# Operational health gauges
_ws_active_connections: Any = None

# Distribution histograms
_tps_distribution: Any = None
_api_call_latency_seconds: Any = None

# Keep histogram model label cardinality bounded. Observations for labels beyond
# the cap are discarded silently rather than creating unbounded time series.
_label_cardinality_cap = 50
_admitted_labels: dict[str, set[str]] = {"model": set()}

TPS_DISTRIBUTION_BUCKETS = (1, 5, 10, 25, 50, 100, 250, 500, 1000)
API_CALL_LATENCY_BUCKETS = (0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)


def _admit_label(label_name: str, value: str) -> bool:
    """Return True if a label value is within the configured cardinality cap."""
    admitted = _admitted_labels.setdefault(label_name, set())
    if value in admitted:
        return True
    if len(admitted) >= _label_cardinality_cap:
        return False
    admitted.add(value)
    return True


def _init_metrics() -> None:
    """Create all metric objects inside the custom registry."""
    global REGISTRY
    global _tps_last_call, _tps_avg, _tps_peak
    global _tps_tokens_total, _tps_api_calls_total
    global _tps_model_avg, _tps_model_peak
    global _tps_provider_avg, _tps_provider_peak
    global _usage_extraction_failures, _db_write_errors, _db_read_errors
    global _ws_broadcast_failures, _ws_dead_clients, _rate_limited_total
    global _ws_active_connections
    global _tps_distribution, _api_call_latency_seconds

    _admitted_labels["model"] = set()

    if not _PROMETHEUS_AVAILABLE:
        return

    REGISTRY = CollectorRegistry()

    # Session-level gauges
    _tps_last_call = Gauge(
        "tps_last_call",
        "Tokens per second for the most recent API call",
        ["session_id"],
        registry=REGISTRY,
    )
    _tps_avg = Gauge(
        "tps_avg",
        "Rolling average tokens per second for the session",
        ["session_id"],
        registry=REGISTRY,
    )
    _tps_peak = Gauge(
        "tps_peak",
        "Peak tokens per second observed in this session",
        ["session_id"],
        registry=REGISTRY,
    )

    # Counters
    _tps_tokens_total = Counter(
        "tps_tokens_total",
        "Total tokens processed by the session",
        ["session_id", "direction"],
        registry=REGISTRY,
    )
    _tps_api_calls_total = Counter(
        "tps_api_calls_total",
        "Total API calls recorded for the session",
        ["session_id"],
        registry=REGISTRY,
    )

    # Per-model gauges
    _tps_model_avg = Gauge(
        "tps_model_avg",
        "Average tokens per second for a specific model within a session",
        ["session_id", "model"],
        registry=REGISTRY,
    )
    _tps_model_peak = Gauge(
        "tps_model_peak",
        "Peak tokens per second for a specific model within a session",
        ["session_id", "model"],
        registry=REGISTRY,
    )

    # Per-provider gauges
    _tps_provider_avg = Gauge(
        "tps_provider_avg",
        "Average tokens per second for a specific provider within a session",
        ["session_id", "provider"],
        registry=REGISTRY,
    )
    _tps_provider_peak = Gauge(
        "tps_provider_peak",
        "Peak tokens per second for a specific provider within a session",
        ["session_id", "provider"],
        registry=REGISTRY,
    )

    # Operational health counters
    _usage_extraction_failures = Counter(
        "usage_extraction_failures_total",
        "Total usage extraction failures (non-empty input yielded zero tokens)",
        registry=REGISTRY,
    )
    _db_write_errors = Counter(
        "db_write_errors_total",
        "Total database write errors during state persistence",
        registry=REGISTRY,
    )
    _db_read_errors = Counter(
        "db_read_errors_total",
        "Total database read errors during state hydration",
        registry=REGISTRY,
    )
    _ws_broadcast_failures = Counter(
        "ws_broadcast_failures_total",
        "Total WebSocket broadcast failures (individual client send errors)",
        registry=REGISTRY,
    )
    _ws_dead_clients = Counter(
        "ws_dead_clients_total",
        "Total dead WebSocket clients removed after send failure",
        registry=REGISTRY,
    )
    _rate_limited_total = Counter(
        "tps_api_rate_limited_total",
        "Total requests rejected by API rate limiting",
        registry=REGISTRY,
    )

    # Operational health gauges
    _ws_active_connections = Gauge(
        "ws_active_connections",
        "Number of currently active WebSocket connections",
        registry=REGISTRY,
    )

    # Distribution histograms
    _tps_distribution = Histogram(
        "tps_distribution",
        "Distribution of tokens-per-second throughput per API call",
        ["model"],
        buckets=TPS_DISTRIBUTION_BUCKETS,
        registry=REGISTRY,
    )
    _api_call_latency_seconds = Histogram(
        "api_call_latency_seconds",
        "Distribution of LLM API call latency in seconds",
        ["model"],
        buckets=API_CALL_LATENCY_BUCKETS,
        registry=REGISTRY,
    )


# Initialize on module load
_init_metrics()


def update_metrics(
    session_id: str,
    state: Any,
    models: Dict[str, Any] | None = None,
    providers: Dict[str, Any] | None = None,
) -> None:
    """Update all Prometheus metrics from current in-memory state.

    Called after each API hook invocation. Must be fast (sub-millisecond).
    prometheus_client gauge.set() and counter.inc() are thread-safe internally.

    Args:
        session_id: The session identifier.
        state: A ``_SessionTPS`` instance with current metrics.
        models: Dict mapping model_name → _ModelTPS (may be None/empty).
        providers: Dict mapping provider_name → _ProviderTPS (may be None/empty).
    """
    if not _PROMETHEUS_AVAILABLE or REGISTRY is None:
        return

    try:
        # Session-level gauges
        _tps_last_call.labels(session_id=session_id).set(state.last_call_tps)
        _tps_avg.labels(session_id=session_id).set(state.avg_tps)
        _tps_peak.labels(session_id=session_id).set(state.peak_tps)

        # Counters — inc by the delta since last call (not cumulative)
        # We use .inc() with the latest call's tokens since prometheus counters
        # are monotonically increasing and state tracks cumulative totals.
        # The gauge approach: we set gauges directly, counters inc by delta.
        _tps_api_calls_total.labels(session_id=session_id).inc(1)

        # Token counters — inc by this call's tokens
        if hasattr(state, "last_call_output_tokens"):
            _tps_tokens_total.labels(
                session_id=session_id, direction="output"
            ).inc(state.last_call_output_tokens)
        if hasattr(state, "last_call_input_tokens"):
            _tps_tokens_total.labels(
                session_id=session_id, direction="input"
            ).inc(state.last_call_input_tokens)

        # Per-model gauges
        if models:
            for model_name, model_state in models.items():
                _tps_model_avg.labels(
                    session_id=session_id, model=model_name
                ).set(model_state.avg_tps)
                _tps_model_peak.labels(
                    session_id=session_id, model=model_name
                ).set(model_state.peak_tps)

        # Per-provider gauges
        if providers:
            for provider_name, provider_state in providers.items():
                _tps_provider_avg.labels(
                    session_id=session_id, provider=provider_name
                ).set(provider_state.avg_tps)
                _tps_provider_peak.labels(
                    session_id=session_id, provider=provider_name
                ).set(provider_state.peak_tps)

    except Exception as exc:
        logger.debug("prometheus_metrics: update failed: %s", exc)


def generate_metrics() -> bytes:
    """Generate Prometheus text exposition format from the registry.

    Returns:
        UTF-8 encoded bytes in Prometheus text format with HELP/TYPE lines.
        Returns empty bytes if prometheus_client is unavailable.
    """
    if not _PROMETHEUS_AVAILABLE or REGISTRY is None:
        return b""
    try:
        return generate_latest(REGISTRY)
    except Exception as exc:
        logger.debug("prometheus_metrics: generate failed: %s", exc)
        return b""


def metrics_available() -> bool:
    """Check whether prometheus_client is installed and metrics are ready."""
    return _PROMETHEUS_AVAILABLE and REGISTRY is not None


def observe_tps(value: float, model: str) -> None:
    """Record one TPS observation for percentile analysis.

    Uses a bounded ``model`` label. If the model cardinality cap has already
    been reached, the observation is dropped silently to protect Prometheus.
    """
    if not _PROMETHEUS_AVAILABLE or _tps_distribution is None:
        return
    model_label = model or "unknown"
    if not _admit_label("model", model_label):
        return
    try:
        _tps_distribution.labels(model=model_label).observe(float(value))
    except Exception as exc:
        logger.debug("prometheus_metrics: TPS histogram observe failed: %s", exc)


def observe_latency(seconds: float, model: str) -> None:
    """Record one API latency observation for percentile analysis.

    Uses a bounded ``model`` label. If the model cardinality cap has already
    been reached, the observation is dropped silently to protect Prometheus.
    """
    if not _PROMETHEUS_AVAILABLE or _api_call_latency_seconds is None:
        return
    model_label = model or "unknown"
    if not _admit_label("model", model_label):
        return
    try:
        _api_call_latency_seconds.labels(model=model_label).observe(float(seconds))
    except Exception as exc:
        logger.debug("prometheus_metrics: latency histogram observe failed: %s", exc)


# ---------------------------------------------------------------------------
# Health metric increment functions (event-driven, not state-synced)
# ---------------------------------------------------------------------------

def increment_usage_extraction_failure() -> None:
    """Increment the usage extraction failure counter.

    Called when _extract_usage returns (0, 0) for a non-empty input dict.
    Thread-safe — prometheus_client Counter.inc() is internally thread-safe.
    """
    if not _PROMETHEUS_AVAILABLE or _usage_extraction_failures is None:
        return
    _usage_extraction_failures.inc()


def increment_db_write_error() -> None:
    """Increment the DB write error counter.

    Called when _persist_state catches an exception.
    """
    if not _PROMETHEUS_AVAILABLE or _db_write_errors is None:
        return
    _db_write_errors.inc()


def increment_db_read_error() -> None:
    """Increment the DB read error counter.

    Called when _hydrate_from_db catches an exception.
    """
    if not _PROMETHEUS_AVAILABLE or _db_read_errors is None:
        return
    _db_read_errors.inc()


def increment_ws_broadcast_failure() -> None:
    """Increment the WebSocket broadcast failure counter.

    Called per failed client in ConnectionManager._safe_send.
    """
    if not _PROMETHEUS_AVAILABLE or _ws_broadcast_failures is None:
        return
    _ws_broadcast_failures.inc()


def increment_ws_dead_client() -> None:
    """Increment the dead WebSocket client counter.

    Called when a dead client is removed in ConnectionManager._safe_send.
    """
    if not _PROMETHEUS_AVAILABLE or _ws_dead_clients is None:
        return
    _ws_dead_clients.inc()


def increment_rate_limited() -> None:
    """Increment the API rate-limited requests counter."""
    if not _PROMETHEUS_AVAILABLE or _rate_limited_total is None:
        return
    _rate_limited_total.inc()


def set_ws_active_connections(count: int) -> None:
    """Set the active WebSocket connections gauge.

    Called after connect/disconnect in ConnectionManager.
    """
    if not _PROMETHEUS_AVAILABLE or _ws_active_connections is None:
        return
    _ws_active_connections.set(count)


def reset_metrics() -> None:
    """Reset all metric state. Used in tests to ensure clean isolation."""
    _init_metrics()
