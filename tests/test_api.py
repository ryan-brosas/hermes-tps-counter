"""Tests for public API: get_tps_stats and register."""
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from __init__ import get_tps_stats, register, _SessionTPS, _SESSIONS, _STATE_LOCK


@pytest.fixture(autouse=True)
def mock_hermes_cli():
    """Mock hermes_cli for plugin import compatibility."""
    mod = types.ModuleType("hermes_cli")
    mod._ACTIVE_CLI_INSTANCE = None
    with patch.dict(sys.modules, {"hermes_cli": mod}):
        yield


@pytest.fixture(autouse=True)
def clear_sessions():
    """Reset global state between tests."""
    with _STATE_LOCK:
        _SESSIONS.clear()
    yield
    with _STATE_LOCK:
        _SESSIONS.clear()


class TestGetTPSStatsExisting:
    def test_returns_correct_data(self):
        with _STATE_LOCK:
            s = _SessionTPS()
            s.record(100, 1.0)
            s.record(200, 2.0)
            _SESSIONS["test-session"] = s

        stats = get_tps_stats("test-session")
        assert stats["calls"] == 2
        assert stats["avg_tps"] == 100.0  # 300 / 3
        assert stats["last_tps"] == 100.0  # 200 / 2
        assert stats["peak_tps"] == 100.0
        assert stats["total_output_tokens"] == 300
        assert stats["total_duration"] == 3.0


class TestGetTPSStatsNonExisting:
    def test_returns_zeros(self):
        stats = get_tps_stats("nonexistent")
        assert stats["calls"] == 0
        assert stats["avg_tps"] == 0
        assert stats["last_tps"] == 0
        assert stats["peak_tps"] == 0
        assert stats["total_output_tokens"] == 0


class TestGetTPSStatsKeys:
    def test_returns_all_expected_keys(self):
        stats = get_tps_stats("any")
        expected_keys = {"calls", "avg_tps", "last_tps", "peak_tps", "total_output_tokens"}
        assert expected_keys.issubset(stats.keys())

    def test_existing_session_includes_duration(self):
        with _STATE_LOCK:
            s = _SessionTPS()
            s.record(50, 0.5)
            _SESSIONS["dur-test"] = s

        stats = get_tps_stats("dur-test")
        assert "total_duration" in stats


class TestRegister:
    def test_register_calls_ctx(self):
        mock_ctx = MagicMock()
        register(mock_ctx)
        mock_ctx.register_hook.assert_called_once()
        args = mock_ctx.register_hook.call_args[0]
        assert args[0] == "post_api_request"
        assert callable(args[1])

    def test_hook_name_is_post_api_request(self):
        mock_ctx = MagicMock()
        register(mock_ctx)
        hook_name = mock_ctx.register_hook.call_args[0][0]
        assert hook_name == "post_api_request"
