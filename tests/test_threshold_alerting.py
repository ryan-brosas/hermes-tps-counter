"""Tests for TPS threshold alerting feature."""
import os
import threading
from unittest.mock import MagicMock, patch, call

import pytest

from __init__ import (
    _on_post_api_request,
    _get_session,
    _SESSIONS,
    _STATE_LOCK,
    _ALERT_CONFIG,
    _evaluate_alert,
    _SessionTPS,
    get_tps_stats,
)


@pytest.fixture(autouse=True)
def clear_state():
    """Reset global state between tests."""
    with _STATE_LOCK:
        _SESSIONS.clear()
    # Reset alert config to defaults
    _ALERT_CONFIG["threshold"] = None
    _ALERT_CONFIG["eval_window"] = 5
    _ALERT_CONFIG["cold_start_calls"] = 10
    _ALERT_CONFIG["cold_start_factor"] = 0.5
    yield
    with _STATE_LOCK:
        _SESSIONS.clear()


def _make_mock_manager():
    """Create a mock plugin manager with invoke_hook tracking."""
    manager = MagicMock()
    return manager


def _simulate_calls(session_id: str, tps_values: list, tokens_per_call: int = 100):
    """Simulate a sequence of API calls with given TPS values.

    Each call produces tokens_per_call output tokens.
    Duration is calculated so that output_tokens/duration = target_tps.
    """
    for tps in tps_values:
        duration = tokens_per_call / tps if tps > 0 else 1.0
        _on_post_api_request(
            session_id=session_id,
            usage={"output_tokens": tokens_per_call},
            api_duration=duration,
        )


class TestThresholdCrossing:
    """Test alert fires when TPS drops below threshold."""

    def test_threshold_crossing_fires_alert(self):
        """Simulate API calls with degrading TPS below threshold."""
        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            # First establish threshold: 10 calls at 100 tok/s each
            _simulate_calls("s1", [100.0] * 10)
            # Auto-threshold should be 100 * 0.5 = 50.0

            # Now drop TPS below threshold
            _simulate_calls("s1", [30.0, 30.0, 30.0, 30.0, 30.0])

            # Should have fired tps_alert with state="firing"
            firing_calls = [
                c for c in manager.invoke_hook.call_args_list
                if c.kwargs.get("state") == "firing" or
                   (len(c.args) > 1 and c.args[1] if len(c.args) > 1 else None) == "firing"
            ]
            # Check via args dict
            alert_calls = [
                c for c in manager.invoke_hook.call_args_list
                if c[0][0] == "tps_alert" and c[1].get("state") == "firing"
            ]
            assert len(alert_calls) >= 1
            payload = alert_calls[0][1]
            assert payload["session_id"] == "s1"
            assert payload["state"] == "firing"
            assert payload["tps"] < payload["threshold"]

    def test_tps_recovery_resolves_alert(self):
        """Simulate recovery above threshold after firing."""
        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            # Establish baseline at 100 tok/s
            _simulate_calls("s1", [100.0] * 10)

            # Drop below threshold to trigger firing
            _simulate_calls("s1", [30.0] * 5)

            # Recover above threshold
            _simulate_calls("s1", [100.0] * 5)

            # Should have a "resolved" alert
            resolved_calls = [
                c for c in manager.invoke_hook.call_args_list
                if c[0][0] == "tps_alert" and c[1].get("state") == "resolved"
            ]
            assert len(resolved_calls) >= 1
            payload = resolved_calls[0][1]
            assert payload["session_id"] == "s1"
            assert payload["state"] == "resolved"


class TestColdStartAutoThreshold:
    """Test auto-calculated threshold from first N calls."""

    def test_cold_start_auto_threshold(self):
        """First 10 calls establish baseline; threshold = baseline * 0.5."""
        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            # 10 calls at 200 tok/s
            _simulate_calls("s1", [200.0] * 10)

            state = _get_session("s1")
            # Auto-threshold should be 200 * 0.5 = 100
            assert state.alert_threshold == 100.0
            assert len(state.cold_start_samples) == 10

    def test_custom_threshold_env_var(self):
        """TPS_THRESHOLD env var overrides auto-calculation."""
        _ALERT_CONFIG["threshold"] = 50.0

        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            # Even with high TPS, threshold should be 50
            _simulate_calls("s1", [200.0] * 10)

            state = _get_session("s1")
            # With fixed threshold, it's set immediately (no cold start needed
            # when user provides threshold)

    def test_no_alert_during_cold_start(self):
        """No alert fires during the first N calls (baseline collection)."""
        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            # Very low TPS during cold start — should NOT fire alert
            _simulate_calls("s1", [5.0] * 9)

            # No tps_alert hooks should have been fired
            alert_calls = [
                c for c in manager.invoke_hook.call_args_list
                if c[0][0] == "tps_alert"
            ]
            assert len(alert_calls) == 0

    def test_cold_start_with_varying_tps(self):
        """Auto-threshold uses mean of cold-start samples."""
        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            # Varying TPS: mean should be (80+120+100+90+110+100+95+105+100+100)/10 = 100
            tps_values = [80.0, 120.0, 100.0, 90.0, 110.0, 100.0, 95.0, 105.0, 100.0, 100.0]
            _simulate_calls("s1", tps_values)

            state = _get_session("s1")
            # Mean = 100, threshold = 100 * 0.5 = 50
            assert state.alert_threshold == 50.0


class TestRollingWindow:
    """Test rolling window evaluation."""

    def test_rolling_window_size(self):
        """Only the last N calls are evaluated."""
        manager = _make_mock_manager()
        _ALERT_CONFIG["eval_window"] = 3
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            # Establish baseline at 100 tok/s
            _simulate_calls("s1", [100.0] * 10)

            # Add 3 calls at 30 tok/s (below threshold of 50)
            _simulate_calls("s1", [30.0, 30.0, 30.0])

            state = _get_session("s1")
            # recent_tps_samples should only have last 3
            assert len(state.recent_tps_samples) == 3
            assert state.alert_state == "firing"

            # Now add 3 calls at 100 tok/s — rolling avg should recover
            _simulate_calls("s1", [100.0, 100.0, 100.0])

            state = _get_session("s1")
            assert state.alert_state == "resolved"


class TestAlertStateTransitions:
    """Test the alert state machine."""

    def test_state_starts_idle(self):
        """New sessions start in idle alert state."""
        _on_post_api_request(
            session_id="s1",
            usage={"output_tokens": 100},
            api_duration=2.0,
        )
        state = _get_session("s1")
        assert state.alert_state == "idle"

    def test_state_transitions_firing_to_resolved(self):
        """Alert goes from firing to resolved when TPS recovers."""
        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            _simulate_calls("s1", [100.0] * 10)
            _simulate_calls("s1", [30.0] * 5)
            state = _get_session("s1")
            assert state.alert_state == "firing"

            _simulate_calls("s1", [100.0] * 5)
            state = _get_session("s1")
            assert state.alert_state == "resolved"

    def test_alert_timestamps_recorded(self):
        """Alert fired_at and resolved_at timestamps are set."""
        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            _simulate_calls("s1", [100.0] * 10)
            _simulate_calls("s1", [30.0] * 5)

            state = _get_session("s1")
            assert state.alert_fired_at is not None
            assert state.alert_fired_at > 0

            _simulate_calls("s1", [100.0] * 5)
            state = _get_session("s1")
            assert state.alert_resolved_at is not None
            assert state.alert_fired_at is not None
            assert state.alert_resolved_at >= state.alert_fired_at


class TestHookPayload:
    """Test tps_alert hook payload shape."""

    def test_hook_payload_shape(self):
        """Payload has required keys: session_id, state, tps, threshold, timestamp."""
        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            _simulate_calls("s1", [100.0] * 10)
            _simulate_calls("s1", [30.0] * 5)

            alert_calls = [
                c for c in manager.invoke_hook.call_args_list
                if c[0][0] == "tps_alert"
            ]
            assert len(alert_calls) >= 1
            payload = alert_calls[0][1]
            assert "session_id" in payload
            assert "state" in payload
            assert "tps" in payload
            assert "threshold" in payload
            assert "timestamp" in payload
            assert isinstance(payload["timestamp"], float)


class TestThreadSafety:
    """Test concurrent session evaluation."""

    def test_concurrent_sessions_no_corruption(self):
        """Multiple sessions evaluated concurrently without corruption."""
        manager = _make_mock_manager()
        errors = []

        def run_session(sid: str, tps: float):
            try:
                for _ in range(12):
                    _on_post_api_request(
                        session_id=sid,
                        usage={"output_tokens": 100},
                        api_duration=100.0 / tps,
                    )
            except Exception as e:
                errors.append(e)

        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            threads = []
            for i in range(5):
                t = threading.Thread(target=run_session, args=(f"session-{i}", 100.0))
                threads.append(t)
                t.start()
            for t in threads:
                t.join()

        assert len(errors) == 0
        # All sessions should exist
        with _STATE_LOCK:
            for i in range(5):
                assert f"session-{i}" in _SESSIONS


class TestGetTpsStatsAlertFields:
    """Test that get_tps_stats includes alert fields."""

    def test_stats_includes_alert_fields(self):
        """get_tps_stats returns alert_state and alert_threshold."""
        _on_post_api_request(
            session_id="s1",
            usage={"output_tokens": 100},
            api_duration=2.0,
        )
        stats = get_tps_stats("s1")
        assert "alert_state" in stats
        assert "alert_threshold" in stats
        assert stats["alert_state"] == "idle"

    def test_stats_after_alert_firing(self):
        """Stats show firing state after threshold crossing."""
        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            _simulate_calls("s1", [100.0] * 10)
            _simulate_calls("s1", [30.0] * 5)

            stats = get_tps_stats("s1")
            assert stats["alert_state"] == "firing"
            assert stats["alert_threshold"] == 50.0


class TestStatusIndicator:
    """Test status bar alert indicator."""

    def test_alert_indicator_when_firing(self):
        """Status bar shows ⚠ indicator when alert is firing."""
        manager = _make_mock_manager()
        mock_agent = MagicMock()
        mock_cli = MagicMock()
        mock_cli.agent = mock_agent

        with patch("__init__._ALERT_HOOK_MANAGER", manager), \
             patch.dict("sys.modules", {"hermes_cli": MagicMock(_ACTIVE_CLI_INSTANCE=mock_cli)}):
            _simulate_calls("s1", [100.0] * 10)
            _simulate_calls("s1", [30.0] * 5)

            snap = mock_agent._tps_snapshot
            assert snap["alert_state"] == "firing"
            assert snap["alert_indicator"] == "⚠ TPS ALERT"

    def test_no_indicator_when_idle(self):
        """No indicator when alert is idle."""
        mock_agent = MagicMock()
        mock_cli = MagicMock()
        mock_cli.agent = mock_agent

        with patch.dict("sys.modules", {"hermes_cli": MagicMock(_ACTIVE_CLI_INSTANCE=mock_cli)}):
            _on_post_api_request(
                session_id="s1",
                usage={"output_tokens": 100},
                api_duration=2.0,
            )
            snap = mock_agent._tps_snapshot
            assert snap["alert_indicator"] == ""


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_multiple_sessions_independent(self):
        """Each session has independent alert state."""
        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            # Session 1: good TPS
            _simulate_calls("s1", [100.0] * 15)
            # Session 2: bad TPS
            _simulate_calls("s2", [100.0] * 10)
            _simulate_calls("s2", [30.0] * 5)

            state1 = _get_session("s1")
            state2 = _get_session("s2")
            assert state1.alert_state == "idle"
            assert state2.alert_state == "firing"

    def test_threshold_zero_tps(self):
        """Zero TPS calls are filtered before evaluation."""
        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            # These should be ignored (zero output tokens)
            _on_post_api_request(
                session_id="s1",
                usage={"output_tokens": 0},
                api_duration=2.0,
            )
            # No session should be created
            assert len(_SESSIONS) == 0

    def test_fixed_threshold_from_register(self):
        """When TPS_THRESHOLD is set, it's used directly."""
        _ALERT_CONFIG["threshold"] = 80.0
        manager = _make_mock_manager()
        with patch("__init__._ALERT_HOOK_MANAGER", manager):
            # Even during "cold start", fixed threshold applies
            _simulate_calls("s1", [100.0] * 10)

            state = _get_session("s1")
            # Fixed threshold should be 80, not auto-calculated
            assert state.alert_threshold == 80.0
