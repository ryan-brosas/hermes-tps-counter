"""Tests for SQLite persistence layer (store.py and __init__ integration)."""
from __future__ import annotations

import os
import sys
import threading
import types
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


# ------------------------------------------------------------------
# T1: Schema creation and store basics
# ------------------------------------------------------------------


class TestSchemaCreation:
    def test_fresh_db_has_tables(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            import sqlite3
            conn = sqlite3.connect(db)
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            conn.close()
            assert "session_tps" in tables
            assert "schema_version" in tables
        finally:
            store.close()

    def test_schema_version_is_set(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            import sqlite3
            conn = sqlite3.connect(db)
            cur = conn.execute("SELECT version FROM schema_version")
            row = cur.fetchone()
            conn.close()
            assert row is not None
            assert row[0] == 1
        finally:
            store.close()

    def test_wal_mode_enabled(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            import sqlite3
            conn = sqlite3.connect(db)
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            conn.close()
            assert mode.lower() == "wal"
        finally:
            store.close()


# ------------------------------------------------------------------
# T2: Save / Load roundtrip
# ------------------------------------------------------------------


class TestSaveLoadRoundtrip:
    def test_save_and_load(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            state = {
                "call_count": 5,
                "total_output_tokens": 1000,
                "total_duration": 10.0,
                "peak_tps": 150.0,
                "last_call_tps": 100.0,
                "avg_tps": 100.0,
            }
            store.save("sess-1", state)
            loaded = store.load("sess-1")
            assert loaded is not None
            assert loaded["call_count"] == 5
            assert loaded["total_output_tokens"] == 1000
            assert loaded["total_duration"] == 10.0
            assert loaded["peak_tps"] == 150.0
            assert loaded["last_call_tps"] == 100.0
            assert loaded["avg_tps"] == 100.0
            assert loaded["session_id"] == "sess-1"
        finally:
            store.close()

    def test_load_nonexistent_returns_none(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            assert store.load("no-such-session") is None
        finally:
            store.close()

    def test_upsert_overwrites(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            store.save("s1", {"call_count": 1, "total_output_tokens": 10,
                               "total_duration": 1.0, "peak_tps": 10.0,
                               "last_call_tps": 10.0, "avg_tps": 10.0})
            store.save("s1", {"call_count": 2, "total_output_tokens": 30,
                               "total_duration": 3.0, "peak_tps": 20.0,
                               "last_call_tps": 20.0, "avg_tps": 10.0})
            loaded = store.load("s1")
            assert loaded["call_count"] == 2
            assert loaded["total_output_tokens"] == 30
        finally:
            store.close()

    def test_survive_close_and_reopen(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        store.save("persist-me", {"call_count": 42, "total_output_tokens": 9999,
                                   "total_duration": 50.0, "peak_tps": 200.0,
                                   "last_call_tps": 180.0, "avg_tps": 199.98})
        store.close()

        # Reopen — data must survive
        store2 = PersistentSessionStore(db)
        try:
            loaded = store2.load("persist-me")
            assert loaded is not None
            assert loaded["call_count"] == 42
            assert loaded["total_output_tokens"] == 9999
            assert loaded["peak_tps"] == 200.0
        finally:
            store2.close()


# ------------------------------------------------------------------
# T3: load_all
# ------------------------------------------------------------------


class TestLoadAll:
    def test_load_all_empty(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            result = store.load_all()
            assert result == {}
        finally:
            store.close()

    def test_load_all_multiple(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            for i in range(5):
                store.save(f"s{i}", {"call_count": i, "total_output_tokens": i * 100,
                                      "total_duration": float(i), "peak_tps": float(i),
                                      "last_call_tps": float(i), "avg_tps": float(i)})
            all_data = store.load_all()
            assert len(all_data) == 5
            assert all_data["s0"]["call_count"] == 0
            assert all_data["s4"]["call_count"] == 4
        finally:
            store.close()


# ------------------------------------------------------------------
# T4: Thread safety — concurrent writes
# ------------------------------------------------------------------


class TestConcurrentWrites:
    def test_concurrent_saves_no_corruption(self, tmp_path):
        db = str(tmp_path / "test.db")
        store = PersistentSessionStore(db)
        try:
            n_threads = 4
            barrier = threading.Barrier(n_threads)

            def worker(idx):
                barrier.wait()
                for j in range(20):
                    store.save(f"t{idx}", {
                        "call_count": j + 1,
                        "total_output_tokens": (j + 1) * 10,
                        "total_duration": float(j + 1),
                        "peak_tps": float(j + 1),
                        "last_call_tps": float(j + 1),
                        "avg_tps": float(j + 1),
                    })

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            all_data = store.load_all()
            assert len(all_data) == n_threads
            for i in range(n_threads):
                entry = all_data[f"t{i}"]
                assert entry["call_count"] == 20
        finally:
            store.close()


# ------------------------------------------------------------------
# T5: Graceful degradation (integration with __init__.py)
# ------------------------------------------------------------------


class TestGracefulDegradation:
    def test_invalid_db_path_falls_back_to_memory(self, tmp_path):
        """If DB path is invalid, register() sets _STORE=None and plugin works."""
        import __init__ as plugin

        # Reset global state
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
        plugin._STORE = None

        mock_ctx = MagicMock()
        # Force config to point at a path inside a read-only location
        mock_ctx.get_config.return_value = {"db_path": "/proc/impossible.tps.db"}
        mock_ctx.config = {}

        plugin.register(mock_ctx)

        # Store should be None (graceful degradation)
        assert plugin._STORE is None

        # Plugin still works in-memory
        plugin._on_post_api_request(
            session_id="fallback-test",
            usage={"output_tokens": 100},
            api_duration=1.0,
        )
        with plugin._STATE_LOCK:
            state = plugin._SESSIONS.get("fallback-test")
        assert state is not None
        assert state.call_count == 1
        assert state.total_output_tokens == 100

        # Cleanup
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()

    def test_persistence_roundtrip_with_register(self, tmp_path):
        """Full integration: register → record → close → register again → data survives."""
        import __init__ as plugin

        db_path = str(tmp_path / "tps.db")

        # First run — record data
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
        plugin._STORE = None

        mock_ctx = MagicMock()
        mock_ctx.get_config.return_value = {"db_path": db_path}
        mock_ctx.config = {}
        plugin.register(mock_ctx)
        assert plugin._STORE is not None

        plugin._on_post_api_request(
            session_id="roundtrip-sess",
            usage={"output_tokens": 500},
            api_duration=2.5,
        )

        # Verify in-memory
        with plugin._STATE_LOCK:
            state = plugin._SESSIONS.get("roundtrip-sess")
        assert state is not None
        assert state.call_count == 1
        assert state.total_output_tokens == 500

        # Close store (simulate restart)
        plugin._STORE.close()
        plugin._STORE = None
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()

        # Second run — should hydrate from DB
        mock_ctx2 = MagicMock()
        mock_ctx2.get_config.return_value = {"db_path": db_path}
        mock_ctx2.config = {}
        plugin.register(mock_ctx2)
        assert plugin._STORE is not None

        # _get_session should load from DB
        session = plugin._get_session("roundtrip-sess")
        assert session.call_count == 1
        assert session.total_output_tokens == 500
        assert session.total_duration == 2.5
        assert session.peak_tps == 200.0

        # Cleanup
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
        plugin._STORE.close()
        plugin._STORE = None

    def test_persist_on_record(self, tmp_path):
        """Each record() call writes through to DB."""
        import __init__ as plugin

        db_path = str(tmp_path / "tps.db")
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
        plugin._STORE = None

        mock_ctx = MagicMock()
        mock_ctx.get_config.return_value = {"db_path": db_path}
        mock_ctx.config = {}
        plugin.register(mock_ctx)

        plugin._on_post_api_request(
            session_id="pw-sess",
            usage={"output_tokens": 100},
            api_duration=1.0,
        )
        plugin._on_post_api_request(
            session_id="pw-sess",
            usage={"output_tokens": 200},
            api_duration=2.0,
        )

        # Verify DB directly
        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT call_count, total_output_tokens FROM session_tps WHERE session_id='pw-sess'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 2  # call_count
        assert row[1] == 300  # total_output_tokens

        # Cleanup
        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
        plugin._STORE.close()
        plugin._STORE = None


# ------------------------------------------------------------------
# T6: Existing test compatibility (import smoke test)
# ------------------------------------------------------------------


class TestImports:
    def test_import_store(self):
        from store import PersistentSessionStore
        assert callable(PersistentSessionStore)

    def test_import_init_no_crash(self):
        import __init__ as plugin
        assert hasattr(plugin, "_SessionTPS")
        assert hasattr(plugin, "_on_post_api_request")
        assert hasattr(plugin, "register")
        assert hasattr(plugin, "get_tps_stats")
