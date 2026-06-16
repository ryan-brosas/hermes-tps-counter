"""Tests for public API: get_tps_stats and register."""
from unittest.mock import MagicMock

import pytest

from __init__ import get_tps_stats, register, _get_session, _SESSIONS, _STATE_LOCK


@pytest.fixture(autouse=True)
def clear_sessions():
    with _STATE_LOCK:
        _SESSIONS.clear()
    yield
    with _STATE_LOCK:
        _SESSIONS.clear()


class TestGetTpsStats:
    def test_nonexistent_session_returns_zeros(self):
        stats = get_tps_stats("no-such-session")
        assert stats["calls"] == 0
        assert stats["avg_tps"] == 0
        assert stats["last_tps"] == 0
        assert stats["peak_tps"] == 0
        assert stats["total_output_tokens"] == 0

    def test_existing_session_returns_data(self):
        state = _get_session("s1")
        state.record(500, 2.0)
        stats = get_tps_stats("s1")
        assert stats["calls"] == 1
        assert stats["avg_tps"] == 250.0
        assert stats["last_tps"] == 250.0
        assert stats["peak_tps"] == 250.0
        assert stats["total_output_tokens"] == 500
        assert stats["total_duration"] == 2.0

    def test_returns_all_expected_keys(self):
        stats = get_tps_stats("any")
        expected_keys = {"calls", "avg_tps", "last_tps", "peak_tps", "total_output_tokens"}
        assert expected_keys.issubset(stats.keys())

    def test_stats_rounded(self):
        state = _get_session("s2")
        state.record(100, 3.0)
        stats = get_tps_stats("s2")
        # avg_tps = 33.333... => rounded to 33.3
        assert stats["avg_tps"] == round(100 / 3.0, 1)
        assert stats["total_duration"] == round(3.0, 2)


class TestRegister:
    def test_register_calls_ctx_register_hook(self):
        ctx = MagicMock()
        register(ctx)
        # post_api_request hook is registered (first call)
        calls = ctx.register_hook.call_args_list
        hook_names = [c[0][0] for c in calls]
        assert "post_api_request" in hook_names
        # tps_alert hook is also registered
        assert "tps_alert" in hook_names

    def test_register_hook_name(self):
        ctx = MagicMock()
        register(ctx)
        first_call = ctx.register_hook.call_args_list[0]
        assert first_call[0][0] == "post_api_request"
