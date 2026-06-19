"""Tests for per-call TPS event storage (store.py + api.py + __init__.py integration)."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import threading
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

# Ensure the plugin root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from store import PersistentSessionStore


@pytest.fixture(autouse=True)
def mock_hermes_cli():
    """Mock hermes_cli for plugin import compatibility."""
    mod = types.ModuleType("hermes_cli")
    mod._ACTIVE_CLI_INSTANCE = None
    with patch.dict(sys.modules, {"hermes_cli": mod}):
        yield


@pytest.fixture
def store(tmp_path):
    """Create a temporary PersistentSessionStore for testing."""
    db = str(tmp_path / "test_events.db")
    s = PersistentSessionStore(db)
    yield s
    s.close()


# ------------------------------------------------------------------
# Schema migration
# ------------------------------------------------------------------


class TestSchemaMigration:
    def test_fresh_db_has_call_events_table(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            conn = sqlite3.connect(db)
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            conn.close()
            assert "call_events" in tables
        finally:
            store.close()

    def test_schema_version_is_3(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            conn = sqlite3.connect(db)
            row = conn.execute("SELECT version FROM schema_version").fetchone()
            conn.close()
            assert row is not None
            assert row[0] == 3
        finally:
            store.close()

    def test_call_events_index_exists(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            conn = sqlite3.connect(db)
            indexes = {
                row[1]
                for row in conn.execute(
                    "SELECT * FROM sqlite_master WHERE type='index'"
                ).fetchall()
            }
            conn.close()
            assert "idx_call_events_session_time" in indexes
            assert "idx_call_events_created_at" in indexes
            assert "idx_session_tps_updated_at" in indexes
        finally:
            store.close()

    def test_migration_from_v2_to_v3(self, tmp_path):
        """Simulate a v2 DB being opened by new code — call_events table is added."""
        db = str(tmp_path / "test.db")
        # Create a v2 schema
        conn = sqlite3.connect(db)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
            INSERT INTO schema_version (version) VALUES (2);
            CREATE TABLE IF NOT EXISTS session_tps (
                session_id TEXT PRIMARY KEY, call_count INTEGER, total_output_tokens INTEGER,
                total_input_tokens INTEGER, total_duration REAL, peak_tps REAL,
                last_call_tps REAL, avg_tps REAL, updated_at TEXT
            );
        """)
        conn.commit()
        conn.close()

        # Open with new code — should migrate to v3 and create call_events
        store = PersistentSessionStore(db)
        try:
            conn = sqlite3.connect(db)
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
            conn.close()
            assert "call_events" in tables
            assert version == 3
        finally:
            store.close()


# ------------------------------------------------------------------
# record_event
# ------------------------------------------------------------------


class TestRecordEvent:
    def test_record_and_count(self, store):
        store.record_event("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0)
        store.record_event("s1", "gpt-4", "openai", 150, 300, 3.0, 100.0)
        assert store.event_count() == 2

    def test_record_multiple_sessions(self, store):
        store.record_event("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0)
        store.record_event("s2", "claude", "anthropic", 50, 100, 1.0, 100.0)
        assert store.event_count() == 2

    def test_record_stores_correct_data(self, store):
        store.record_event("s1", "gpt-4o", "openai", 150, 250, 2.5, 100.0)
        events = store.load_events("s1")
        assert len(events) == 1
        e = events[0]
        assert e["session_id"] == "s1"
        assert e["model"] == "gpt-4o"
        assert e["provider"] == "openai"
        assert e["input_tokens"] == 150
        assert e["output_tokens"] == 250
        assert e["duration"] == 2.5
        assert e["tps"] == 100.0
        assert "created_at" in e


# ------------------------------------------------------------------
# load_events
# ------------------------------------------------------------------


class TestLoadEvents:
    def test_load_empty(self, store):
        events = store.load_events("nonexistent")
        assert events == []

    def test_load_with_since_filter(self, store):
        # Insert events with known timestamps
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

        # Query with since filter — should return only the recent one
        since = (now - timedelta(hours=1)).isoformat()
        events = store.load_events("s1", since=since)
        assert len(events) == 1
        assert events[0]["output_tokens"] == 40

    def test_load_with_until_filter(self, store):
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

        until = (now - timedelta(hours=1)).isoformat()
        events = store.load_events("s1", until=until)
        assert len(events) == 1
        assert events[0]["output_tokens"] == 20

    def test_load_with_limit(self, store):
        for i in range(10):
            store.record_event("s1", "m1", "p1", i * 10, i * 20, 1.0, float(i * 20))
        events = store.load_events("s1", limit=5)
        assert len(events) == 5


# ------------------------------------------------------------------
# Aggregation
# ------------------------------------------------------------------


class TestAggregateByModel:
    def test_two_models(self, store):
        store.record_event("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0)
        store.record_event("s1", "gpt-4", "openai", 150, 300, 3.0, 100.0)
        store.record_event("s1", "claude", "anthropic", 50, 100, 1.0, 100.0)

        result = store.aggregate_by_model("s1")
        assert "gpt-4" in result
        assert "claude" in result
        assert result["gpt-4"]["calls"] == 2
        assert result["gpt-4"]["total_output"] == 500
        assert result["gpt-4"]["total_input"] == 250
        assert result["claude"]["calls"] == 1
        assert result["claude"]["total_output"] == 100

    def test_with_since_filter(self, store):
        now = datetime.now(timezone.utc)
        old = (now - timedelta(hours=2)).isoformat()
        recent = (now - timedelta(minutes=5)).isoformat()

        with store._lock:
            store._conn.execute(
                "INSERT INTO call_events (session_id, model, provider, input_tokens, output_tokens, duration, tps, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0, old),
            )
            store._conn.execute(
                "INSERT INTO call_events (session_id, model, provider, input_tokens, output_tokens, duration, tps, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("s1", "gpt-4", "openai", 150, 300, 3.0, 100.0, recent),
            )
            store._conn.commit()

        since = (now - timedelta(hours=1)).isoformat()
        result = store.aggregate_by_model("s1", since=since)
        assert result["gpt-4"]["calls"] == 1
        assert result["gpt-4"]["total_output"] == 300


class TestAggregateByProvider:
    def test_two_providers(self, store):
        store.record_event("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0)
        store.record_event("s1", "gpt-4", "openai", 150, 300, 3.0, 100.0)
        store.record_event("s1", "claude", "anthropic", 50, 100, 1.0, 100.0)

        result = store.aggregate_by_provider("s1")
        assert "openai" in result
        assert "anthropic" in result
        assert result["openai"]["calls"] == 2
        assert result["openai"]["total_output"] == 500
        assert result["anthropic"]["calls"] == 1
        assert result["anthropic"]["total_output"] == 100


# ------------------------------------------------------------------
# Auto-expiry
# ------------------------------------------------------------------


class TestAutoExpiry:
    def test_delete_expired_events(self, store):
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=10)).isoformat()
        recent = (now - timedelta(hours=1)).isoformat()

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

        deleted = store.delete_expired_events(7 * 86400)  # 7 days
        assert deleted == 1
        events = store.load_events("s1")
        assert len(events) == 1
        assert events[0]["output_tokens"] == 40

    def test_lazy_expiry_on_write(self, store):
        """After 100 event writes, old events should be auto-purged."""
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=10)).isoformat()

        # Insert an old event directly
        with store._lock:
            store._conn.execute(
                "INSERT INTO call_events (session_id, model, provider, input_tokens, output_tokens, duration, tps, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("s1", "m1", "p1", 10, 20, 1.0, 20.0, old),
            )
            store._conn.commit()

        # Write 100 events to trigger lazy expiry
        for i in range(100):
            store.record_event("s1", "m1", "p1", 10, 20, 1.0, 20.0)

        # The old event should be gone; the 100 new ones should remain
        events = store.load_events("s1", limit=200)
        for e in events:
            assert e["output_tokens"] == 20  # only new events


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------


class TestConcurrentEventWrites:
    def test_concurrent_writes_no_corruption(self, store):
        n_threads = 4
        writes_per_thread = 20
        barrier = threading.Barrier(n_threads)

        def worker(idx):
            barrier.wait()
            for j in range(writes_per_thread):
                store.record_event(
                    f"t{idx}", "model", "provider", j * 10, j * 20, 1.0, float(j * 20)
                )

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert store.event_count() == n_threads * writes_per_thread


# ------------------------------------------------------------------
# Export store methods
# ------------------------------------------------------------------


class TestExportEvents:
    def test_export_events_empty(self, store):
        """Empty DB returns empty list."""
        assert store.export_events() == []

    def test_export_events_returns_seeded_data(self, store):
        """Records events and exports them with correct fields."""
        store.record_event("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0)
        store.record_event("s2", "claude", "anthropic", 50, 100, 1.0, 100.0)
        result = store.export_events()
        assert len(result) == 2
        for e in result:
            assert "id" in e
            assert "session_id" in e
            assert "model" in e
            assert "provider" in e
            assert "input_tokens" in e
            assert "output_tokens" in e
            assert "duration" in e
            assert "tps" in e
            assert "created_at" in e

    def test_export_events_with_since_filter(self, store):
        """Only events after the since timestamp are returned."""
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
        result = store.export_events(since=since)
        assert len(result) == 1
        assert result[0]["output_tokens"] == 40

    def test_export_events_with_session_id_filter(self, store):
        """Only events for the requested session are returned before LIMIT."""
        for idx in range(5):
            store.record_event(f"other-{idx}", "m1", "p1", 10, 20, 1.0, 20.0)
        store.record_event("target", "m1", "p1", 30, 40, 2.0, 20.0)

        result = store.export_events(session_id="target", limit=1)

        assert len(result) == 1
        assert result[0]["session_id"] == "target"

    def test_export_events_with_until_filter(self, store):
        """Only events before the until timestamp are returned."""
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

        until = (now - timedelta(hours=1)).isoformat()
        result = store.export_events(until=until)
        assert len(result) == 1
        assert result[0]["output_tokens"] == 20

    def test_export_events_respects_limit(self, store):
        """Limit caps the number of returned rows."""
        for i in range(10):
            store.record_event("s1", "m1", "p1", i * 10, i * 20, 1.0, float(i * 20))
        result = store.export_events(limit=5)
        assert len(result) == 5

    def test_export_events_max_limit_clamped(self, store):
        """max_limit overrides an excessive limit value."""
        for i in range(10):
            store.record_event("s1", "m1", "p1", i * 10, i * 20, 1.0, float(i * 20))
        result = store.export_events(limit=999, max_limit=5)
        assert len(result) == 5

    def test_export_events_cross_session(self, store):
        """Exports events from multiple sessions."""
        store.record_event("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0)
        store.record_event("s2", "claude", "anthropic", 50, 100, 1.0, 100.0)
        store.record_event("s3", "gemini", "google", 80, 160, 1.5, 106.7)
        result = store.export_events()
        assert len(result) == 3
        session_ids = {e["session_id"] for e in result}
        assert session_ids == {"s1", "s2", "s3"}


class TestExportSessions:
    def test_export_sessions_empty(self, store):
        """Empty DB returns empty list."""
        assert store.export_sessions() == []

    def test_export_sessions_returns_seeded_data(self, store):
        """Saves sessions and exports them with correct fields."""
        store.save("s1", {"call_count": 1, "total_output_tokens": 100,
                          "total_input_tokens": 50, "total_duration": 2.0,
                          "peak_tps": 50.0, "last_call_tps": 50.0, "avg_tps": 50.0})
        store.save("s2", {"call_count": 3, "total_output_tokens": 300,
                          "total_input_tokens": 150, "total_duration": 6.0,
                          "peak_tps": 60.0, "last_call_tps": 55.0, "avg_tps": 50.0})
        result = store.export_sessions()
        assert len(result) == 2
        for s in result:
            assert "session_id" in s
            assert "call_count" in s
            assert "total_output_tokens" in s
            assert "total_input_tokens" in s
            assert "updated_at" in s

    def test_export_sessions_with_session_ids_filter(self, store):
        """Filters to requested sessions only."""
        store.save("s1", {"call_count": 1, "total_output_tokens": 100,
                          "total_input_tokens": 50, "total_duration": 2.0,
                          "peak_tps": 50.0, "last_call_tps": 50.0, "avg_tps": 50.0})
        store.save("s2", {"call_count": 3, "total_output_tokens": 300,
                          "total_input_tokens": 150, "total_duration": 6.0,
                          "peak_tps": 60.0, "last_call_tps": 55.0, "avg_tps": 50.0})
        store.save("s3", {"call_count": 2, "total_output_tokens": 200,
                          "total_input_tokens": 100, "total_duration": 4.0,
                          "peak_tps": 55.0, "last_call_tps": 50.0, "avg_tps": 50.0})
        result = store.export_sessions(session_ids=["s1", "s3"])
        assert len(result) == 2
        ids = {s["session_id"] for s in result}
        assert ids == {"s1", "s3"}

    def test_export_sessions_respects_limit(self, store):
        """Limit caps the number of returned rows."""
        for i in range(10):
            store.save(f"s{i}", {"call_count": i, "total_output_tokens": i * 100,
                                 "total_input_tokens": i * 50, "total_duration": float(i),
                                 "peak_tps": float(i * 10), "last_call_tps": float(i * 10),
                                 "avg_tps": float(i * 10)})
        result = store.export_sessions(limit=5)
        assert len(result) == 5

    def test_export_sessions_max_limit_clamped(self, store):
        """max_limit overrides an excessive limit value."""
        for i in range(10):
            store.save(f"s{i}", {"call_count": i, "total_output_tokens": i * 100,
                                 "total_input_tokens": i * 50, "total_duration": float(i),
                                 "peak_tps": float(i * 10), "last_call_tps": float(i * 10),
                                 "avg_tps": float(i * 10)})
        result = store.export_sessions(limit=999, max_limit=3)
        assert len(result) == 3


# ------------------------------------------------------------------
# REST API endpoints
# ------------------------------------------------------------------


class TestEventsEndpoint:
    @pytest.fixture
    def client(self, store):
        from api import create_app
        from fastapi.testclient import TestClient

        app = create_app(store)
        return TestClient(app)

    def test_events_503_when_store_none(self):
        from api import create_app
        from fastapi.testclient import TestClient

        app = create_app(None)
        c = TestClient(app)
        resp = c.get("/api/v1/events/s1")
        assert resp.status_code == 503

    def test_events_404_when_no_events(self, client):
        resp = client.get("/api/v1/events/nonexistent")
        assert resp.status_code == 404

    def test_events_returns_correct_count(self, client, store):
        store.record_event("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0)
        store.record_event("s1", "gpt-4", "openai", 150, 300, 3.0, 100.0)
        store.record_event("s1", "claude", "anthropic", 50, 100, 1.0, 100.0)

        resp = client.get("/api/v1/events/s1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 3
        assert data["events"][0]["session_id"] == "s1"

    def test_events_with_since_filter(self, client, store):
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
        resp = client.get(f"/api/v1/events/s1?since={since}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 1


class TestExportHistoryEndpoint:
    @pytest.fixture
    def client(self, store):
        from api import create_app
        from fastapi.testclient import TestClient

        app = create_app(store)
        return TestClient(app)

    def test_export_history_rejects_limit_above_hard_cap(self, client):
        resp = client.get("/api/v1/export/history?limit=1001")

        assert resp.status_code == 422
        assert "exceeds maximum 1000" in resp.json()["detail"]

    def test_export_history_filters_events_before_limit(self, client, store):
        for idx in range(5):
            store.record_event(f"other-{idx}", "m1", "p1", 10, 20, 1.0, 20.0)
        store.record_event("target", "m1", "p1", 30, 40, 2.0, 20.0)

        resp = client.get("/api/v1/export/history?session_id=target&limit=1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"]["event_count"] == 1
        assert data["events"][0]["session_id"] == "target"


class TestTrendsEndpoint:
    @pytest.fixture
    def client(self, store):
        from api import create_app
        from fastapi.testclient import TestClient

        app = create_app(store)
        return TestClient(app)

    def test_trends_503_when_store_none(self):
        from api import create_app
        from fastapi.testclient import TestClient

        app = create_app(None)
        c = TestClient(app)
        resp = c.get("/api/v1/trends/s1")
        assert resp.status_code == 503

    def test_trends_404_when_no_events(self, client):
        resp = client.get("/api/v1/trends/nonexistent")
        assert resp.status_code == 404

    def test_trends_returns_model_and_provider_breakdowns(self, client, store):
        store.record_event("s1", "gpt-4", "openai", 100, 200, 2.0, 100.0)
        store.record_event("s1", "gpt-4", "openai", 150, 300, 3.0, 100.0)
        store.record_event("s1", "claude", "anthropic", 50, 100, 1.0, 100.0)

        resp = client.get("/api/v1/trends/s1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "s1"
        assert "gpt-4" in data["models"]
        assert "claude" in data["models"]
        assert "openai" in data["providers"]
        assert "anthropic" in data["providers"]
        assert data["models"]["gpt-4"]["calls"] == 2
        assert data["models"]["claude"]["calls"] == 1


# ------------------------------------------------------------------
# Integration: hook records events
# ------------------------------------------------------------------


class TestHookIntegration:
    def test_hook_records_events(self, tmp_path):
        """_on_post_api_request should write to call_events table."""
        import __init__ as plugin

        db_path = str(tmp_path / "tps.db")
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
        plugin._STORE = None

        mock_ctx = MagicMock()
        mock_ctx.get_config.return_value = {"db_path": db_path}
        mock_ctx.config = {}
        plugin.register(mock_ctx)
        assert plugin._STORE is not None

        # Call the hook 3 times
        for i in range(3):
            plugin._on_post_api_request(
                session_id="hook-test",
                model="openai/gpt-4o",
                usage={"output_tokens": 100 * (i + 1), "input_tokens": 50 * (i + 1)},
                api_duration=1.0,
            )

        # Verify call_events has 3 rows
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM call_events").fetchone()[0]
        conn.close()
        assert count == 3

        # Cleanup
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
        plugin._STORE.close()
        plugin._STORE = None
