"""Tests for public API: get_tps_stats and register."""
from unittest.mock import MagicMock

import pytest

from __init__ import get_tps_stats, register, _get_session, _SESSIONS, _STATE_LOCK


# ---------------------------------------------------------------------------
# Health diagnostics endpoint
# ---------------------------------------------------------------------------

class TestHealthDiagnosticsEndpoint:

    def test_diagnostics_returns_200_with_all_components(self, client):
        """Diagnostics endpoint returns 200 with all 5 component sections."""
        resp = client.get("/api/v1/health/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "components" in data
        assert "timestamp" in data
        components = data["components"]
        for name in ("memory", "sqlite", "prometheus", "websocket", "health_counters"):
            assert name in components, f"Missing component: {name}"
            assert "status" in components[name], f"Missing status in {name}"

    def test_component_statuses_are_valid(self, client):
        """Each component has a valid status value."""
        resp = client.get("/api/v1/health/diagnostics")
        data = resp.json()
        valid_statuses = {"ok", "degraded", "unavailable"}
        for name, comp in data["components"].items():
            assert comp["status"] in valid_statuses, \
                f"Component {name} has invalid status: {comp['status']}"

    def test_memory_component_reports_fields(self, client):
        """Memory component reports session count, max_sessions, models, providers."""
        resp = client.get("/api/v1/health/diagnostics")
        data = resp.json()
        memory = data["components"]["memory"]
        assert "sessions" in memory
        assert "max_sessions" in memory
        assert "models" in memory
        assert "providers" in memory
        assert isinstance(memory["sessions"], int)
        assert isinstance(memory["max_sessions"], int)

    def test_sqlite_component_reports_fields(self, client, store):
        """SQLite component reports connected, session_count, event_count."""
        resp = client.get("/api/v1/health/diagnostics")
        data = resp.json()
        sqlite = data["components"]["sqlite"]
        assert sqlite["status"] == "ok"
        assert sqlite["connected"] is True
        assert "session_count" in sqlite
        assert "event_count" in sqlite
        assert "retention_days" in sqlite

    def test_prometheus_component_reports_fields(self, client):
        """Prometheus component reports enabled/available status."""
        resp = client.get("/api/v1/health/diagnostics")
        data = resp.json()
        prom = data["components"]["prometheus"]
        assert "enabled" in prom
        assert "available" in prom
        assert "registered_collectors" in prom

    def test_websocket_component_reports_fields(self, client):
        """WebSocket component reports active_connections count."""
        resp = client.get("/api/v1/health/diagnostics")
        data = resp.json()
        ws = data["components"]["websocket"]
        assert "enabled" in ws
        assert "active_connections" in ws
        assert isinstance(ws["active_connections"], int)

    def test_health_counters_component_reports_fields(self, client):
        """Health counters component reports all 5 counter values."""
        resp = client.get("/api/v1/health/diagnostics")
        data = resp.json()
        hc = data["components"]["health_counters"]
        for counter_name in ("usage_extraction_failures", "db_write_errors",
                             "db_read_errors", "ws_broadcast_failures",
                             "ws_dead_clients"):
            assert counter_name in hc, f"Missing counter: {counter_name}"
            assert isinstance(hc[counter_name], int)

    def test_graceful_degradation_broken_store(self):
        """Broken store returns sqlite.status=unavailable, overall 200."""
        from api import create_app
        from fastapi.testclient import TestClient

        # Create a mock store that raises on count()
        class BrokenStore:
            _retention_days = 7
            _lock = __import__("threading").Lock()
            _conn = None
            def count(self):
                raise RuntimeError("DB corrupted")
            def load_all(self):
                raise RuntimeError("DB corrupted")

        app = create_app(BrokenStore())
        c = TestClient(app)
        resp = c.get("/api/v1/health/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["components"]["sqlite"]["status"] in ("degraded", "unavailable")

    def test_graceful_degradation_no_callback(self, store):
        """No get_diagnostics callback returns memory.status=unavailable."""
        from api import create_app
        from fastapi.testclient import TestClient

        app = create_app(store, get_diagnostics=None)
        c = TestClient(app)
        resp = c.get("/api/v1/health/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["components"]["memory"]["status"] == "unavailable"

    def test_graceful_degradation_callback_raises(self, store):
        """Callback that raises returns memory.status=degraded."""
        from api import create_app
        from fastapi.testclient import TestClient

        def bad_callback():
            raise RuntimeError("state corrupted")

        app = create_app(store, get_diagnostics=bad_callback)
        c = TestClient(app)
        resp = c.get("/api/v1/health/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["components"]["memory"]["status"] == "degraded"

    def test_existing_health_endpoint_unchanged(self, client):
        """Existing /api/v1/health endpoint is backward compatible."""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["db"] == "connected"

    def test_overall_status_ok_when_all_ok(self, store):
        """Overall status is 'ok' when all components are ok."""
        from api import create_app
        from fastapi.testclient import TestClient

        def good_callback():
            return {"sessions": [], "models": {}, "providers": {}, "max_sessions": 50}

        app = create_app(store, get_diagnostics=good_callback)
        c = TestClient(app)
        resp = c.get("/api/v1/health/diagnostics")
        data = resp.json()
        # All components should be ok (store is connected, callback works, prometheus/ws available)
        assert data["status"] == "ok"

    def test_overall_status_degraded_when_component_degraded(self, store):
        """Overall status is 'degraded' when any component is degraded."""
        from api import create_app
        from fastapi.testclient import TestClient

        def bad_callback():
            raise RuntimeError("partial failure")

        app = create_app(store, get_diagnostics=bad_callback)
        c = TestClient(app)
        resp = c.get("/api/v1/health/diagnostics")
        data = resp.json()
        # memory will be degraded
        assert data["components"]["memory"]["status"] == "degraded"
        assert data["status"] == "degraded"

    def test_diagnostics_with_callback_data(self, store):
        """Diagnostics endpoint reflects callback data correctly."""
        from api import create_app
        from fastapi.testclient import TestClient

        def mock_callback():
            return {
                "sessions": ["s1", "s2", "s3"],
                "models": {"s1": ["gpt-4o"], "s2": ["claude-sonnet", "gpt-4o"]},
                "providers": {"s1": ["openai"], "s2": ["anthropic", "openai"]},
                "max_sessions": 100,
            }

        app = create_app(store, get_diagnostics=mock_callback)
        c = TestClient(app)
        resp = c.get("/api/v1/health/diagnostics")
        data = resp.json()
        memory = data["components"]["memory"]
        assert memory["status"] == "ok"
        assert memory["sessions"] == 3
        assert memory["max_sessions"] == 100
        assert memory["models"] == 2
        assert memory["providers"] == 2


# ---------------------------------------------------------------------------
# Historical Export endpoint
# ---------------------------------------------------------------------------


class TestExportHistoryEndpoint:

    def test_register_hook_name(self):
        ctx = MagicMock()
        register(ctx)
        args = ctx.register_hook.call_args
        assert args[0][0] == "post_api_request"
