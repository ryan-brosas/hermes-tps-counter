"""Tests for delete, delete_expired, count methods and cleanup integration."""
from __future__ import annotations

import os
import sys
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


def _make_state(call_count=1, tokens=100, duration=1.0, peak=100.0, last=100.0, avg=100.0):
    return {
        "call_count": call_count,
        "total_output_tokens": tokens,
        "total_duration": duration,
        "peak_tps": peak,
        "last_call_tps": last,
        "avg_tps": avg,
    }


# ------------------------------------------------------------------
# TestDelete
# ------------------------------------------------------------------


class TestDelete:
    def test_delete_existing_session(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            store.save("sess-1", _make_state())
            assert store.load("sess-1") is not None

            result = store.delete("sess-1")
            assert result is True
            assert store.load("sess-1") is None
        finally:
            store.close()

    def test_delete_nonexistent_session(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            result = store.delete("no-such-session")
            assert result is False
        finally:
            store.close()

    def test_delete_on_closed_store(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        store.close()
        result = store.delete("any-session")
        assert result is False


# ------------------------------------------------------------------
# TestDeleteExpired
# ------------------------------------------------------------------


class TestDeleteExpired:
    def test_delete_expired_removes_old_sessions(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            # Save 3 sessions (all get fresh updated_at)
            store.save("s1", _make_state())
            store.save("s2", _make_state())
            store.save("s3", _make_state())

            # Back-date 2 of them
            old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
            with store._lock:
                store._conn.execute(
                    "UPDATE session_tps SET updated_at = ? WHERE session_id IN (?, ?)",
                    (old_time, "s1", "s2"),
                )
                store._conn.commit()

            deleted = store.delete_expired(max_age_seconds=3600)  # 1 hour
            assert deleted == 2
            assert store.count() == 1
            assert store.load("s3") is not None
        finally:
            store.close()

    def test_delete_expired_no_matches(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            store.save("s1", _make_state())
            deleted = store.delete_expired(max_age_seconds=1)  # 1 second
            assert deleted == 0
            assert store.count() == 1
        finally:
            store.close()

    def test_delete_expired_empty_db(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            deleted = store.delete_expired(max_age_seconds=3600)
            assert deleted == 0
        finally:
            store.close()


# ------------------------------------------------------------------
# TestCount
# ------------------------------------------------------------------


class TestCount:
    def test_count_empty(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            assert store.count() == 0
        finally:
            store.close()

    def test_count_populated(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            for i in range(3):
                store.save(f"s{i}", _make_state())
            assert store.count() == 3
        finally:
            store.close()

    def test_count_after_delete(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            for i in range(3):
                store.save(f"s{i}", _make_state())
            store.delete("s1")
            assert store.count() == 2
        finally:
            store.close()


# ------------------------------------------------------------------
# TestCleanupIntegration
# ------------------------------------------------------------------


class TestCleanupIntegration:
    def test_cleanup_deletes_from_db(self, tmp_path):
        """_cleanup_session removes from both memory and DB."""
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

        # Create a session via the hook
        plugin._on_post_api_request(
            session_id="cleanup-test",
            usage={"output_tokens": 200},
            api_duration=2.0,
        )

        # Verify it exists in both memory and DB
        with plugin._STATE_LOCK:
            assert "cleanup-test" in plugin._SESSIONS
        assert plugin._STORE.load("cleanup-test") is not None

        # Cleanup
        plugin._cleanup_session("cleanup-test")

        # Verify removed from both
        with plugin._STATE_LOCK:
            assert "cleanup-test" not in plugin._SESSIONS
        assert plugin._STORE.load("cleanup-test") is None

        # Teardown
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
        plugin._STORE.close()
        plugin._STORE = None

    def test_cleanup_nonexistent_session(self, tmp_path):
        """_cleanup_session for unknown session does not error."""
        import __init__ as plugin

        db_path = str(tmp_path / "tps.db")
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
        plugin._STORE = None

        mock_ctx = MagicMock()
        mock_ctx.get_config.return_value = {"db_path": db_path}
        mock_ctx.config = {}
        plugin.register(mock_ctx)

        # Should not raise
        plugin._cleanup_session("unknown-session")

        # Teardown
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
        plugin._STORE.close()
        plugin._STORE = None

    def test_concurrent_deletes(self, tmp_path):
        """Thread safety: concurrent deletes don't corrupt the DB."""
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            for i in range(20):
                store.save(f"s{i}", _make_state())
            assert store.count() == 20

            n_threads = 4
            barrier = threading.Barrier(n_threads)

            def worker(idx):
                barrier.wait()
                for j in range(5):
                    store.delete(f"s{idx * 5 + j}")

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            assert store.count() == 0
        finally:
            store.close()
