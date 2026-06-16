"""Tests for the built-in TPS dashboard served at GET /."""
from __future__ import annotations

import os
import sys
import tempfile
from unittest.mock import patch

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
# Root dashboard route
# ---------------------------------------------------------------------------

class TestDashboardRoot:

    def test_root_returns_200_html(self, client):
        """GET / returns HTTP 200 with text/html content type."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_root_contains_dashboard_markers(self, client):
        """Response body contains expected dashboard content markers."""
        body = client.get("/").text
        assert "TPS Dashboard" in body
        assert "/ws/tps" in body
        assert "/api/v1/summary" in body
        assert "/api/v1/sessions" in body

    def test_root_contains_no_cdn_references(self, client):
        """Dashboard HTML contains zero external CDN or remote asset references."""
        body = client.get("/").text
        import re
        # No external script src
        external_scripts = re.findall(r'<script[^>]+src=["\']https?://', body)
        assert external_scripts == [], f"External scripts: {external_scripts}"
        # No external link href (stylesheets, fonts)
        external_links = re.findall(r'<link[^>]+href=["\']https?://', body)
        assert external_links == [], f"External links: {external_links}"
        # No CDN domain references
        assert "cdn." not in body.lower()
        assert "fonts.googleapis" not in body.lower()
        assert "cdnjs." not in body.lower()
        assert "unpkg.com" not in body.lower()
        assert "jsdelivr" not in body.lower()

    def test_root_contains_websocket_reconnect_logic(self, client):
        """Dashboard JavaScript includes WebSocket auto-reconnect with backoff."""
        body = client.get("/").text
        # Check for reconnect-related patterns
        assert "reconnect" in body.lower() or "reconnectDelay" in body
        # Check for backoff timer logic
        assert "setTimeout" in body or "setInterval" in body

    def test_root_contains_rest_fallback(self, client):
        """Dashboard JavaScript includes REST polling fallback."""
        body = client.get("/").text
        # Should have fetch calls to REST endpoints for fallback
        assert "fetch(" in body
        assert "summary" in body

    def test_root_contains_websocket_endpoint(self, client):
        """Dashboard JavaScript references the /ws/tps WebSocket endpoint."""
        body = client.get("/").text
        assert "/ws/tps" in body
        assert "WebSocket" in body

    def test_root_contains_health_endpoint(self, client):
        """Dashboard JavaScript references the health/diagnostics endpoint."""
        body = client.get("/").text
        assert "/api/v1/health/diagnostics" in body


# ---------------------------------------------------------------------------
# Route compatibility — existing routes not shadowed
# ---------------------------------------------------------------------------

class TestRouteCompatibility:

    def test_docs_still_available(self, client):
        """GET /docs still returns 200 after dashboard route is registered."""
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_health_still_available(self, client):
        """GET /api/v1/health still returns 200 after dashboard route."""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_summary_still_available(self, client):
        """GET /api/v1/summary still returns 200 after dashboard route."""
        resp = client.get("/api/v1/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sessions" in data

    def test_sessions_still_available(self, client):
        """GET /api/v1/sessions still returns 200 after dashboard route."""
        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 200

    def test_metrics_still_available(self, client):
        """GET /metrics still returns 200 or 503 (not 404) after dashboard route."""
        resp = client.get("/metrics")
        # 200 if prometheus_client installed, 503 if not — never 404
        assert resp.status_code in (200, 503)
