"""Tests for core plugin behavior: TPS calculation, session management, and lifecycle."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import types
from unittest.mock import patch, MagicMock

import pytest

# Ensure the plugin root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def mock_hermes_cli():
    """Mock hermes_cli for plugin import compatibility."""
    mod = types.ModuleType("hermes_cli")
    mod._ACTIVE_CLI_INSTANCE = None
    with patch.dict(sys.modules, {"hermes_cli": mod}):
        yield


@pytest.fixture(autouse=True)
def clean_state():
    """Clear all global state before and after each test."""
    from __init__ import _SESSIONS, _MODELS, _PROVIDERS, _STATE_LOCK, _STORE
    import __init__ as plugin
    with _STATE_LOCK:
        _SESSIONS.clear()
        _MODELS.clear()
        _PROVIDERS.clear()
    # Reset _STORE to None to avoid persistence side effects in unit tests
    old_store = plugin._STORE
    plugin._STORE = None
    yield
    with _STATE_LOCK:
        _SESSIONS.clear()
        _MODELS.clear()
        _PROVIDERS.clear()
    plugin._STORE = old_store


@pytest.fixture
def temp_db():
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


# ---------------------------------------------------------------------------
# 1. _SessionTPS: record() and properties
# ---------------------------------------------------------------------------

class TestSessionTPSRecord:
    """Test _SessionTPS.record() behavior."""

    def test_record_single_call(self):
        """record() increments call_count, accumulates tokens/duration, computes TPS."""
        from __init__ import _SessionTPS
        s = _SessionTPS()
        s.record(output_tokens=100, duration=2.0, input_tokens=50)
        assert s.call_count == 1
        assert s.total_output_tokens == 100
        assert s.total_input_tokens == 50
        assert s.total_duration == 2.0
        assert s.last_call_tps == 50.0
        assert s.last_call_output_tokens == 100
        assert s.last_call_input_tokens == 50
        assert s.last_call_duration == 2.0

    def test_record_multiple_calls(self):
        """Multiple record() calls accumulate correctly."""
        from __init__ import _SessionTPS
        s = _SessionTPS()
        s.record(output_tokens=100, duration=2.0, input_tokens=50)
        s.record(output_tokens=200, duration=1.0, input_tokens=80)
        assert s.call_count == 2
        assert s.total_output_tokens == 300
        assert s.total_input_tokens == 130
        assert s.total_duration == 3.0

    def test_record_zero_duration(self):
        """record() with zero duration does not compute TPS."""
        from __init__ import _SessionTPS
        s = _SessionTPS()
        s.record(output_tokens=100, duration=0.0)
        assert s.call_count == 1
        assert s.last_call_tps == 0.0


class TestSessionTPSProperties:
    """Test _SessionTPS properties: avg_tps, peak_tps, total_tokens, turn_tps."""

    def test_avg_tps_returns_ratio(self):
        """avg_tps returns total_output_tokens / total_duration."""
        from __init__ import _SessionTPS
        s = _SessionTPS()
        s.record(output_tokens=200, duration=4.0)
        assert s.avg_tps == 50.0

    def test_avg_tps_zero_duration(self):
        """avg_tps returns 0.0 when total_duration is 0."""
        from __init__ import _SessionTPS
        s = _SessionTPS()
        assert s.avg_tps == 0.0

    def test_peak_tps_tracks_max(self):
        """peak_tps tracks the maximum TPS across multiple record() calls."""
        from __init__ import _SessionTPS
        s = _SessionTPS()
        s.record(output_tokens=100, duration=2.0)  # 50 tok/s
        s.record(output_tokens=300, duration=1.0)  # 300 tok/s
        s.record(output_tokens=50, duration=2.0)   # 25 tok/s
        assert s.peak_tps == 300.0

    def test_total_tokens_property(self):
        """total_tokens returns input + output tokens."""
        from __init__ import _SessionTPS
        s = _SessionTPS()
        s.record(output_tokens=100, duration=1.0, input_tokens=50)
        s.record(output_tokens=200, duration=1.0, input_tokens=80)
        assert s.total_tokens == 430  # (100+50) + (200+80)

    def test_turn_tps_after_reset(self):
        """turn_tps reflects tokens since last reset_turn()."""
        from __init__ import _SessionTPS
        s = _SessionTPS()
        s.record(output_tokens=100, duration=1.0, input_tokens=50)
        s.reset_turn()
        time.sleep(0.05)
        s.record(output_tokens=50, duration=1.0, input_tokens=20)
        turn = s.turn_tps
        # Should reflect the 50 tokens since reset, divided by elapsed wall time
        assert turn > 0
        assert turn < 1000  # sanity check

    def test_turn_tps_zero_elapsed(self):
        """turn_tps returns 0.0 when no time has elapsed since reset."""
        from __init__ import _SessionTPS
        s = _SessionTPS()
        s.record(output_tokens=100, duration=1.0)
        # Before reset, turn_start_time is creation time — some elapsed
        # After reset immediately, turn_start_tokens == current tokens → 0 delta
        s.reset_turn()
        assert s.turn_tps == 0.0


# ---------------------------------------------------------------------------
# 2. _SessionTPS: summary_line and _fmt_tokens
# ---------------------------------------------------------------------------

class TestSessionTPSSummary:
    """Test _SessionTPS.summary_line() and _fmt_tokens()."""

    def test_fmt_tokens_under_1000(self):
        """_fmt_tokens returns raw string for values < 1000."""
        from __init__ import _SessionTPS
        assert _SessionTPS._fmt_tokens(999) == "999"
        assert _SessionTPS._fmt_tokens(0) == "0"
        assert _SessionTPS._fmt_tokens(1) == "1"

    def test_fmt_tokens_thousands(self):
        """_fmt_tokens returns K format for values >= 1000."""
        from __init__ import _SessionTPS
        assert _SessionTPS._fmt_tokens(1500) == "1.5K"
        assert _SessionTPS._fmt_tokens(1000) == "1.0K"
        assert _SessionTPS._fmt_tokens(999999) == "1000.0K"

    def test_fmt_tokens_millions(self):
        """_fmt_tokens returns M format for values >= 1_000_000."""
        from __init__ import _SessionTPS
        assert _SessionTPS._fmt_tokens(1_000_000) == "1.0M"
        assert _SessionTPS._fmt_tokens(2_300_000) == "2.3M"

    def test_summary_line_with_data(self):
        """summary_line() contains expected components when data exists."""
        from __init__ import _SessionTPS
        s = _SessionTPS()
        s.record(output_tokens=500, duration=1.0, input_tokens=200)
        s.record(output_tokens=300, duration=2.0, input_tokens=100)
        line = s.summary_line()
        assert "tok/s" in line
        assert "avg" in line
        assert "peak" in line
        assert "total" in line

    def test_summary_line_single_call_no_avg(self):
        """summary_line() omits avg for single call."""
        from __init__ import _SessionTPS
        s = _SessionTPS()
        s.record(output_tokens=100, duration=1.0, input_tokens=50)
        line = s.summary_line()
        assert "tok/s" in line
        # avg only shown when call_count > 1
        assert "avg" not in line

    def test_summary_line_empty_session(self):
        """summary_line() returns empty string for session with no calls."""
        from __init__ import _SessionTPS
        s = _SessionTPS()
        assert s.summary_line() == ""


# ---------------------------------------------------------------------------
# 3. _ModelTPS and get_model_stats()
# ---------------------------------------------------------------------------

class TestModelTPS:
    """Test _ModelTPS class behavior."""

    def test_model_tps_record(self):
        """_ModelTPS.record() tracks call_count, tokens, duration, avg_tps, peak_tps."""
        from __init__ import _ModelTPS
        m = _ModelTPS()
        m.record(output_tokens=200, duration=2.0)
        assert m.call_count == 1
        assert m.total_output_tokens == 200
        assert m.total_duration == 2.0
        assert m.avg_tps == 100.0
        assert m.peak_tps == 100.0

    def test_model_tps_multiple_records(self):
        """Multiple records accumulate and peak_tps tracks max."""
        from __init__ import _ModelTPS
        m = _ModelTPS()
        m.record(output_tokens=100, duration=2.0)  # 50 tok/s
        m.record(output_tokens=300, duration=1.0)  # 300 tok/s
        assert m.call_count == 2
        assert m.total_output_tokens == 400
        assert m.total_duration == 3.0
        assert m.peak_tps == 300.0

    def test_model_tps_zero_duration(self):
        """avg_tps returns 0.0 when total_duration is 0."""
        from __init__ import _ModelTPS
        m = _ModelTPS()
        assert m.avg_tps == 0.0


class TestGetModelStats:
    """Test get_model_stats() public API."""

    def test_get_model_stats_empty(self):
        """Returns {} for unknown session."""
        from __init__ import get_model_stats
        assert get_model_stats("nonexistent") == {}

    def test_get_model_stats_multiple_models(self):
        """Returns dict with 2+ model keys when multiple models recorded."""
        from __init__ import (
            _on_post_api_request, _SESSIONS, _MODELS, _STATE_LOCK, get_model_stats,
        )
        mock_cli = MagicMock()
        mock_cli.agent._tps_snapshot = {}
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="s1", model="openai/gpt-4o",
                usage={"output_tokens": 100, "input_tokens": 50}, api_duration=1.0,
            )
            _on_post_api_request(
                session_id="s1", model="anthropic/claude-sonnet-4",
                usage={"output_tokens": 200, "input_tokens": 80}, api_duration=2.0,
            )
        stats = get_model_stats("s1")
        assert "openai/gpt-4o" in stats
        assert "anthropic/claude-sonnet-4" in stats
        assert len(stats) == 2

    def test_get_model_stats_structure(self):
        """Each model entry has avg_tps, peak_tps, calls, total_output_tokens, total_duration."""
        from __init__ import (
            _on_post_api_request, _SESSIONS, _MODELS, _STATE_LOCK, get_model_stats,
        )
        mock_cli = MagicMock()
        mock_cli.agent._tps_snapshot = {}
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="s1", model="openai/gpt-4o",
                usage={"output_tokens": 100, "input_tokens": 50}, api_duration=1.0,
            )
        stats = get_model_stats("s1")
        model = stats["openai/gpt-4o"]
        for key in ("avg_tps", "peak_tps", "calls", "total_output_tokens", "total_duration"):
            assert key in model, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# 4. get_tps_stats()
# ---------------------------------------------------------------------------

class TestGetTpsStats:
    """Test get_tps_stats() public API."""

    def test_get_tps_stats_unknown_session(self):
        """Returns dict with zeros for unknown session."""
        from __init__ import get_tps_stats
        stats = get_tps_stats("nonexistent")
        assert stats["calls"] == 0
        assert stats["avg_tps"] == 0
        assert stats["last_tps"] == 0
        assert stats["peak_tps"] == 0
        assert stats["total_output_tokens"] == 0
        assert stats["total_input_tokens"] == 0
        assert stats["total_tokens"] == 0

    def test_get_tps_stats_with_data(self):
        """Returns correct values after recording data."""
        from __init__ import (
            _on_post_api_request, _SESSIONS, _STATE_LOCK, get_tps_stats,
        )
        mock_cli = MagicMock()
        mock_cli.agent._tps_snapshot = {}
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="s1", model="openai/gpt-4o",
                usage={"output_tokens": 200, "input_tokens": 100}, api_duration=2.0,
            )
        stats = get_tps_stats("s1")
        assert stats["calls"] == 1
        assert stats["avg_tps"] == 100.0
        assert stats["last_tps"] == 100.0
        assert stats["peak_tps"] == 100.0
        assert stats["total_output_tokens"] == 200
        assert stats["total_input_tokens"] == 100
        assert stats["total_tokens"] == 300

    def test_get_tps_stats_includes_session_duration(self):
        """Stats dict includes session_duration key."""
        from __init__ import (
            _on_post_api_request, _SESSIONS, _STATE_LOCK, get_tps_stats,
        )
        mock_cli = MagicMock()
        mock_cli.agent._tps_snapshot = {}
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="s1", model="openai/gpt-4o",
                usage={"output_tokens": 100, "input_tokens": 50}, api_duration=1.0,
            )
        stats = get_tps_stats("s1")
        assert "session_duration" in stats
        assert stats["session_duration"] >= 0


# ---------------------------------------------------------------------------
# 5. _get_session() with DB hydration
# ---------------------------------------------------------------------------

class TestGetSession:
    """Test _get_session() with and without DB hydration."""

    def test_get_session_creates_new(self):
        """Returns fresh _SessionTPS for unknown session id."""
        from __init__ import _get_session, _SessionTPS
        s = _get_session("new-session")
        assert isinstance(s, _SessionTPS)
        assert s.call_count == 0

    def test_get_session_returns_cached(self):
        """Returns same object on second call."""
        from __init__ import _get_session
        s1 = _get_session("cached-session")
        s2 = _get_session("cached-session")
        assert s1 is s2

    def test_get_session_hydrates_from_db(self, temp_db):
        """Loads from persistent store when not in memory."""
        import __init__ as plugin
        from __init__ import _get_session, _SessionTPS, _persist_state
        # Set up a session in the DB
        plugin._STORE = temp_db
        s = _SessionTPS()
        s.record(output_tokens=500, duration=5.0, input_tokens=200)
        _persist_state("db-session", s)
        # Clear in-memory state
        from __init__ import _SESSIONS, _STATE_LOCK
        with _STATE_LOCK:
            _SESSIONS.clear()
        # Now get_session should hydrate from DB
        loaded = _get_session("db-session")
        assert loaded.call_count == 1
        assert loaded.total_output_tokens == 500
        assert loaded.total_input_tokens == 200
        assert loaded.total_duration == 5.0


# ---------------------------------------------------------------------------
# 6. _evict_if_needed()
# ---------------------------------------------------------------------------

class TestEviction:
    """Test _evict_if_needed() LRU eviction logic."""

    def test_evict_noop_under_limit(self):
        """Nothing evicted when count <= MAX_SESSIONS."""
        from __init__ import (
            _get_session, _evict_if_needed, _SESSIONS, _STATE_LOCK, MAX_SESSIONS,
        )
        # Create a few sessions (well under limit)
        for i in range(3):
            _get_session(f"session-{i}")
        _evict_if_needed()
        with _STATE_LOCK:
            assert len(_SESSIONS) == 3

    def test_evicts_oldest_session(self):
        """Removes session with oldest turn_start_time."""
        from __init__ import (
            _SessionTPS, _evict_if_needed, _SESSIONS, _STATE_LOCK, MAX_SESSIONS,
        )
        import time as _time
        with _STATE_LOCK:
            for i in range(MAX_SESSIONS + 1):
                s = _SessionTPS()
                s.turn_start_time = _time.time() + i  # oldest = i=0
                _SESSIONS[f"session-{i}"] = s
        _evict_if_needed()
        with _STATE_LOCK:
            assert len(_SESSIONS) == MAX_SESSIONS
            assert "session-0" not in _SESSIONS  # oldest evicted

    def test_evict_cleans_models_and_providers(self):
        """Eviction removes associated model and provider state."""
        from __init__ import (
            _SessionTPS, _ModelTPS, _ProviderTPS,
            _evict_if_needed, _SESSIONS, _MODELS, _PROVIDERS, _STATE_LOCK, MAX_SESSIONS,
        )
        import time as _time
        with _STATE_LOCK:
            for i in range(MAX_SESSIONS + 1):
                sid = f"session-{i}"
                s = _SessionTPS()
                s.turn_start_time = _time.time() + i
                _SESSIONS[sid] = s
                _MODELS[sid] = {"model": _ModelTPS()}
                _PROVIDERS[sid] = {"provider": _ProviderTPS()}
        _evict_if_needed()
        with _STATE_LOCK:
            assert "session-0" not in _SESSIONS
            assert "session-0" not in _MODELS
            assert "session-0" not in _PROVIDERS


# ---------------------------------------------------------------------------
# 7. _on_session_end() hook
# ---------------------------------------------------------------------------

class TestSessionEnd:
    """Test _on_session_end() hook callback."""

    def test_on_session_end_removes_state(self):
        """Removes session + model + provider state."""
        from __init__ import (
            _on_session_end, _cleanup_session,
            _SessionTPS, _ModelTPS, _ProviderTPS,
            _SESSIONS, _MODELS, _PROVIDERS, _STATE_LOCK,
        )
        with _STATE_LOCK:
            _SESSIONS["s1"] = _SessionTPS()
            _MODELS["s1"] = {"m1": _ModelTPS()}
            _PROVIDERS["s1"] = {"p1": _ProviderTPS()}
        _on_session_end(session_id="s1")
        with _STATE_LOCK:
            assert "s1" not in _SESSIONS
            assert "s1" not in _MODELS
            assert "s1" not in _PROVIDERS

    def test_on_session_end_no_session_id(self):
        """Handles missing session_id gracefully (no crash)."""
        from __init__ import _on_session_end
        # Should not raise
        _on_session_end()
        _on_session_end(session_id="")
        _on_session_end(session_id=None)


# ---------------------------------------------------------------------------
# 8. Status bar snapshot
# ---------------------------------------------------------------------------

class TestStatusBarSnapshot:
    """Test status bar snapshot construction in _on_post_api_request."""

    def test_snapshot_basic_fields(self):
        """Snapshot contains all expected base fields."""
        from __init__ import _on_post_api_request
        mock_cli = MagicMock()
        mock_cli.agent._tps_snapshot = {}
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="s1", model="openai/gpt-4o",
                usage={"output_tokens": 200, "input_tokens": 100}, api_duration=2.0,
            )
        snap = mock_cli.agent._tps_snapshot
        for key in ("last_tps", "avg_tps", "peak_tps", "output_tokens", "input_tokens", "total_tokens"):
            assert key in snap, f"Missing snapshot key: {key}"

    def test_snapshot_includes_models(self):
        """Snapshot includes models dict when model data exists."""
        from __init__ import _on_post_api_request
        mock_cli = MagicMock()
        mock_cli.agent._tps_snapshot = {}
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="s1", model="openai/gpt-4o",
                usage={"output_tokens": 100, "input_tokens": 50}, api_duration=1.0,
            )
        snap = mock_cli.agent._tps_snapshot
        assert "models" in snap
        assert "openai/gpt-4o" in snap["models"]

    def test_snapshot_includes_providers(self):
        """Snapshot includes providers dict when provider data exists."""
        from __init__ import _on_post_api_request
        mock_cli = MagicMock()
        mock_cli.agent._tps_snapshot = {}
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="s1", model="anthropic/claude-sonnet-4",
                usage={"output_tokens": 100, "input_tokens": 50}, api_duration=1.0,
            )
        snap = mock_cli.agent._tps_snapshot
        assert "providers" in snap
        assert "anthropic" in snap["providers"]


# ---------------------------------------------------------------------------
# 9. Persistence integration
# ---------------------------------------------------------------------------

class TestPersistenceIntegration:
    """Test _hydrate_from_db and _persist_state with real store."""

    def test_persist_state_writes_to_store(self, temp_db):
        """_persist_state calls store.save() and data is retrievable."""
        import __init__ as plugin
        from __init__ import _persist_state, _SessionTPS
        plugin._STORE = temp_db
        s = _SessionTPS()
        s.record(output_tokens=300, duration=3.0, input_tokens=100)
        _persist_state("persist-test", s)
        # Verify it was written
        data = temp_db.load("persist-test")
        assert data is not None
        assert data["call_count"] == 1
        assert data["total_output_tokens"] == 300

    def test_hydrate_from_db_loads_state(self, temp_db):
        """_hydrate_from_db returns _SessionTPS with correct fields."""
        import __init__ as plugin
        from __init__ import _hydrate_from_db, _persist_state, _SessionTPS
        plugin._STORE = temp_db
        s = _SessionTPS()
        s.record(output_tokens=500, duration=5.0, input_tokens=200)
        _persist_state("hydrate-test", s)
        loaded = _hydrate_from_db("hydrate-test")
        assert loaded is not None
        assert loaded.call_count == 1
        assert loaded.total_output_tokens == 500
        assert loaded.total_input_tokens == 200
        assert loaded.total_duration == 5.0
        assert loaded.peak_tps == 100.0

    def test_hydrate_from_db_returns_none_when_absent(self, temp_db):
        """Returns None for unknown session."""
        import __init__ as plugin
        from __init__ import _hydrate_from_db
        plugin._STORE = temp_db
        assert _hydrate_from_db("nonexistent") is None


# ---------------------------------------------------------------------------
# 10. Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    """Test that concurrent hooks don't corrupt state."""

    def test_concurrent_hooks_produce_correct_totals(self):
        """Multiple threads calling _on_post_api_request produce correct totals."""
        from __init__ import (
            _on_post_api_request, _SESSIONS, _STATE_LOCK, get_tps_stats,
        )
        mock_cli = MagicMock()
        mock_cli.agent._tps_snapshot = {}
        n_threads = 10
        tokens_per_call = 100
        barrier = threading.Barrier(n_threads)

        def worker(thread_id):
            barrier.wait()
            with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
                _on_post_api_request(
                    session_id="shared-session",
                    model="openai/gpt-4o",
                    usage={"output_tokens": tokens_per_call, "input_tokens": 50},
                    api_duration=1.0,
                )

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = get_tps_stats("shared-session")
        assert stats["calls"] == n_threads
        assert stats["total_output_tokens"] == n_threads * tokens_per_call


# ---------------------------------------------------------------------------
# 11. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases: zero tokens, zero duration, missing session_id."""

    def test_hook_returns_early_for_missing_session_id(self):
        """Hook returns early when session_id is missing."""
        from __init__ import _on_post_api_request, _SESSIONS, _STATE_LOCK
        mock_cli = MagicMock()
        mock_cli.agent._tps_snapshot = {}
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="",
                model="openai/gpt-4o",
                usage={"output_tokens": 100, "input_tokens": 50},
                api_duration=1.0,
            )
        with _STATE_LOCK:
            assert len(_SESSIONS) == 0

    def test_hook_returns_early_for_zero_tokens(self):
        """Hook returns early when output_tokens is 0."""
        from __init__ import _on_post_api_request, _SESSIONS, _STATE_LOCK
        mock_cli = MagicMock()
        mock_cli.agent._tps_snapshot = {}
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="s1",
                model="openai/gpt-4o",
                usage={"output_tokens": 0, "input_tokens": 50},
                api_duration=1.0,
            )
        with _STATE_LOCK:
            assert len(_SESSIONS) == 0

    def test_hook_returns_early_for_zero_duration(self):
        """Hook returns early when api_duration is 0."""
        from __init__ import _on_post_api_request, _SESSIONS, _STATE_LOCK
        mock_cli = MagicMock()
        mock_cli.agent._tps_snapshot = {}
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="s1",
                model="openai/gpt-4o",
                usage={"output_tokens": 100, "input_tokens": 50},
                api_duration=0.0,
            )
        with _STATE_LOCK:
            assert len(_SESSIONS) == 0

    def test_hook_handles_none_usage(self):
        """Hook handles None usage dict gracefully."""
        from __init__ import _on_post_api_request, _SESSIONS, _STATE_LOCK
        mock_cli = MagicMock()
        mock_cli.agent._tps_snapshot = {}
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="s1",
                model="openai/gpt-4o",
                usage=None,
                api_duration=1.0,
            )
        with _STATE_LOCK:
            assert len(_SESSIONS) == 0
