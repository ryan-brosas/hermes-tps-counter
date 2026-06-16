"""Tests for configurable TPS privacy redaction policy."""
import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from __init__ import (
    _SESSIONS,
    _STATE_LOCK,
    _on_post_api_request,
    _redact_identifier,
    _redact_payload,
    get_observability_contract,
    get_privacy_diagnostics,
    get_tps_stats,
)


PRIVACY_ENV = {
    "HERMES_TPS_PRIVACY_MODE": "pseudonymized",
    "HERMES_TPS_PRIVACY_SALT": "unit-test-secret-salt",
    "HERMES_TPS_PRIVACY_SCOPE": "unit-test-scope",
}


@pytest.fixture(autouse=True)
def clear_sessions_and_privacy_env(monkeypatch):
    with _STATE_LOCK:
        _SESSIONS.clear()
    for name in (
        "HERMES_TPS_PRIVACY_MODE",
        "HERMES_TPS_PRIVACY_SALT",
        "HERMES_TPS_PRIVACY_SCOPE",
        "HERMES_TPS_PRIVACY_FIELDS",
        "HERMES_TPS_PRIVACY_TREATMENTS",
    ):
        monkeypatch.delenv(name, raising=False)
    yield
    with _STATE_LOCK:
        _SESSIONS.clear()


def test_disabled_mode_returns_raw_identifiers_by_default():
    assert _redact_identifier("session_id", "raw-session-secret") == "raw-session-secret"
    payload = _redact_payload({"session_id": "raw-session-secret", "last_tps": 10.0})
    assert payload == {"session_id": "raw-session-secret", "last_tps": 10.0}


def test_enabled_pseudonyms_are_deterministic_distinct_and_non_raw(monkeypatch):
    for name, value in PRIVACY_ENV.items():
        monkeypatch.setenv(name, value)

    first = _redact_identifier("session_id", "raw-session-secret")
    second = _redact_identifier("session_id", "raw-session-secret")
    other = _redact_identifier("session_id", "other-session-secret")
    model = _redact_identifier("model", "raw-model-name")
    provider = _redact_identifier("provider", "raw-provider-name")

    assert first == second
    assert first != other
    assert first != model
    assert "raw-session-secret" not in first
    assert "raw-model-name" not in model
    assert "raw-provider-name" not in provider
    assert first.startswith("session_id:pseudonym:")


def test_changing_salt_changes_pseudonym(monkeypatch):
    monkeypatch.setenv("HERMES_TPS_PRIVACY_MODE", "pseudonymized")
    monkeypatch.setenv("HERMES_TPS_PRIVACY_SALT", "first-secret")
    first = _redact_identifier("session_id", "raw-session-secret")
    monkeypatch.setenv("HERMES_TPS_PRIVACY_SALT", "second-secret")
    second = _redact_identifier("session_id", "raw-session-secret")
    assert first != second


def test_enabled_snapshot_and_logs_do_not_emit_raw_identifiers(monkeypatch, caplog):
    for name, value in PRIVACY_ENV.items():
        monkeypatch.setenv(name, value)
    raw_session = "raw-session-secret"
    raw_model = "raw-model-name"
    raw_provider = "raw-provider-name"

    mock_agent = MagicMock()
    mock_cli = MagicMock()
    mock_cli.agent = mock_agent

    caplog.set_level(logging.DEBUG)
    with patch.dict("sys.modules", {"hermes_cli": MagicMock(_ACTIVE_CLI_INSTANCE=mock_cli)}):
        _on_post_api_request(
            session_id=raw_session,
            model=raw_model,
            provider=raw_provider,
            usage={"output_tokens": 200},
            api_duration=4.0,
        )

    snap = mock_agent._tps_snapshot
    serialized_snapshot = json.dumps(snap, sort_keys=True)
    log_text = "\n".join(record.getMessage() for record in caplog.records)

    assert snap["last_tps"] == 50.0
    assert snap["avg_tps"] == 50.0
    assert snap["peak_tps"] == 50.0
    assert snap["output_tokens"] == 200
    assert raw_session not in serialized_snapshot
    assert raw_model not in serialized_snapshot
    assert raw_provider not in serialized_snapshot
    assert raw_session[:8] not in log_text
    assert raw_session not in log_text
    assert raw_model not in log_text
    assert raw_provider not in log_text
    assert snap["session_id"].startswith("session_id:pseudonym:")
    assert snap["model"].startswith("model:pseudonym:")
    assert snap["provider"].startswith("provider:pseudonym:")

    # Raw lookup input still works and counters are unchanged.
    stats = get_tps_stats(raw_session)
    assert stats["calls"] == 1
    assert stats["last_tps"] == 50.0
    assert stats["total_output_tokens"] == 200


def test_contract_and_diagnostics_describe_privacy_without_secret(monkeypatch):
    for name, value in PRIVACY_ENV.items():
        monkeypatch.setenv(name, value)
    contract = get_observability_contract()
    diagnostics = get_privacy_diagnostics()
    serialized = json.dumps({"contract": contract, "diagnostics": diagnostics}, sort_keys=True)

    assert contract["privacy"]["mode"] == "pseudonymized"
    assert contract["privacy"]["field_treatments"]["session_id"] == "pseudonymized"
    assert contract["privacy"]["field_treatments"]["model"] == "pseudonymized"
    assert contract["privacy"]["field_treatments"]["provider"] == "pseudonymized"
    assert contract["status_snapshot"]["fields"]["session_id"]["privacy_treatment"] == "pseudonymized"
    assert contract["api"]["routes"]["observability_contract"]["available"] is False
    assert contract["websocket"]["available"] is False
    assert contract["prometheus"]["available"] is False
    assert "unit-test-secret-salt" not in serialized
    assert "raw-session-secret" not in serialized
    assert contract["privacy"]["configuration"]["secret_material_exposed"] is False
    assert diagnostics["secret_material_exposed"] is False


def test_per_field_omit_and_future_identifier_fields(monkeypatch):
    monkeypatch.setenv("HERMES_TPS_PRIVACY_MODE", "pseudonymized")
    monkeypatch.setenv("HERMES_TPS_PRIVACY_FIELDS", "tenant_id")
    monkeypatch.setenv("HERMES_TPS_PRIVACY_TREATMENTS", "provider=redacted,tenant_id=omitted")

    payload = _redact_payload(
        {
            "session_id": "raw-session-secret",
            "provider": "raw-provider-name",
            "tenant_id": "raw-tenant-secret",
            "last_tps": 10.0,
        }
    )

    assert payload["session_id"].startswith("session_id:pseudonym:")
    assert payload["provider"] == "[redacted]"
    assert "tenant_id" not in payload
    assert payload["last_tps"] == 10.0
