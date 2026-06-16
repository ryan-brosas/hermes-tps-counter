"""Tests for the Prometheus metrics exporter.

Covers:
- Metric definitions and HELP/TYPE metadata
- update_metrics() gauge and counter updates
- Per-model and per-provider metric labels
- generate_metrics() output format
- /metrics endpoint on FastAPI app
- Thread-safety of concurrent updates
- Config integration (prometheus.enabled)
- Graceful degradation when prometheus_client unavailable
"""
from __future__ import annotations

import sys
import types
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared fixtures (same pattern as other test files)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_hermes_cli():
    """Provide a mock hermes_cli module so imports don't fail."""
    mod = types.ModuleType("hermes_cli")
    mod._ACTIVE_CLI_INSTANCE = None
    with patch.dict(sys.modules, {"hermes_cli": mod}):
        yield


@pytest.fixture(autouse=True)
def _reset_prometheus():
    """Reset prometheus registry between tests for isolation."""
    from prometheus_metrics import reset_metrics
    reset_metrics()
    yield
    reset_metrics()


@pytest.fixture()
def _enable_prometheus():
    """Set the _prometheus_enabled flag in __init__ for tests that need it."""
    import __init__ as plugin
    old = plugin._prometheus_enabled
    plugin._prometheus_enabled = True
    yield
    plugin._prometheus_enabled = old


@pytest.fixture()
def client():
    """FastAPI TestClient with a mock store."""
    from api import create_app

    class _MockStore:
        def load_all(self):
            return {}
        def load(self, sid):
            return None

    app = create_app(_MockStore())
    return TestClient(app)


# ---------------------------------------------------------------------------
# TestMetricDefinitions — metric objects exist with correct names
# ---------------------------------------------------------------------------

class TestMetricDefinitions:
    """Verify all expected metrics are registered in the custom registry."""

    def test_registry_exists(self):
        from prometheus_metrics import REGISTRY
        assert REGISTRY is not None

    def test_metrics_available(self):
        from prometheus_metrics import metrics_available
        assert metrics_available() is True

    def test_session_gauges_registered(self):
        from prometheus_metrics import REGISTRY
        names = {m.name for m in REGISTRY.collect()}
        assert "tps_last_call" in names
        assert "tps_avg" in names
        assert "tps_peak" in names

    def test_counters_registered(self):
        from prometheus_metrics import REGISTRY
        names = {m.name for m in REGISTRY.collect()}
        # prometheus_client strips _total suffix from collected counter names
        assert "tps_tokens" in names
        assert "tps_api_calls" in names

    def test_model_gauges_registered(self):
        from prometheus_metrics import REGISTRY
        names = {m.name for m in REGISTRY.collect()}
        assert "tps_model_avg" in names
        assert "tps_model_peak" in names

    def test_provider_gauges_registered(self):
        from prometheus_metrics import REGISTRY
        names = {m.name for m in REGISTRY.collect()}
        assert "tps_provider_avg" in names
        assert "tps_provider_peak" in names

    def test_histograms_registered(self):
        from prometheus_metrics import REGISTRY
        names = {m.name for m in REGISTRY.collect()}
        assert "tps_distribution" in names
        assert "api_call_latency_seconds" in names


# ---------------------------------------------------------------------------
# TestHistogramMetrics — histogram registration, observations, output
# ---------------------------------------------------------------------------

class TestHistogramMetrics:
    """Verify TPS and API latency histograms behave as expected."""

    def test_observe_helpers_record_histogram_samples(self):
        from prometheus_metrics import REGISTRY, observe_latency, observe_tps

        observe_tps(50.0, "openai/gpt-4o")
        observe_tps(150.0, "openai/gpt-4o")
        observe_latency(1.5, "openai/gpt-4o")
        observe_latency(0.3, "openai/gpt-4o")

        labels = {"model": "openai/gpt-4o"}
        assert REGISTRY.get_sample_value("tps_distribution_count", labels) == 2.0
        assert REGISTRY.get_sample_value("api_call_latency_seconds_count", labels) == 2.0
        assert REGISTRY.get_sample_value(
            "tps_distribution_bucket", {**labels, "le": "100.0"}
        ) >= 1.0
        assert REGISTRY.get_sample_value(
            "api_call_latency_seconds_bucket", {**labels, "le": "2.5"}
        ) == 2.0

    def test_histogram_output_contains_help_type_and_buckets(self):
        from prometheus_metrics import generate_metrics, observe_latency, observe_tps

        observe_tps(50.0, "anthropic/claude-3")
        observe_latency(0.3, "anthropic/claude-3")
        output = generate_metrics().decode()

        assert "# HELP tps_distribution" in output
        assert "# TYPE tps_distribution histogram" in output
        assert "# HELP api_call_latency_seconds" in output
        assert "# TYPE api_call_latency_seconds histogram" in output
        for bucket in ["1.0", "5.0", "10.0", "25.0", "50.0", "100.0", "250.0", "500.0", "1000.0"]:
            assert f'tps_distribution_bucket{{le="{bucket}",model="anthropic/claude-3"}}' in output
        for bucket in ["0.1", "0.25", "0.5", "1.0", "2.5", "5.0", "10.0", "30.0", "60.0"]:
            assert f'api_call_latency_seconds_bucket{{le="{bucket}",model="anthropic/claude-3"}}' in output

    def test_hook_records_histogram_observations(self, _enable_prometheus):
        import __init__ as plugin
        from prometheus_metrics import REGISTRY

        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
            plugin._MODELS.clear()
            plugin._PROVIDERS.clear()

        for tokens, duration in [(100, 2.0), (300, 3.0)]:
            plugin._on_post_api_request(
                session_id="hist_hook_sess",
                usage={"output_tokens": tokens, "input_tokens": 50},
                api_duration=duration,
                model="openai/gpt-4o",
            )

        labels = {"model": "openai/gpt-4o"}
        assert REGISTRY.get_sample_value("tps_distribution_count", labels) == 2.0
        assert REGISTRY.get_sample_value("api_call_latency_seconds_count", labels) == 2.0

    def test_histogram_model_label_cardinality_cap(self):
        from prometheus_metrics import REGISTRY, observe_tps

        for idx in range(51):
            observe_tps(10.0, f"model-{idx}")

        assert REGISTRY.get_sample_value("tps_distribution_count", {"model": "model-49"}) == 1.0
        assert REGISTRY.get_sample_value("tps_distribution_count", {"model": "model-50"}) is None


# ---------------------------------------------------------------------------
# TestUpdateMetrics — gauge.set and counter.inc correctness
# ---------------------------------------------------------------------------

class _FakeState:
    """Minimal _SessionTPS stand-in for testing."""
    def __init__(self):
        self.last_call_tps = 42.5
        self.avg_tps = 40.0
        self.peak_tps = 45.0
        self.call_count = 2
        self.last_call_output_tokens = 100
        self.last_call_input_tokens = 50


class _FakeModelState:
    """Minimal _ModelTPS stand-in."""
    def __init__(self, avg=30.0, peak=35.0):
        self.avg_tps = avg
        self.peak_tps = peak
        self.call_count = 1
        self.total_output_tokens = 100


class _FakeProviderState:
    """Minimal _ProviderTPS stand-in."""
    def __init__(self, avg=25.0, peak=28.0):
        self.avg_tps = avg
        self.peak_tps = peak
        self.call_count = 1
        self.total_output_tokens = 100


class TestUpdateMetrics:
    """Verify update_metrics correctly sets gauge and counter values."""

    def test_gauge_values_set(self):
        from prometheus_metrics import update_metrics, generate_metrics
        state = _FakeState()
        update_metrics("sess1", state)
        output = generate_metrics().decode()
        assert "tps_last_call" in output
        assert "42.5" in output
        assert "tps_avg" in output
        assert "40.0" in output
        assert "tps_peak" in output
        assert "45.0" in output

    def test_counter_increments(self):
        from prometheus_metrics import update_metrics, generate_metrics
        state = _FakeState()
        update_metrics("sess2", state)
        output = generate_metrics().decode()
        assert "tps_api_calls_total" in output
        assert "tps_tokens_total" in output
        assert 'direction="output"' in output
        assert 'direction="input"' in output

    def test_multiple_calls_accumulate_counters(self):
        from prometheus_metrics import update_metrics, generate_metrics
        state = _FakeState()
        update_metrics("sess3", state)
        update_metrics("sess3", state)
        output = generate_metrics().decode()
        # After 2 calls, api_calls_total should be 2
        assert "2.0" in output

    def test_per_model_metrics(self):
        from prometheus_metrics import update_metrics, generate_metrics
        state = _FakeState()
        models = {"openai/gpt-4o": _FakeModelState(avg=33.0, peak=38.0)}
        update_metrics("sess4", state, models=models)
        output = generate_metrics().decode()
        assert 'model="openai/gpt-4o"' in output
        assert "33.0" in output
        assert "38.0" in output

    def test_per_provider_metrics(self):
        from prometheus_metrics import update_metrics, generate_metrics
        state = _FakeState()
        providers = {"openai": _FakeProviderState(avg=22.0, peak=26.0)}
        update_metrics("sess5", state, providers=providers)
        output = generate_metrics().decode()
        assert 'provider="openai"' in output
        assert "22.0" in output
        assert "26.0" in output


# ---------------------------------------------------------------------------
# TestGenerateMetrics — output format
# ---------------------------------------------------------------------------

class TestGenerateMetrics:

    def test_returns_bytes(self):
        from prometheus_metrics import generate_metrics
        result = generate_metrics()
        assert isinstance(result, bytes)

    def test_contains_help_and_type(self):
        from prometheus_metrics import update_metrics, generate_metrics
        state = _FakeState()
        update_metrics("fmt_test", state)
        output = generate_metrics().decode()
        assert "# HELP" in output
        assert "# TYPE" in output

    def test_content_type_compatible_format(self):
        """Verify the output uses Prometheus text exposition format v0.0.4."""
        from prometheus_metrics import update_metrics, generate_metrics
        state = _FakeState()
        update_metrics("fmt2", state)
        output = generate_metrics().decode()
        # HELP and TYPE lines should precede metric samples
        lines = output.strip().split("\n")
        help_lines = [l for l in lines if l.startswith("# HELP")]
        type_lines = [l for l in lines if l.startswith("# TYPE")]
        assert len(help_lines) > 0
        assert len(type_lines) > 0


# ---------------------------------------------------------------------------
# TestMetricsEndpoint — /metrics on FastAPI
# ---------------------------------------------------------------------------

class TestMetricsEndpoint:

    def test_metrics_returns_200(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_content_type(self, client):
        resp = client.get("/metrics")
        assert "text/plain" in resp.headers["content-type"]
        assert "version=0.0.4" in resp.headers["content-type"]

    def test_metrics_body_contains_help(self, client):
        resp = client.get("/metrics")
        assert b"# HELP" in resp.content or resp.content == b""

    def test_health_still_works(self, client):
        """Verify /api/v1/health coexists with /metrics on same app."""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# TestGracefulDegradation — works when prometheus_client unavailable
# ---------------------------------------------------------------------------

class TestGracefulDegradation:

    def test_no_prometheus_module_still_works(self):
        """If prometheus_client is missing, metrics_available returns False."""
        import prometheus_metrics as pm
        old = pm._PROMETHEUS_AVAILABLE
        pm._PROMETHEUS_AVAILABLE = False
        try:
            assert pm.metrics_available() is False
            assert pm.generate_metrics() == b""
            # update_metrics/observe helpers should be no-ops
            state = _FakeState()
            pm.update_metrics("degraded", state)  # should not raise
            pm.observe_tps(10.0, "model")  # should not raise
            pm.observe_latency(1.0, "model")  # should not raise
        finally:
            pm._PROMETHEUS_AVAILABLE = old


# ---------------------------------------------------------------------------
# TestThreadSafety — concurrent update_metrics calls
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_updates_no_crash(self):
        """4 threads updating metrics concurrently should not corrupt state."""
        import threading
        from prometheus_metrics import update_metrics, generate_metrics

        state = _FakeState()
        errors = []

        def worker(sid):
            try:
                for _ in range(10):
                    update_metrics(sid, state)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(f"ts_{i}",)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        output = generate_metrics().decode()
        # All 4 session IDs should appear
        for i in range(4):
            assert f'ts_{i}' in output or f"ts_{i}" in output


# ---------------------------------------------------------------------------
# TestConfigIntegration — prometheus.enabled config path
# ---------------------------------------------------------------------------

class TestConfigIntegration:

    def test_prometheus_disabled_by_default(self):
        """Without prometheus.enabled in config, _prometheus_enabled stays False."""
        import __init__ as plugin
        # Default state should be False
        assert plugin._prometheus_enabled is False

    def test_register_enables_prometheus(self):
        """When config has prometheus.enabled=True, flag gets set."""
        import __init__ as plugin

        class _FakeCtx:
            def register_hook(self, name, fn):
                pass
            def get_config(self, name, default=None):
                return {"prometheus": {"enabled": True}}

        old = plugin._prometheus_enabled
        plugin._prometheus_enabled = False
        try:
            plugin.register(_FakeCtx())
            assert plugin._prometheus_enabled is True
        finally:
            plugin._prometheus_enabled = old

    def test_register_without_prometheus_config(self):
        """When config has no prometheus key, flag stays False."""
        import __init__ as plugin

        class _FakeCtx:
            def register_hook(self, name, fn):
                pass
            def get_config(self, name, default=None):
                return {}

        old = plugin._prometheus_enabled
        plugin._prometheus_enabled = False
        try:
            plugin.register(_FakeCtx())
            assert plugin._prometheus_enabled is False
        finally:
            plugin._prometheus_enabled = old


# ---------------------------------------------------------------------------
# TestHookIntegration — metrics updated after simulated hook calls
# ---------------------------------------------------------------------------

class TestHookIntegration:

    def test_hook_updates_metrics_when_enabled(self, _enable_prometheus):
        """Simulate 2 hook calls and verify Prometheus metrics reflect them."""
        import __init__ as plugin
        from prometheus_metrics import generate_metrics

        # Clear state
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
            plugin._MODELS.clear()
            plugin._PROVIDERS.clear()

        # Simulate 2 API calls
        plugin._on_post_api_request(
            session_id="hook_sess",
            usage={"output_tokens": 200, "input_tokens": 100},
            api_duration=2.0,
            model="openai/gpt-4o",
        )
        plugin._on_post_api_request(
            session_id="hook_sess",
            usage={"output_tokens": 300, "input_tokens": 150},
            api_duration=3.0,
            model="openai/gpt-4o",
        )

        output = generate_metrics().decode()
        # Session gauges should be set
        assert "tps_last_call" in output
        assert "tps_avg" in output
        assert "tps_peak" in output
        # Per-model metrics should appear
        assert 'model="openai/gpt-4o"' in output
        # Per-provider metrics should appear
        assert 'provider="openai"' in output
        # Token counters should have values > 0
        assert "tps_tokens_total" in output

    def test_hook_no_metrics_when_disabled(self):
        """When _prometheus_enabled is False, hook should not update metrics."""
        import __init__ as plugin
        from prometheus_metrics import generate_metrics, reset_metrics

        reset_metrics()

        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
            plugin._MODELS.clear()
            plugin._PROVIDERS.clear()

        old = plugin._prometheus_enabled
        plugin._prometheus_enabled = False
        try:
            plugin._on_post_api_request(
                session_id="disabled_sess",
                usage={"output_tokens": 100, "input_tokens": 50},
                api_duration=1.0,
                model="openai/gpt-4o",
            )
            output = generate_metrics().decode()
            # Should NOT contain session-specific data
            assert "disabled_sess" not in output
        finally:
            plugin._prometheus_enabled = old


# ---------------------------------------------------------------------------
# TestHealthMetricDefinitions — new health metrics registered in REGISTRY
# ---------------------------------------------------------------------------

class TestHealthMetricDefinitions:
    """Verify all 6 new health metrics are registered in the custom registry."""

    def test_health_counters_registered(self):
        from prometheus_metrics import REGISTRY
        names = {m.name for m in REGISTRY.collect()}
        # prometheus_client strips _total suffix from collected counter names
        assert "usage_extraction_failures" in names
        assert "db_write_errors" in names
        assert "db_read_errors" in names
        assert "ws_broadcast_failures" in names
        assert "ws_dead_clients" in names

    def test_ws_active_connections_gauge_registered(self):
        from prometheus_metrics import REGISTRY
        names = {m.name for m in REGISTRY.collect()}
        assert "ws_active_connections" in names

    def test_all_six_metrics_in_generate_output(self):
        """All 6 new metrics appear in generate_metrics() output with HELP/TYPE."""
        from prometheus_metrics import generate_metrics
        output = generate_metrics().decode()
        for name in [
            "usage_extraction_failures_total",
            "db_write_errors_total",
            "db_read_errors_total",
            "ws_broadcast_failures_total",
            "ws_dead_clients_total",
            "ws_active_connections",
        ]:
            assert name in output, f"{name} missing from /metrics output"
            # HELP and TYPE lines should be present for each
            assert f"# HELP {name}" in output, f"# HELP {name} missing"
            assert f"# TYPE {name}" in output, f"# TYPE {name} missing"


# ---------------------------------------------------------------------------
# TestHealthMetricIncrements — counter/gauge increment behavior
# ---------------------------------------------------------------------------

class TestHealthMetricIncrements:
    """Verify each increment/set function correctly updates its metric."""

    def test_usage_extraction_failure_increments(self):
        from prometheus_metrics import (
            increment_usage_extraction_failure, generate_metrics,
        )
        increment_usage_extraction_failure()
        output = generate_metrics().decode()
        assert "usage_extraction_failures_total 1.0" in output

    def test_db_write_error_increments(self):
        from prometheus_metrics import (
            increment_db_write_error, generate_metrics,
        )
        increment_db_write_error()
        output = generate_metrics().decode()
        assert "db_write_errors_total 1.0" in output

    def test_db_read_error_increments(self):
        from prometheus_metrics import (
            increment_db_read_error, generate_metrics,
        )
        increment_db_read_error()
        output = generate_metrics().decode()
        assert "db_read_errors_total 1.0" in output

    def test_ws_broadcast_failure_increments(self):
        from prometheus_metrics import (
            increment_ws_broadcast_failure, generate_metrics,
        )
        increment_ws_broadcast_failure()
        output = generate_metrics().decode()
        assert "ws_broadcast_failures_total 1.0" in output

    def test_ws_dead_client_increments(self):
        from prometheus_metrics import (
            increment_ws_dead_client, generate_metrics,
        )
        increment_ws_dead_client()
        output = generate_metrics().decode()
        assert "ws_dead_clients_total 1.0" in output

    def test_ws_active_connections_set(self):
        from prometheus_metrics import (
            set_ws_active_connections, generate_metrics,
        )
        set_ws_active_connections(5)
        output = generate_metrics().decode()
        assert "ws_active_connections 5.0" in output

    def test_multiple_increments_accumulate(self):
        """Counters should accumulate across multiple calls."""
        from prometheus_metrics import (
            increment_db_write_error, generate_metrics,
        )
        increment_db_write_error()
        increment_db_write_error()
        increment_db_write_error()
        output = generate_metrics().decode()
        assert "db_write_errors_total 3.0" in output

    def test_gauge_overwrites_on_set(self):
        """Gauge should reflect the latest set() value, not accumulate."""
        from prometheus_metrics import (
            set_ws_active_connections, generate_metrics,
        )
        set_ws_active_connections(10)
        set_ws_active_connections(3)
        output = generate_metrics().decode()
        assert "ws_active_connections 3.0" in output


# ---------------------------------------------------------------------------
# TestHealthMetricDegradation — no-ops when prometheus_client unavailable
# ---------------------------------------------------------------------------

class TestHealthMetricDegradation:
    """Verify all increment/set functions are safe no-ops when prometheus_client absent."""

    def test_increment_functions_noop_without_prometheus(self):
        import prometheus_metrics as pm
        old = pm._PROMETHEUS_AVAILABLE
        pm._PROMETHEUS_AVAILABLE = False
        try:
            # None of these should raise
            pm.increment_usage_extraction_failure()
            pm.increment_db_write_error()
            pm.increment_db_read_error()
            pm.increment_ws_broadcast_failure()
            pm.increment_ws_dead_client()
            pm.set_ws_active_connections(0)
        finally:
            pm._PROMETHEUS_AVAILABLE = old
