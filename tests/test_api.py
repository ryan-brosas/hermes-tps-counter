"""Tests for public API: get_tps_stats and register."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import __init__ as tps_counter

from __init__ import (
    get_observability_contract,
    get_retention_diagnostics,
    get_tps_stats,
    register,
    _get_session,
    _on_post_api_request,
    _SESSIONS,
    _STATE_LOCK,
)


@pytest.fixture(autouse=True)
def clear_sessions(monkeypatch):
    monkeypatch.delenv("HERMES_TPS_MAX_SESSIONS", raising=False)
    monkeypatch.delenv("HERMES_TPS_SESSION_TTL_SECONDS", raising=False)
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

    def test_stats_read_does_not_create_missing_session(self):
        assert get_tps_stats("missing") == {
            "calls": 0,
            "avg_tps": 0,
            "last_tps": 0,
            "peak_tps": 0,
            "total_output_tokens": 0,
        }
        assert "missing" not in _SESSIONS


class TestSessionRetention:
    def test_default_retention_disabled_preserves_unbounded_behavior(self):
        for i in range(5):
            _on_post_api_request(session_id=f"s{i}", usage={"output_tokens": 10}, api_duration=1.0)

        assert len(_SESSIONS) == 5
        diagnostics = get_retention_diagnostics()
        assert diagnostics["enabled"] is False
        assert diagnostics["max_sessions"]["enabled"] is False
        assert diagnostics["session_ttl_seconds"]["enabled"] is False

    def test_max_sessions_prunes_oldest_and_preserves_current(self, monkeypatch):
        monkeypatch.setenv("HERMES_TPS_MAX_SESSIONS", "2")
        old = _get_session("old")
        old.record(10, 1.0)
        old.last_updated_monotonic = 10.0
        recent = _get_session("recent")
        recent.record(10, 1.0)
        recent.last_updated_monotonic = 20.0

        monkeypatch.setattr(tps_counter.time, "monotonic", lambda: 30.0)
        _on_post_api_request(session_id="current", usage={"output_tokens": 10}, api_duration=1.0)

        assert set(_SESSIONS) == {"recent", "current"}
        assert get_tps_stats("old") == {
            "calls": 0,
            "avg_tps": 0,
            "last_tps": 0,
            "peak_tps": 0,
            "total_output_tokens": 0,
        }
        assert "old" not in _SESSIONS

    def test_session_ttl_prunes_stale_without_real_sleep(self, monkeypatch):
        monkeypatch.setenv("HERMES_TPS_SESSION_TTL_SECONDS", "5")
        stale = _get_session("stale")
        stale.record(10, 1.0)
        stale.last_updated_monotonic = 10.0
        recent = _get_session("recent")
        recent.record(10, 1.0)
        recent.last_updated_monotonic = 27.0

        monkeypatch.setattr(tps_counter.time, "monotonic", lambda: 30.0)
        _on_post_api_request(session_id="current", usage={"output_tokens": 10}, api_duration=1.0)

        assert "stale" not in _SESSIONS
        assert "recent" in _SESSIONS
        assert "current" in _SESSIONS
        assert get_tps_stats("stale") == {
            "calls": 0,
            "avg_tps": 0,
            "last_tps": 0,
            "peak_tps": 0,
            "total_output_tokens": 0,
        }

    @pytest.mark.parametrize(
        "env_name,env_value,diagnostic_key",
        [
            ("HERMES_TPS_MAX_SESSIONS", "", "max_sessions"),
            ("HERMES_TPS_MAX_SESSIONS", "0", "max_sessions"),
            ("HERMES_TPS_MAX_SESSIONS", "-3", "max_sessions"),
            ("HERMES_TPS_MAX_SESSIONS", "not-a-number", "max_sessions"),
            ("HERMES_TPS_SESSION_TTL_SECONDS", "", "session_ttl_seconds"),
            ("HERMES_TPS_SESSION_TTL_SECONDS", "0", "session_ttl_seconds"),
            ("HERMES_TPS_SESSION_TTL_SECONDS", "-1", "session_ttl_seconds"),
            ("HERMES_TPS_SESSION_TTL_SECONDS", "not-a-number", "session_ttl_seconds"),
        ],
    )
    def test_invalid_or_disabled_env_values_do_not_prune(self, monkeypatch, env_name, env_value, diagnostic_key):
        monkeypatch.setenv(env_name, env_value)
        for i in range(4):
            _on_post_api_request(session_id=f"s{i}", usage={"output_tokens": 10}, api_duration=1.0)

        assert len(_SESSIONS) == 4
        diagnostics = get_retention_diagnostics()
        assert diagnostics["enabled"] is False
        assert diagnostics[diagnostic_key]["enabled"] is False


class TestObservabilityContract:
    def test_contract_is_json_serializable_with_required_sections(self):
        contract = get_observability_contract()
        assert isinstance(contract, dict)
        json.dumps(contract, sort_keys=True)
        assert {"contract", "compatibility", "privacy", "retention", "status_snapshot", "api", "websocket", "prometheus"}.issubset(
            contract.keys()
        )

    def test_contract_metadata_matches_plugin_yaml(self):
        contract = get_observability_contract()
        plugin_yaml = Path(__file__).resolve().parents[1] / "plugin.yaml"
        raw_plugin = plugin_yaml.read_text(encoding="utf-8")

        assert contract["contract"]["contract_version"] == "1.0.0"
        assert contract["contract"]["plugin"] == {
            "name": "tps-counter",
            "version": "1.0.0",
        }
        assert "name: tps-counter" in raw_plugin
        assert 'version: "1.0.0"' in raw_plugin
        assert contract["compatibility"]["unknown_fields"] == "ignore"

    def test_status_snapshot_fields_describe_current_snapshot_keys(self):
        fields = get_observability_contract()["status_snapshot"]["fields"]
        expected = {
            "last_tps",
            "avg_tps",
            "peak_tps",
            "output_tokens",
            "updated_at",
            "updated_monotonic",
            "session_id",
        }
        assert expected.issubset(fields.keys())
        assert fields["last_tps"]["unit"] == "tokens_per_second"
        assert fields["output_tokens"]["type"] == "integer"
        assert fields["updated_monotonic"]["unit"] == "monotonic_seconds"
        assert "stale" in get_observability_contract()["status_snapshot"]["freshness_guidance"]["stale_behavior"]
        assert "active session" in fields["session_id"]["semantics"]

    def test_get_tps_stats_surface_metadata_matches_live_behavior(self):
        contract = get_observability_contract()
        surface = contract["api"]["surfaces"]["get_tps_stats"]
        assert surface["available"] is True
        assert surface["call"] == "get_tps_stats(session_id)"
        assert {
            "calls",
            "avg_tps",
            "last_tps",
            "peak_tps",
            "total_output_tokens",
            "total_duration",
        }.issubset(surface["fields"].keys())
        assert surface["fields"]["total_duration"]["unit"] == "seconds"
        assert get_tps_stats("missing") == surface["absent_session_behavior"]["returns"]

    def test_absent_optional_surfaces_are_explicit_and_dependency_free(self):
        contract = get_observability_contract()
        assert contract["api"]["routes"]["observability_contract"]["available"] is False
        assert contract["websocket"]["available"] is False
        assert contract["prometheus"]["available"] is False
        assert contract["prometheus"]["metrics"] == {}
        assert "unbounded labels" in contract["prometheus"]["label_cardinality"]["guidance"]

    def test_contract_read_does_not_create_session_state(self):
        assert _SESSIONS == {}
        get_observability_contract()
        assert _SESSIONS == {}

    def test_contract_exposes_retention_policy_without_identifiers(self, monkeypatch):
        monkeypatch.setenv("HERMES_TPS_MAX_SESSIONS", "7")
        monkeypatch.setenv("HERMES_TPS_SESSION_TTL_SECONDS", "12.5")
        _get_session("raw-session-id").record(10, 1.0)

        contract = get_observability_contract()
        retention = contract["retention"]
        json.dumps(retention, sort_keys=True)

        assert retention["enabled"] is True
        assert retention["configuration"]["max_sessions_env"] == "HERMES_TPS_MAX_SESSIONS"
        assert retention["configuration"]["session_ttl_seconds_env"] == "HERMES_TPS_SESSION_TTL_SECONDS"
        assert retention["max_sessions"] == {"enabled": True, "value": 7, "status": "enabled"}
        assert retention["session_ttl_seconds"] == {"enabled": True, "value": 12.5, "status": "enabled"}
        assert retention["identifier_material_exposed"] is False
        serialized = json.dumps(retention)
        assert "raw-session-id" not in serialized
        assert "secret" not in serialized.lower()


class TestRegister:
    def test_register_calls_ctx_register_hook(self):
        ctx = MagicMock()
        register(ctx)
        ctx.register_hook.assert_called_once_with("post_api_request", pytest.importorskip("__init__")._on_post_api_request)

    def test_register_hook_name(self):
        ctx = MagicMock()
        register(ctx)
        args = ctx.register_hook.call_args
        assert args[0][0] == "post_api_request"
