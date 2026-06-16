"""Tests for _extract_usage provider-resilient usage data extraction."""
from __future__ import annotations

import os
import sys
import types
from unittest.mock import patch

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


class TestExtractUsage:
    """Test _extract_usage with various provider formats."""

    def test_anthropic_format(self):
        from __init__ import _extract_usage

        usage = {"input_tokens": 500, "output_tokens": 150}
        inp, out = _extract_usage(usage)
        assert inp == 500
        assert out == 150

    def test_openai_format(self):
        from __init__ import _extract_usage

        usage = {"prompt_tokens": 300, "completion_tokens": 200}
        inp, out = _extract_usage(usage)
        assert inp == 300
        assert out == 200

    def test_google_camel_case_format(self):
        from __init__ import _extract_usage

        usage = {"promptTokens": 400, "completionTokens": 100}
        inp, out = _extract_usage(usage)
        assert inp == 400
        assert out == 100

    def test_empty_dict(self):
        from __init__ import _extract_usage

        inp, out = _extract_usage({})
        assert inp == 0
        assert out == 0

    def test_none_input(self):
        from __init__ import _extract_usage

        inp, out = _extract_usage(None)
        assert inp == 0
        assert out == 0

    def test_string_input(self):
        from __init__ import _extract_usage

        inp, out = _extract_usage("not a dict")
        assert inp == 0
        assert out == 0

    def test_list_input(self):
        from __init__ import _extract_usage

        inp, out = _extract_usage([1, 2, 3])
        assert inp == 0
        assert out == 0

    def test_mixed_keys_openai_takes_precedence(self):
        """When both output_tokens and completion_tokens exist, output_tokens wins."""
        from __init__ import _extract_usage

        usage = {"output_tokens": 100, "completion_tokens": 200}
        _, out = _extract_usage(usage)
        assert out == 100  # output_tokens is checked first

    def test_string_token_values(self):
        """Token values as strings should be parsed."""
        from __init__ import _extract_usage

        usage = {"output_tokens": "150", "input_tokens": "300"}
        inp, out = _extract_usage(usage)
        assert inp == 300
        assert out == 150

    def test_invalid_token_values_skipped(self):
        """Non-numeric token values should be skipped, fallback used."""
        from __init__ import _extract_usage

        usage = {"output_tokens": "bad", "completion_tokens": 200}
        _, out = _extract_usage(usage)
        assert out == 200  # Fell through to completion_tokens

    def test_negative_tokens_clamped_to_zero(self):
        from __init__ import _extract_usage

        usage = {"output_tokens": -10, "input_tokens": 100}
        inp, out = _extract_usage(usage)
        assert out == 0
        assert inp == 100

    def test_zero_tokens_returned(self):
        from __init__ import _extract_usage

        usage = {"output_tokens": 0, "input_tokens": 0}
        inp, out = _extract_usage(usage)
        assert inp == 0
        assert out == 0

    def test_extra_keys_ignored(self):
        """Extra usage keys don't interfere."""
        from __init__ import _extract_usage

        usage = {
            "output_tokens": 150,
            "input_tokens": 500,
            "total_tokens": 650,
            "model": "gpt-4o",
            "cache_creation_input_tokens": 0,
        }
        inp, out = _extract_usage(usage)
        assert inp == 500
        assert out == 150

    def test_only_input_tokens(self):
        """When only input_tokens present, output should be 0."""
        from __init__ import _extract_usage

        usage = {"input_tokens": 100}
        inp, out = _extract_usage(usage)
        assert inp == 100
        assert out == 0

    def test_only_output_tokens(self):
        """When only output_tokens present, input should be 0."""
        from __init__ import _extract_usage

        usage = {"output_tokens": 200}
        inp, out = _extract_usage(usage)
        assert inp == 0
        assert out == 200


class TestExtractUsageIntegration:
    """Test _extract_usage wired into _on_post_api_request."""

    def test_hook_with_openai_format(self):
        import __init__ as plugin

        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()

        plugin._on_post_api_request(
            session_id="openai-test",
            usage={"prompt_tokens": 300, "completion_tokens": 200},
            api_duration=2.0,
        )

        with plugin._STATE_LOCK:
            state = plugin._SESSIONS.get("openai-test")
        assert state is not None
        assert state.total_output_tokens == 200
        assert state.total_input_tokens == 300
        assert state.call_count == 1

        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()

    def test_hook_with_anthropic_format(self):
        import __init__ as plugin

        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()

        plugin._on_post_api_request(
            session_id="anthropic-test",
            usage={"input_tokens": 500, "output_tokens": 150},
            api_duration=1.5,
        )

        with plugin._STATE_LOCK:
            state = plugin._SESSIONS.get("anthropic-test")
        assert state is not None
        assert state.total_output_tokens == 150
        assert state.total_input_tokens == 500

        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()

    def test_hook_with_google_format(self):
        import __init__ as plugin

        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()

        plugin._on_post_api_request(
            session_id="google-test",
            usage={"promptTokens": 400, "completionTokens": 100},
            api_duration=0.8,
        )

        with plugin._STATE_LOCK:
            state = plugin._SESSIONS.get("google-test")
        assert state is not None
        assert state.total_output_tokens == 100
        assert state.total_input_tokens == 400

        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()

    def test_hook_with_empty_usage_returns_early(self):
        import __init__ as plugin

        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()

        plugin._on_post_api_request(
            session_id="empty-test",
            usage={},
            api_duration=1.0,
        )

        with plugin._STATE_LOCK:
            state = plugin._SESSIONS.get("empty-test")
        # Should not create a session when output_tokens is 0
        assert state is None

        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()

    def test_hook_backward_compatible(self):
        """Existing Anthropic format still works as before."""
        import __init__ as plugin

        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()

        plugin._on_post_api_request(
            session_id="compat-test",
            usage={"output_tokens": 100},
            api_duration=1.0,
        )

        with plugin._STATE_LOCK:
            state = plugin._SESSIONS.get("compat-test")
        assert state is not None
        assert state.total_output_tokens == 100
        assert state.total_input_tokens == 0  # No input_tokens in usage

        with plugin._STATE_LOCK:
            plugin._SESSIONS.clear()
