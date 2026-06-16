"""Tests for _on_post_api_request hook callback."""
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from __init__ import _on_post_api_request, _SESSIONS, _STATE_LOCK


def _make_mock_hermes_cli():
    """Create a fresh mock hermes_cli module."""
    mod = types.ModuleType("hermes_cli")
    mod._ACTIVE_CLI_INSTANCE = None
    return mod


@pytest.fixture(autouse=True)
def mock_hermes_cli():
    """Mock hermes_cli module for all tests in this file."""
    mod = _make_mock_hermes_cli()
    with patch.dict(sys.modules, {"hermes_cli": mod}):
        yield mod


@pytest.fixture(autouse=True)
def clear_sessions(mock_hermes_cli):
    """Reset global state between tests."""
    with _STATE_LOCK:
        _SESSIONS.clear()
    yield
    with _STATE_LOCK:
        _SESSIONS.clear()


class TestHookValidCall:
    def test_records_tps(self):
        _on_post_api_request(
            session_id="s1",
            usage={"output_tokens": 100},
            api_duration=2.0,
        )
        with _STATE_LOCK:
            state = _SESSIONS.get("s1")
        assert state is not None
        assert state.call_count == 1
        assert state.total_output_tokens == 100
        assert state.total_duration == 2.0

    def test_injects_tps_snapshot_on_agent(self, mock_hermes_cli):
        class FakeAgent:
            pass

        class FakeCLI:
            agent = FakeAgent()

        fake_cli = FakeCLI()
        mock_hermes_cli._ACTIVE_CLI_INSTANCE = fake_cli

        _on_post_api_request(
            session_id="s2",
            usage={"output_tokens": 200},
            api_duration=1.0,
        )

        assert hasattr(fake_cli.agent, "_tps_snapshot")
        snap = fake_cli.agent._tps_snapshot
        assert snap["last_tps"] == 200.0
        assert snap["avg_tps"] == 200.0
        assert snap["peak_tps"] == 200.0
        assert snap["output_tokens"] == 200


class TestHookMissingSessionId:
    def test_missing_session_id_noop(self):
        _on_post_api_request(usage={"output_tokens": 100}, api_duration=1.0)
        assert len(_SESSIONS) == 0

    def test_empty_session_id_noop(self):
        _on_post_api_request(
            session_id="",
            usage={"output_tokens": 100},
            api_duration=1.0,
        )
        assert len(_SESSIONS) == 0


class TestHookZeroTokens:
    def test_zero_output_tokens_noop(self):
        _on_post_api_request(
            session_id="s3",
            usage={"output_tokens": 0},
            api_duration=1.0,
        )
        assert len(_SESSIONS) == 0


class TestHookZeroDuration:
    def test_zero_duration_noop(self):
        _on_post_api_request(
            session_id="s4",
            usage={"output_tokens": 100},
            api_duration=0.0,
        )
        assert len(_SESSIONS) == 0


class TestHookEmptyUsage:
    def test_empty_usage_dict_noop(self):
        _on_post_api_request(
            session_id="s5",
            usage={},
            api_duration=1.0,
        )
        assert len(_SESSIONS) == 0

    def test_missing_usage_defaults_noop(self):
        _on_post_api_request(session_id="s6", api_duration=1.0)
        assert len(_SESSIONS) == 0


class TestHookNonDictUsage:
    def test_non_dict_usage_noop(self):
        _on_post_api_request(
            session_id="s7",
            usage="not a dict",
            api_duration=1.0,
        )
        assert len(_SESSIONS) == 0

    def test_none_usage_noop(self):
        _on_post_api_request(
            session_id="s8",
            usage=None,
            api_duration=1.0,
        )
        assert len(_SESSIONS) == 0


class TestHookImportFailure:
    def test_hermes_cli_import_error_handled(self):
        """If hermes_cli isn't available, hook still records TPS."""
        # Remove hermes_cli from sys.modules to trigger import error
        with patch.dict(sys.modules, {"hermes_cli": None}):
            _on_post_api_request(
                session_id="s9",
                usage={"output_tokens": 50},
                api_duration=1.0,
            )

        with _STATE_LOCK:
            state = _SESSIONS.get("s9")
        assert state is not None
        assert state.call_count == 1


class TestHookMultipleCalls:
    def test_multiple_calls_accumulate(self):
        _on_post_api_request(
            session_id="s10",
            usage={"output_tokens": 100},
            api_duration=1.0,
        )
        _on_post_api_request(
            session_id="s10",
            usage={"output_tokens": 200},
            api_duration=2.0,
        )
        with _STATE_LOCK:
            state = _SESSIONS["s10"]
        assert state.call_count == 2
        assert state.total_output_tokens == 300
        assert state.total_duration == 3.0


class TestHookApiDurationNone:
    def test_none_api_duration_noop(self):
        _on_post_api_request(
            session_id="s11",
            usage={"output_tokens": 100},
            api_duration=None,
        )
        assert len(_SESSIONS) == 0
