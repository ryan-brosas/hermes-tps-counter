"""Tests for _on_post_api_request hook callback."""
from unittest.mock import MagicMock, patch

import pytest

from __init__ import _on_post_api_request, _get_session, _SESSIONS, _STATE_LOCK


@pytest.fixture(autouse=True)
def clear_sessions():
    """Reset global state between tests."""
    with _STATE_LOCK:
        _SESSIONS.clear()
    yield
    with _STATE_LOCK:
        _SESSIONS.clear()


class TestHookValid:
    def test_valid_kwargs_records_tps(self):
        _on_post_api_request(
            session_id="s1",
            usage={"output_tokens": 100},
            api_duration=2.0,
        )
        state = _get_session("s1")
        assert state.call_count == 1
        assert state.total_output_tokens == 100
        assert state.last_call_tps == 50.0

    def test_injects_tps_snapshot_on_agent(self):
        import time as _time
        mock_agent = MagicMock()
        mock_cli = MagicMock()
        mock_cli.agent = mock_agent

        with patch.dict("sys.modules", {"hermes_cli": MagicMock(_ACTIVE_CLI_INSTANCE=mock_cli)}):
            _on_post_api_request(
                session_id="s2",
                usage={"output_tokens": 200},
                api_duration=4.0,
            )

        assert hasattr(mock_agent, "_tps_snapshot")
        snap = mock_agent._tps_snapshot
        assert snap["last_tps"] == 50.0
        assert snap["avg_tps"] == 50.0
        assert snap["peak_tps"] == 50.0
        assert snap["output_tokens"] == 200
        # Freshness metadata assertions
        assert isinstance(snap["updated_at"], float)
        assert abs(snap["updated_at"] - _time.time()) < 1.0
        assert isinstance(snap["updated_monotonic"], float)
        assert abs(snap["updated_monotonic"] - _time.monotonic()) < 1.0
        assert snap["session_id"] == "s2"

    def test_snapshot_session_id_changes_on_new_call(self):
        """Snapshot session_id reflects the most recent hook call."""
        import time as _time
        mock_agent = MagicMock()
        mock_cli = MagicMock()
        mock_cli.agent = mock_agent

        with patch.dict("sys.modules", {"hermes_cli": MagicMock(_ACTIVE_CLI_INSTANCE=mock_cli)}):
            _on_post_api_request(
                session_id="alpha",
                usage={"output_tokens": 100},
                api_duration=2.0,
            )
            snap_first = mock_agent._tps_snapshot
            assert snap_first["session_id"] == "alpha"

            _on_post_api_request(
                session_id="beta",
                usage={"output_tokens": 150},
                api_duration=3.0,
            )
            snap_second = mock_agent._tps_snapshot
            assert snap_second["session_id"] == "beta"
            # Freshness timestamp should be newer than first call
            assert snap_second["updated_monotonic"] >= snap_first["updated_monotonic"]


class TestHookEdgeCases:
    def test_missing_session_id_noop(self):
        _on_post_api_request(usage={"output_tokens": 100}, api_duration=2.0)
        assert len(_SESSIONS) == 0

    def test_empty_session_id_noop(self):
        _on_post_api_request(session_id="", usage={"output_tokens": 100}, api_duration=2.0)
        assert len(_SESSIONS) == 0

    def test_zero_output_tokens_noop(self):
        _on_post_api_request(session_id="s1", usage={"output_tokens": 0}, api_duration=2.0)
        assert len(_SESSIONS) == 0

    def test_zero_duration_noop(self):
        _on_post_api_request(session_id="s1", usage={"output_tokens": 100}, api_duration=0.0)
        assert len(_SESSIONS) == 0

    def test_empty_usage_dict_noop(self):
        _on_post_api_request(session_id="s1", usage={}, api_duration=2.0)
        assert len(_SESSIONS) == 0

    def test_non_dict_usage_noop(self):
        _on_post_api_request(session_id="s1", usage="not a dict", api_duration=2.0)
        assert len(_SESSIONS) == 0

    def test_no_usage_kwarg_noop(self):
        _on_post_api_request(session_id="s1", api_duration=2.0)
        assert len(_SESSIONS) == 0

    def test_no_api_duration_noop(self):
        _on_post_api_request(session_id="s1", usage={"output_tokens": 100})
        assert len(_SESSIONS) == 0

    def test_negative_duration_noop(self):
        _on_post_api_request(session_id="s1", usage={"output_tokens": 100}, api_duration=-1.0)
        assert len(_SESSIONS) == 0


class TestHookImportFailure:
    def test_hermes_cli_import_failure_graceful(self):
        """Hook should not raise even if hermes_cli import fails."""
        import sys
        # Remove hermes_cli from sys.modules if present, and block its import
        original = sys.modules.get("hermes_cli")
        sys.modules["hermes_cli"] = None  # type: ignore[assignment]
        try:
            # Should not raise
            _on_post_api_request(
                session_id="s3",
                usage={"output_tokens": 100},
                api_duration=2.0,
            )
            state = _get_session("s3")
            assert state.call_count == 1
        finally:
            if original is not None:
                sys.modules["hermes_cli"] = original
            else:
                sys.modules.pop("hermes_cli", None)


class TestHookMultipleCalls:
    def test_multiple_calls_accumulate(self):
        _on_post_api_request(session_id="s1", usage={"output_tokens": 100}, api_duration=2.0)
        _on_post_api_request(session_id="s1", usage={"output_tokens": 200}, api_duration=4.0)
        state = _get_session("s1")
        assert state.call_count == 2
        assert state.total_output_tokens == 300
        assert state.total_duration == 6.0
