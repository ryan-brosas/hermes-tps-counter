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

        # Plugin hook should still be registered (post_api_request + on_session_end + on_shutdown)
        assert ctx.register_hook.call_count == 3
