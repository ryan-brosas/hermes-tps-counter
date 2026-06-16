"""Tests for the FastAPI REST API endpoints (api.py)."""
from __future__ import annotations

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

# Ensure the plugin root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def mock_hermes_cli():
    """Mock hermes_cli for plugin import compatibility."""
    import types
    mod = types.ModuleType("hermes_cli")
    mod._ACTIVE_CLI_INSTANCE = None
    with patch.dict(sys.modules, {"hermes_cli": mod}):
        yield


@pytest.fixture
def store():
    """Create a temporary PersistentSessionStore for testing."""
    from store import PersistentSessionStore
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = PersistentSessionStore(path)
    yield s
    s.close()
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def app(store):
    """Create a FastAPI test app backed by the temp store."""
    from api import create_app
    return create_app(store)


@pytest.fixture
def client(app):
    """Create a TestClient for the FastAPI app."""
    from fastapi.testclient import TestClient
    return TestClient(app)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    def test_health_returns_ok(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["db"] == "connected"

    def test_health_with_none_store(self):
        """Health endpoint handles a None store gracefully."""
        from api import create_app
        from fastapi.testclient import TestClient
        app = create_app(None)
        c = TestClient(app)
        resp = c.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["db"] == "disconnected"


# ---------------------------------------------------------------------------
# Session TPS endpoint
# ---------------------------------------------------------------------------

class TestSessionTPSEndpoint:

    def test_session_not_found(self, client):
        resp = client.get("/api/v1/sessions/nonexistent/tps")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_session_returns_saved_data(self, client, store):
        # Save some test data
        state = {
            "call_count": 5,
            "total_output_tokens": 500,
            "total_input_tokens": 200,
            "total_duration": 10.0,
            "peak_tps": 80.0,
            "last_call_tps": 60.0,
            "avg_tps": 50.0,
        }
        store.save("test-session-1", state)

        resp = client.get("/api/v1/sessions/test-session-1/tps")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "test-session-1"
        assert data["call_count"] == 5
        assert data["total_output_tokens"] == 500
        assert data["total_input_tokens"] == 200
        assert data["peak_tps"] == 80.0
        assert data["last_call_tps"] == 60.0
        assert data["avg_tps"] == 50.0
        assert "updated_at" in data


# ---------------------------------------------------------------------------
# All sessions endpoint
# ---------------------------------------------------------------------------

class TestAllSessionsEndpoint:

    def test_empty_db_returns_empty_list(self, client):
        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []

    def test_returns_all_sessions(self, client, store):
        store.save("s1", {"call_count": 1, "total_output_tokens": 100,
                           "total_input_tokens": 50, "total_duration": 2.0,
                           "peak_tps": 50.0, "last_call_tps": 50.0, "avg_tps": 50.0})
        store.save("s2", {"call_count": 3, "total_output_tokens": 300,
                           "total_input_tokens": 150, "total_duration": 6.0,
                           "peak_tps": 60.0, "last_call_tps": 55.0, "avg_tps": 50.0})

        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sessions"]) == 2
        ids = {s["session_id"] for s in data["sessions"]}
        assert ids == {"s1", "s2"}


# ---------------------------------------------------------------------------
# Batch session TPS endpoint
# ---------------------------------------------------------------------------

class TestBatchSessionTPSEndpoint:

    def test_returns_multiple_existing_sessions(self, client, store):
        store.save("s1", {"call_count": 1, "total_output_tokens": 100,
                           "total_input_tokens": 50, "total_duration": 2.0,
                           "peak_tps": 50.0, "last_call_tps": 50.0, "avg_tps": 50.0})
        store.save("s2", {"call_count": 3, "total_output_tokens": 300,
                           "total_input_tokens": 150, "total_duration": 6.0,
                           "peak_tps": 60.0, "last_call_tps": 55.0, "avg_tps": 50.0})

        resp = client.post("/api/v1/sessions/batch/tps", json={"session_ids": ["s1", "s2"]})

        assert resp.status_code == 200
        data = resp.json()
        assert [s["session_id"] for s in data["sessions"]] == ["s1", "s2"]
        assert data["missing_session_ids"] == []
        assert data["sessions"][0]["call_count"] == 1
        assert data["sessions"][1]["total_output_tokens"] == 300

    def test_partial_miss_returns_found_and_missing(self, client, store):
        store.save("s1", {"call_count": 1, "total_output_tokens": 100,
                           "total_input_tokens": 50, "total_duration": 2.0,
                           "peak_tps": 50.0, "last_call_tps": 50.0, "avg_tps": 50.0})

        resp = client.post(
            "/api/v1/sessions/batch/tps",
            json={"session_ids": ["missing-1", "s1", "missing-2"]},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert [s["session_id"] for s in data["sessions"]] == ["s1"]
        assert data["missing_session_ids"] == ["missing-1", "missing-2"]

    def test_all_miss_returns_empty_sessions_and_all_missing(self, client):
        resp = client.post(
            "/api/v1/sessions/batch/tps",
            json={"session_ids": ["missing-1", "missing-2"]},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []
        assert data["missing_session_ids"] == ["missing-1", "missing-2"]

    def test_duplicate_ids_are_deduplicated_with_first_seen_order(self, client, store):
        store.save("s1", {"call_count": 1, "total_output_tokens": 100,
                           "total_input_tokens": 50, "total_duration": 2.0,
                           "peak_tps": 50.0, "last_call_tps": 50.0, "avg_tps": 50.0})
        store.save("s2", {"call_count": 2, "total_output_tokens": 200,
                           "total_input_tokens": 80, "total_duration": 4.0,
                           "peak_tps": 55.0, "last_call_tps": 45.0, "avg_tps": 50.0})

        resp = client.post(
            "/api/v1/sessions/batch/tps",
            json={"session_ids": ["s2", "s1", "s2", "missing", "s1", "missing"]},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert [s["session_id"] for s in data["sessions"]] == ["s2", "s1"]
        assert data["missing_session_ids"] == ["missing"]

    def test_empty_input_returns_422(self, client):
        resp = client.post("/api/v1/sessions/batch/tps", json={"session_ids": []})
        assert resp.status_code == 422

    def test_non_list_input_returns_422(self, client):
        resp = client.post(
            "/api/v1/sessions/batch/tps",
            json={"session_ids": "not-a-list"},
        )
        assert resp.status_code == 422

    def test_store_none_returns_503(self):
        from api import create_app
        from fastapi.testclient import TestClient
        app = create_app(None)
        c = TestClient(app)

        resp = c.post("/api/v1/sessions/batch/tps", json={"session_ids": ["s1"]})

        assert resp.status_code == 503
        assert resp.json()["detail"] == "Database not available"


# ---------------------------------------------------------------------------
# Summary endpoint
# ---------------------------------------------------------------------------

class TestSummaryEndpoint:

    def test_empty_db_returns_zeros(self, client):
        resp = client.get("/api/v1/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] == 0
        assert data["total_calls"] == 0
        assert data["total_tokens"] == 0
        assert data["average_tps"] == 0.0

    def test_summary_aggregates_correctly(self, client, store):
        store.save("s1", {"call_count": 2, "total_output_tokens": 200,
                           "total_input_tokens": 100, "total_duration": 4.0,
                           "peak_tps": 60.0, "last_call_tps": 50.0, "avg_tps": 50.0})
        store.save("s2", {"call_count": 3, "total_output_tokens": 300,
                           "total_input_tokens": 150, "total_duration": 6.0,
                           "peak_tps": 70.0, "last_call_tps": 55.0, "avg_tps": 50.0})

        resp = client.get("/api/v1/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] == 2
        assert data["total_calls"] == 5
        assert data["total_tokens"] == 750  # (200+100) + (300+150)
        # avg_tps = total_output / total_duration = 500 / 10.0 = 50.0
        assert data["average_tps"] == 50.0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:

    def test_session_tps_503_when_store_none(self):
        """Session TPS returns 503 when store is None."""
        from api import create_app
        from fastapi.testclient import TestClient
        app = create_app(None)
        c = TestClient(app)
        resp = c.get("/api/v1/sessions/any/tps")
        assert resp.status_code == 503

    def test_all_sessions_503_when_store_none(self):
        """All sessions returns 503 when store is None."""
        from api import create_app
        from fastapi.testclient import TestClient
        app = create_app(None)
        c = TestClient(app)
        resp = c.get("/api/v1/sessions")
        assert resp.status_code == 503

    def test_summary_503_when_store_none(self):
        """Summary returns 503 when store is None."""
        from api import create_app
        from fastapi.testclient import TestClient
        app = create_app(None)
        c = TestClient(app)
        resp = c.get("/api/v1/summary")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Integration tests: register() with API config
# ---------------------------------------------------------------------------

class TestRegisterIntegration:

    def test_register_without_api_config_does_not_start_server(self, store):
        """register() without api.enabled does NOT start uvicorn."""
        from unittest.mock import MagicMock
        ctx = MagicMock()
        ctx.get_config.return_value = {"db_path": store._db_path}

        with patch.dict("os.environ", {}, clear=False):
            # register should succeed without starting API
            import importlib
            import __init__ as tps_mod
            tps_mod._STORE = None
            tps_mod.register(ctx)

        # Should not have started any server thread
        assert tps_mod._STORE is not None

    def test_register_with_api_enabled_starts_server(self, store):
        """register() with api.enabled=True starts uvicorn in a daemon thread."""
        import threading
        from unittest.mock import MagicMock, patch as _patch

        ctx = MagicMock()
        ctx.get_config.return_value = {
            "db_path": store._db_path,
            "api": {"enabled": True, "host": "127.0.0.1", "port": 19127},
        }

        import __init__ as tps_mod
        tps_mod._STORE = None

        # Patch threading.Thread to capture the server.run call
        started = []
        real_thread = threading.Thread

        class FakeThread:
            def __init__(self, target=None, daemon=False, name=""):
                self._target = target
                self._daemon = daemon
                self._name = name
            def start(self):
                started.append(self._target)

        with _patch("threading.Thread", FakeThread):
            tps_mod.register(ctx)

        # Should have created a server thread
        assert len(started) == 1
        # _API_SERVER should be set
        assert tps_mod._API_SERVER is not None

    def test_graceful_import_failure(self):
        """Plugin still works when fastapi/uvicorn are not installed."""
        from unittest.mock import MagicMock

        ctx = MagicMock()
        ctx.get_config.return_value = {
            "api": {"enabled": True, "host": "127.0.0.1", "port": 19127},
        }

        import __init__ as tps_mod
        tps_mod._STORE = None

        # Simulate fastapi not installed
        with patch.dict(sys.modules, {"fastapi": None, "uvicorn": None}):
            # Should not raise — just logs a warning
            tps_mod.register(ctx)

        # Plugin hook should still be registered (post_api_request + on_session_end)
        assert ctx.register_hook.call_count == 2


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

    def test_export_history_returns_200_with_json(self, client, store):
        """Basic JSON export with seeded data."""
        store.save("s1", {"call_count": 5, "total_output_tokens": 500,
                          "total_input_tokens": 200, "total_duration": 10.0,
                          "peak_tps": 80.0, "last_call_tps": 60.0, "avg_tps": 50.0})
        store.record_event("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0)

        resp = client.get("/api/v1/export/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "metadata" in data
        assert "sessions" in data
        assert "events" in data
        assert len(data["sessions"]) == 1
        assert len(data["events"]) == 1
        assert data["sessions"][0]["session_id"] == "s1"
        assert data["events"][0]["session_id"] == "s1"

    def test_export_history_503_when_store_none(self):
        """Store unavailable returns 503."""
        from api import create_app
        from fastapi.testclient import TestClient
        app = create_app(None)
        c = TestClient(app)
        resp = c.get("/api/v1/export/history")
        assert resp.status_code == 503

    def test_export_history_with_session_id_filter(self, client, store):
        """Filters to specific session."""
        store.save("s1", {"call_count": 1, "total_output_tokens": 100,
                          "total_input_tokens": 50, "total_duration": 2.0,
                          "peak_tps": 50.0, "last_call_tps": 50.0, "avg_tps": 50.0})
        store.save("s2", {"call_count": 3, "total_output_tokens": 300,
                          "total_input_tokens": 150, "total_duration": 6.0,
                          "peak_tps": 60.0, "last_call_tps": 55.0, "avg_tps": 50.0})
        store.record_event("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0)
        store.record_event("s2", "claude", "anthropic", 50, 100, 1.0, 100.0)

        resp = client.get("/api/v1/export/history?session_id=s1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["session_id"] == "s1"
        assert all(e["session_id"] == "s1" for e in data["events"])

    def test_export_history_with_time_bounds(self, client, store):
        """since/until filters work."""
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        old = (now - timedelta(hours=2)).isoformat()
        recent = (now - timedelta(minutes=5)).isoformat()

        with store._lock:
            store._conn.execute(
                "INSERT INTO call_events (session_id, model, provider, input_tokens, output_tokens, duration, tps, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("s1", "m1", "p1", 10, 20, 1.0, 20.0, old),
            )
            store._conn.execute(
                "INSERT INTO call_events (session_id, model, provider, input_tokens, output_tokens, duration, tps, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("s1", "m1", "p1", 30, 40, 2.0, 20.0, recent),
            )
            store._conn.commit()

        since = (now - timedelta(hours=1)).isoformat()
        resp = client.get(f"/api/v1/export/history?since={since}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["output_tokens"] == 40

    def test_export_history_respects_limit(self, client, store):
        """Limit parameter caps results."""
        for i in range(10):
            store.record_event("s1", "m1", "p1", i * 10, i * 20, 1.0, float(i * 20))

        resp = client.get("/api/v1/export/history?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 5

    def test_export_history_rejects_invalid_limit(self, client):
        """limit <= 0 returns 422."""
        resp = client.get("/api/v1/export/history?limit=0")
        assert resp.status_code == 422

        resp = client.get("/api/v1/export/history?limit=-1")
        assert resp.status_code == 422

    def test_export_history_rejects_excessive_limit(self, client):
        """limit > max_limit returns 422."""
        resp = client.get("/api/v1/export/history?limit=2000")
        assert resp.status_code == 422

    def test_export_history_rejects_unsupported_format(self, client):
        """format=xml returns 400."""
        resp = client.get("/api/v1/export/history?format=xml")
        assert resp.status_code == 400

    def test_export_history_empty_result(self, client):
        """No matching data returns 200 with empty arrays."""
        resp = client.get("/api/v1/export/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []
        assert data["events"] == []
        assert data["metadata"]["session_count"] == 0
        assert data["metadata"]["event_count"] == 0

    def test_export_history_csv_format(self, client, store):
        """format=csv returns text/csv with correct columns."""
        store.record_event("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0)

        resp = client.get("/api/v1/export/history?format=csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        lines = resp.text.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row
        header = lines[0]
        assert "session_id" in header
        assert "model" in header

    def test_export_history_metadata_fields(self, client, store):
        """Response contains generated_at, filters, counts."""
        store.save("s1", {"call_count": 1, "total_output_tokens": 100,
                          "total_input_tokens": 50, "total_duration": 2.0,
                          "peak_tps": 50.0, "last_call_tps": 50.0, "avg_tps": 50.0})
        store.record_event("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0)

        resp = client.get("/api/v1/export/history")
        data = resp.json()
        meta = data["metadata"]
        assert "generated_at" in meta
        assert meta["session_count"] == 1
        assert meta["event_count"] == 1
        assert meta["format"] == "json"
        assert "limit" in meta["filters"]

    def test_existing_endpoints_not_regressed(self, client, store):
        """Existing endpoints still work after export endpoint is added."""
        # Health
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        # Sessions
        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 200
        # Summary
        resp = client.get("/api/v1/summary")
        assert resp.status_code == 200
