"""Tests for provider-level TPS aggregation."""
from __future__ import annotations

import os
import sys
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


class TestExtractProvider:
    """Test _extract_provider with various model string formats."""

    def test_openai_model(self):
        from __init__ import _extract_provider
        assert _extract_provider("openai/gpt-4o") == "openai"

    def test_anthropic_model(self):
        from __init__ import _extract_provider
        assert _extract_provider("anthropic/claude-sonnet-4") == "anthropic"

    def test_google_model(self):
        from __init__ import _extract_provider
        assert _extract_provider("google/gemini-pro") == "google"

    def test_no_slash_returns_default(self):
        from __init__ import _extract_provider
        assert _extract_provider("gpt-4") == "default"

    def test_empty_string_returns_default(self):
        from __init__ import _extract_provider
        assert _extract_provider("") == "default"

    def test_multiple_slashes(self):
        from __init__ import _extract_provider
        assert _extract_provider("openai/gpt-4/turbo") == "openai"

    def test_slash_only(self):
        from __init__ import _extract_provider
        assert _extract_provider("/") == ""


class TestProviderTPS:
    """Test _ProviderTPS class behavior."""

    def test_initial_state(self):
        from __init__ import _ProviderTPS
        p = _ProviderTPS()
        assert p.call_count == 0
        assert p.total_output_tokens == 0
        assert p.total_duration == 0.0
        assert p.peak_tps == 0.0
        assert p.avg_tps == 0.0

    def test_record_single_call(self):
        from __init__ import _ProviderTPS
        p = _ProviderTPS()
        p.record(100, 2.0)
        assert p.call_count == 1
        assert p.total_output_tokens == 100
        assert p.total_duration == 2.0
        assert p.avg_tps == 50.0
        assert p.peak_tps == 50.0

    def test_record_multiple_calls(self):
        from __init__ import _ProviderTPS
        p = _ProviderTPS()
        p.record(100, 2.0)  # 50 tps
        p.record(200, 2.0)  # 100 tps
        assert p.call_count == 2
        assert p.total_output_tokens == 300
        assert p.total_duration == 4.0
        assert p.avg_tps == 75.0
        assert p.peak_tps == 100.0

    def test_record_zero_duration(self):
        from __init__ import _ProviderTPS
        p = _ProviderTPS()
        p.record(100, 0.0)
        assert p.call_count == 1
        assert p.avg_tps == 0.0
        assert p.peak_tps == 0.0


class TestGetProvider:
    """Test _get_provider helper."""

    def test_creates_new_provider(self):
        from __init__ import _get_provider, _PROVIDERS, _STATE_LOCK
        with _STATE_LOCK:
            _PROVIDERS.clear()
            p = _get_provider("session1", "openai")
            assert p.call_count == 0
            assert "session1" in _PROVIDERS
            assert "openai" in _PROVIDERS["session1"]
            _PROVIDERS.clear()

    def test_returns_existing_provider(self):
        from __init__ import _get_provider, _PROVIDERS, _STATE_LOCK
        with _STATE_LOCK:
            _PROVIDERS.clear()
            p1 = _get_provider("session1", "openai")
            p1.record(100, 1.0)
            p2 = _get_provider("session1", "openai")
            assert p2 is p1
            assert p2.call_count == 1
            _PROVIDERS.clear()

    def test_multiple_providers(self):
        from __init__ import _get_provider, _PROVIDERS, _STATE_LOCK
        with _STATE_LOCK:
            _PROVIDERS.clear()
            p1 = _get_provider("session1", "openai")
            p2 = _get_provider("session1", "anthropic")
            assert p1 is not p2
            _PROVIDERS.clear()


class TestGetProviderStats:
    """Test get_provider_stats public API."""

    def test_empty_session(self):
        from __init__ import get_provider_stats
        result = get_provider_stats("nonexistent")
        assert result == {}

    def test_returns_correct_structure(self):
        from __init__ import _PROVIDERS, _ProviderTPS, _STATE_LOCK, get_provider_stats
        with _STATE_LOCK:
            _PROVIDERS.clear()
            p = _ProviderTPS()
            p.record(200, 2.0)
            _PROVIDERS["session1"] = {"openai": p}

        result = get_provider_stats("session1")
        assert "openai" in result
        assert result["openai"]["avg_tps"] == 100.0
        assert result["openai"]["peak_tps"] == 100.0
        assert result["openai"]["calls"] == 1
        assert result["openai"]["total_output_tokens"] == 200
        assert result["openai"]["total_duration"] == 2.0

        with _STATE_LOCK:
            _PROVIDERS.clear()


class TestProviderIntegration:
    """Test provider tracking via the hook."""

    def _make_cli_mock(self):
        cli = MagicMock()
        cli.agent = MagicMock()
        cli.agent._tps_snapshot = {}
        return cli

    def test_hook_records_provider(self):
        from __init__ import (
            _on_post_api_request,
            _SESSIONS,
            _PROVIDERS,
            _STATE_LOCK,
            get_provider_stats,
        )
        with _STATE_LOCK:
            _SESSIONS.clear()
            _PROVIDERS.clear()

        mock_cli = self._make_cli_mock()
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="test-session",
                model="openai/gpt-4o",
                usage={"output_tokens": 100, "input_tokens": 50},
                api_duration=1.0,
            )

        stats = get_provider_stats("test-session")
        assert "openai" in stats
        assert stats["openai"]["calls"] == 1
        assert stats["openai"]["total_output_tokens"] == 100

        with _STATE_LOCK:
            _SESSIONS.clear()
            _PROVIDERS.clear()

    def test_hook_default_provider(self):
        from __init__ import (
            _on_post_api_request,
            _SESSIONS,
            _PROVIDERS,
            _STATE_LOCK,
            get_provider_stats,
        )
        with _STATE_LOCK:
            _SESSIONS.clear()
            _PROVIDERS.clear()

        mock_cli = self._make_cli_mock()
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="test-session",
                model="gpt-4",
                usage={"completion_tokens": 200, "prompt_tokens": 100},
                api_duration=2.0,
            )

        stats = get_provider_stats("test-session")
        assert "default" in stats
        assert stats["default"]["calls"] == 1

        with _STATE_LOCK:
            _SESSIONS.clear()
            _PROVIDERS.clear()

    def test_snapshot_includes_providers(self):
        from __init__ import (
            _on_post_api_request,
            _SESSIONS,
            _PROVIDERS,
            _STATE_LOCK,
        )
        with _STATE_LOCK:
            _SESSIONS.clear()
            _PROVIDERS.clear()

        mock_cli = self._make_cli_mock()
        with patch("hermes_cli._ACTIVE_CLI_INSTANCE", mock_cli):
            _on_post_api_request(
                session_id="test-session",
                model="anthropic/claude-sonnet-4",
                usage={"output_tokens": 300, "input_tokens": 100},
                api_duration=3.0,
            )

        snapshot = mock_cli.agent._tps_snapshot
        assert "providers" in snapshot
        assert "anthropic" in snapshot["providers"]
        assert snapshot["providers"]["anthropic"]["calls"] == 1

        with _STATE_LOCK:
            _SESSIONS.clear()
            _PROVIDERS.clear()


class TestCleanupSession:
    """Test that _cleanup_session removes provider state."""

    def test_cleanup_removes_providers(self):
        from __init__ import (
            _cleanup_session,
            _SESSIONS,
            _PROVIDERS,
            _ProviderTPS,
            _SessionTPS,
            _STATE_LOCK,
        )
        with _STATE_LOCK:
            _SESSIONS.clear()
            _PROVIDERS.clear()
            _SESSIONS["session1"] = _SessionTPS()
            p = _ProviderTPS()
            p.record(100, 1.0)
            _PROVIDERS["session1"] = {"openai": p}

        _cleanup_session("session1")

        with _STATE_LOCK:
            assert "session1" not in _SESSIONS
            assert "session1" not in _PROVIDERS
            _SESSIONS.clear()
            _PROVIDERS.clear()
