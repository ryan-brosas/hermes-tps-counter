"""Tests for the built-in TPS dashboard route."""
from __future__ import annotations

import os
import re
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
    setattr(mod, "_ACTIVE_CLI_INSTANCE", None)
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
def client(store):
    """Create a TestClient for the dashboard-enabled app."""
    from api import create_app
    from fastapi.testclient import TestClient
    return TestClient(create_app(store))


def test_root_serves_dashboard_html(client):
    resp = client.get("/")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "TPS Dashboard" in resp.text
    assert "/ws/tps" in resp.text
    assert "/api/v1/summary" in resp.text
    assert "/api/v1/sessions" in resp.text
    assert "/api/v1/health/diagnostics" in resp.text


def test_dashboard_has_no_external_asset_dependencies(client):
    html = client.get("/").text
    script_srcs = re.findall(r"<script[^>]+src=[\"']([^\"']+)", html, flags=re.I)
    link_hrefs = re.findall(r"<link[^>]+href=[\"']([^\"']+)", html, flags=re.I)

    assert script_srcs == []
    assert link_hrefs == []
    assert "cdn." not in html.lower()
    assert "fonts.googleapis.com" not in html.lower()
    assert "fonts.gstatic.com" not in html.lower()
    assert "https://" not in html
    assert "http://" not in html


def test_dashboard_reuses_existing_live_and_rest_channels(client):
    html = client.get("/").text

    assert "new WebSocket(url)" in html
    assert "'/ws/tps'" in html
    assert "fetchJson('/api/v1/summary')" in html
    assert "fetchJson('/api/v1/sessions')" in html
    assert "fetchJson('/api/v1/health')" in html
    assert "fetchJson('/api/v1/health/diagnostics')" in html


def test_dashboard_contains_reconnect_and_rest_polling_fallback_hooks(client):
    html = client.get("/").text

    assert "scheduleReconnect" in html
    assert "backoff" in html
    assert "setTimeout(connectWebSocket, backoff)" in html
    assert "startPollingFallback" in html
    assert "setInterval(loadInitialState, 5000)" in html
    assert "Polling REST fallback" in html


def test_dashboard_does_not_shadow_existing_routes(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/summary").status_code == 200
    metrics = client.get("/metrics")
    assert metrics.status_code in {200, 503}
