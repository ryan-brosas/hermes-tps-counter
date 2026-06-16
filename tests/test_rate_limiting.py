"""Tests for API per-IP rate limiting middleware."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def store():
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
def clock() -> FakeClock:
    return FakeClock()


def _client(store, clock: FakeClock, requests_per_minute: int = 2, burst_size: int = 1) -> TestClient:
    from api import create_app
    from config import TPSConfig

    app = create_app(
        store,
        config=TPSConfig(requests_per_minute=requests_per_minute, burst_size=burst_size),
        rate_limit_time_fn=clock.time,
    )
    return TestClient(app)


def test_under_limit_requests_preserve_endpoint_contracts(store, clock):
    client = _client(store, clock, requests_per_minute=2, burst_size=1)

    first = client.get("/api/v1/sessions")
    second = client.get("/api/v1/summary")

    assert first.status_code == 200
    assert first.json() == {"sessions": []}
    assert second.status_code == 200
    assert second.json()["total_sessions"] == 0


def test_throttled_request_returns_429_with_retry_after_and_json(store, clock):
    client = _client(store, clock, requests_per_minute=2, burst_size=1)

    for _ in range(3):
        assert client.get("/api/v1/sessions").status_code == 200

    resp = client.get("/api/v1/sessions")

    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "60"
    assert resp.json() == {"detail": "Rate limit exceeded", "retry_after": 60}


def test_throttled_request_does_not_invoke_protected_store_path(clock):
    store = MagicMock()
    store.load_all.return_value = {}
    client = _client(store, clock, requests_per_minute=1, burst_size=1)

    assert client.get("/api/v1/sessions").status_code == 200
    assert client.get("/api/v1/sessions").status_code == 200
    store.load_all.reset_mock()

    resp = client.get("/api/v1/sessions")

    assert resp.status_code == 429
    store.load_all.assert_not_called()


def test_health_endpoint_is_exempt_when_client_is_over_limit(store, clock):
    client = _client(store, clock, requests_per_minute=1, burst_size=1)

    assert client.get("/api/v1/sessions").status_code == 200
    assert client.get("/api/v1/sessions").status_code == 200
    assert client.get("/api/v1/sessions").status_code == 429

    health = client.get("/api/v1/health")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_custom_config_values_are_applied(store, clock):
    client = _client(store, clock, requests_per_minute=1, burst_size=2)

    for _ in range(3):
        assert client.get("/api/v1/summary").status_code == 200

    assert client.get("/api/v1/summary").status_code == 429


def test_stale_entries_are_pruned_and_requests_allowed_after_window(store, clock):
    client = _client(store, clock, requests_per_minute=1, burst_size=1)

    assert client.get("/api/v1/sessions").status_code == 200
    assert client.get("/api/v1/sessions").status_code == 200
    assert client.get("/api/v1/sessions").status_code == 429

    clock.advance(61)

    assert client.get("/api/v1/sessions").status_code == 200


def test_prometheus_rate_limited_counter_exposed(store, clock):
    import prometheus_metrics

    prometheus_metrics.reset_metrics()
    client = _client(store, clock, requests_per_minute=1, burst_size=1)

    assert client.get("/api/v1/sessions").status_code == 200
    assert client.get("/api/v1/sessions").status_code == 200
    assert client.get("/api/v1/sessions").status_code == 429

    clock.advance(61)
    metrics = client.get("/metrics")
    if not prometheus_metrics.metrics_available():
        assert metrics.status_code == 503
    else:
        assert metrics.status_code == 200
        body = metrics.text
        assert "# HELP tps_api_rate_limited_total" in body
        assert "tps_api_rate_limited_total 1.0" in body
