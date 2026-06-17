"""Tests for configurable call-event sampling to bound SQLite write amplification."""
import json
import threading
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def clear_sessions_and_sampling_env(monkeypatch):
    from __init__ import _SESSIONS, _STATE_LOCK, _reset_event_sampling_counters
    with _STATE_LOCK:
        _SESSIONS.clear()
    _reset_event_sampling_counters()
    for name in (
        "HERMES_TPS_EVENT_SAMPLING_MODE",
        "HERMES_TPS_EVENT_SAMPLING_RATE",
    ):
        monkeypatch.delenv(name, raising=False)
    yield
    with _STATE_LOCK:
        _SESSIONS.clear()
    _reset_event_sampling_counters()
    for name in (
        "HERMES_TPS_EVENT_SAMPLING_MODE",
        "HERMES_TPS_EVENT_SAMPLING_RATE",
    ):
        monkeypatch.delenv(name, raising=False)


# --- Default / Backward Compatibility ---

class TestDefaultBehavior:
    def test_default_policy_is_lossless(self):
        from __init__ import _parse_event_sampling_policy
        policy = _parse_event_sampling_policy()
        assert policy.enabled is False
        assert policy.rate == 1.0
        assert policy.should_keep_event() is True

    def test_default_keeps_every_event(self):
        from __init__ import _parse_event_sampling_policy
        policy = _parse_event_sampling_policy()
        for _ in range(100):
            assert policy.should_keep_event() is True

    def test_default_diagnostics(self):
        from __init__ import get_event_sampling_diagnostics
        diag = get_event_sampling_diagnostics()
        assert diag["enabled"] is False
        assert diag["mode"] == "disabled"
        assert diag["rate"] == 1.0
        assert diag["event_history_complete"] is True
        assert diag["events_skipped"] == 0
        assert diag["events_kept"] == 0

    def test_default_contract_metadata(self):
        from __init__ import get_observability_contract
        contract = get_observability_contract()
        sampling = contract["event_sampling"]
        assert sampling["enabled"] is False
        assert sampling["mode"] == "disabled"
        assert sampling["rate"] == 1.0
        assert sampling["event_history_complete"] is True


# --- Configuration Parsing ---

class TestConfigParsing:
    def test_disabled_aliases(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV
        for alias in ("disabled", "off", "false", "0", ""):
            monkeypatch.setenv(_SAMPLING_MODE_ENV, alias)
            policy = _parse_event_sampling_policy()
            assert policy.enabled is False
            assert policy.mode == "disabled"

    def test_enabled_aliases(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV
        for alias in ("enabled", "on", "true", "1"):
            monkeypatch.setenv(_SAMPLING_MODE_ENV, alias)
            policy = _parse_event_sampling_policy()
            assert policy.enabled is True
            assert policy.mode == "cadence"

    def test_cadence_mode_with_rate(self, monkeypatch):
        from __init__ import _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")
        from __init__ import _parse_event_sampling_policy
        policy = _parse_event_sampling_policy()
        assert policy.enabled is True
        assert policy.rate == 0.5

    def test_rate_default_is_one(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        policy = _parse_event_sampling_policy()
        assert policy.rate == 1.0

    def test_rate_one_keeps_all(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "1.0")
        policy = _parse_event_sampling_policy()
        for _ in range(10):
            assert policy.should_keep_event() is True

    def test_rate_zero_keeps_none(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.0")
        policy = _parse_event_sampling_policy()
        for _ in range(10):
            assert policy.should_keep_event() is False

    def test_invalid_rate_too_high(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "1.5")
        with pytest.raises(ValueError, match="sampling rate"):
            _parse_event_sampling_policy()

    def test_invalid_rate_negative(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "-0.1")
        with pytest.raises(ValueError, match="sampling rate"):
            _parse_event_sampling_policy()

    def test_invalid_rate_non_numeric(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "abc")
        with pytest.raises(ValueError, match="sampling rate"):
            _parse_event_sampling_policy()

    def test_invalid_mode_string(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "invalid_mode")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")
        with pytest.raises(ValueError, match="sampling mode"):
            _parse_event_sampling_policy()


# --- Deterministic Sampling ---

class TestDeterministicSampling:
    def test_cadence_keeps_every_nth(self, monkeypatch):
        """With rate 0.5, cadence keeps every 2nd event (0th, 2nd, 4th, ...)."""
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")
        policy = _parse_event_sampling_policy()
        results = [policy.should_keep_event() for _ in range(10)]
        kept_indices = [i for i in range(10) if results[i]]
        assert kept_indices == [0, 2, 4, 6, 8]

    def test_cadence_is_deterministic(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")
        policy1 = _parse_event_sampling_policy()
        results1 = [policy1.should_keep_event() for _ in range(10)]
        policy2 = _parse_event_sampling_policy()
        results2 = [policy2.should_keep_event() for _ in range(10)]
        assert results1 == results2

    def test_cadence_rate_one_fifth(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.2")
        policy = _parse_event_sampling_policy()
        results = [policy.should_keep_event() for _ in range(10)]
        kept = [i for i in range(10) if results[i]]
        assert kept == [0, 5]

    def test_cadence_rate_one_keeps_all(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "1.0")
        policy = _parse_event_sampling_policy()
        for _ in range(20):
            assert policy.should_keep_event() is True

    def test_cadence_rate_zero_keeps_none(self, monkeypatch):
        from __init__ import _parse_event_sampling_policy, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.0")
        policy = _parse_event_sampling_policy()
        for _ in range(20):
            assert policy.should_keep_event() is False


# --- Aggregate vs History Separation ---

class TestAggregateSeparation:
    def test_sampling_does_not_affect_aggregates(self, monkeypatch):
        """Aggregate session counters must count all events even when sampling drops some."""
        from __init__ import _on_post_api_request, get_tps_stats, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")

        for i in range(4):
            _on_post_api_request(
                session_id="s1",
                usage={"output_tokens": 100},
                api_duration=1.0,
                model="test-model",
                provider="test-provider",
            )

        stats = get_tps_stats("s1")
        assert stats["calls"] == 4
        assert stats["total_output_tokens"] == 400
        assert stats["avg_tps"] == 100.0
        assert stats["last_tps"] == 100.0
        assert stats["peak_tps"] == 100.0

    def test_sampling_skips_event_persistence(self, monkeypatch):
        """With cadence at 0.5, only half of events should be 'persisted'."""
        from __init__ import _on_post_api_request, get_event_sampling_diagnostics, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")

        for i in range(4):
            _on_post_api_request(
                session_id="s1",
                usage={"output_tokens": 100},
                api_duration=1.0,
                model="test-model",
                provider="test-provider",
            )

        diag = get_event_sampling_diagnostics()
        assert diag["events_kept"] == 2
        assert diag["events_skipped"] == 2

    def test_disabled_sampling_keeps_all_events(self):
        """With sampling disabled, all events should be kept."""
        from __init__ import _on_post_api_request, get_event_sampling_diagnostics
        for i in range(4):
            _on_post_api_request(
                session_id="s1",
                usage={"output_tokens": 100},
                api_duration=1.0,
                model="test-model",
                provider="test-provider",
            )

        diag = get_event_sampling_diagnostics()
        assert diag["events_kept"] == 4
        assert diag["events_skipped"] == 0


# --- Metadata and Privacy ---

class TestMetadataAndPrivacy:
    def test_diagnostics_are_json_serializable(self, monkeypatch):
        from __init__ import get_event_sampling_diagnostics, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")
        diag = get_event_sampling_diagnostics()
        json.dumps(diag, sort_keys=True)

    def test_diagnostics_no_raw_identifiers(self, monkeypatch):
        from __init__ import _on_post_api_request, get_event_sampling_diagnostics, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")
        for i in range(4):
            _on_post_api_request(
                session_id="s1",
                usage={"output_tokens": 100},
                api_duration=1.0,
                model="raw-model-name",
                provider="raw-provider-name",
            )

        diag = get_event_sampling_diagnostics()
        serialized = json.dumps(diag)
        assert "raw-model-name" not in serialized
        assert "raw-provider-name" not in serialized

    def test_contract_section_is_json_serializable(self, monkeypatch):
        from __init__ import get_observability_contract, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")
        contract = get_observability_contract()
        sampling = contract["event_sampling"]
        json.dumps(sampling, sort_keys=True)

    def test_contract_has_required_fields(self, monkeypatch):
        from __init__ import get_observability_contract, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")
        contract = get_observability_contract()
        sampling = contract["event_sampling"]
        assert "enabled" in sampling
        assert "mode" in sampling
        assert "rate" in sampling
        assert "strategy" in sampling
        assert "event_history_complete" in sampling
        assert "env_vars" in sampling
        assert "aggregate_tps_lossless" in sampling
        assert "notes" in sampling

    def test_contract_cadence_notes(self, monkeypatch):
        from __init__ import get_observability_contract, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")
        contract = get_observability_contract()
        notes = contract["event_sampling"]["notes"]
        assert any("complete" in n for n in notes)
        assert any("aggregate" in n for n in notes)

    def test_contract_cadence_no_raw_identifiers(self, monkeypatch):
        from __init__ import _on_post_api_request, get_observability_contract, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")
        for i in range(4):
            _on_post_api_request(
                session_id="secret-session",
                usage={"output_tokens": 100},
                api_duration=1.0,
                model="secret-model",
                provider="secret-provider",
            )

        contract = get_observability_contract()
        serialized = json.dumps(contract["event_sampling"])
        assert "secret-session" not in serialized
        assert "secret-model" not in serialized
        assert "secret-provider" not in serialized


# --- Thread Safety ---

class TestThreadSafety:
    def test_concurrent_sampling_decisions(self, monkeypatch):
        from __init__ import _on_post_api_request, get_tps_stats, _SAMPLING_MODE_ENV, _SAMPLING_RATE_ENV
        monkeypatch.setenv(_SAMPLING_MODE_ENV, "cadence")
        monkeypatch.setenv(_SAMPLING_RATE_ENV, "0.5")

        n_threads = 20
        barrier = threading.Barrier(n_threads)
        errors = []

        def worker():
            barrier.wait()
            try:
                for _ in range(10):
                    _on_post_api_request(
                        session_id="s1",
                        usage={"output_tokens": 100},
                        api_duration=1.0,
                        model="m",
                        provider="p",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        stats = get_tps_stats("s1")
        assert stats["calls"] == n_threads * 10
