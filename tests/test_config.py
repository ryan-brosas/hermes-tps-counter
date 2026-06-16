"""Tests for the centralized configuration module."""

import os
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure config module is importable
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import TPSConfig, get_config, reset_config


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset config singleton before each test."""
    reset_config()
    yield
    reset_config()


@pytest.fixture
def config_dir(tmp_path):
    """Return a temporary config directory with a config.toml file."""
    return tmp_path


class TestTPSConfigDefaults:
    """Test that defaults match current hardcoded values."""

    def test_max_sessions_default(self):
        cfg = get_config()
        assert cfg.max_sessions == 50

    def test_db_path_default(self):
        cfg = get_config()
        assert cfg.db_path.endswith("tps.db")
        assert ".hermes" in cfg.db_path

    def test_retention_days_default(self):
        cfg = get_config()
        assert cfg.retention_days == 7

    def test_api_host_default(self):
        cfg = get_config()
        assert cfg.api_host == "127.0.0.1"

    def test_api_port_default(self):
        cfg = get_config()
        assert cfg.api_port == 9127

    def test_prometheus_enabled_default(self):
        cfg = get_config()
        assert cfg.prometheus_enabled is False

    def test_api_enabled_default(self):
        cfg = get_config()
        assert cfg.api_enabled is False

    def test_rate_limit_defaults(self):
        cfg = get_config()
        assert cfg.requests_per_minute == 60
        assert cfg.burst_size == 10


class TestEnvVarOverrides:
    """Test environment variable overrides via TPS_COUNTER_* prefix."""

    def test_max_sessions_env_override(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_MAX_SESSIONS", "100")
        cfg = get_config()
        assert cfg.max_sessions == 100

    def test_db_path_env_override(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_DB_PATH", "/tmp/custom.db")
        cfg = get_config()
        assert cfg.db_path == "/tmp/custom.db"

    def test_retention_days_env_override(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_RETENTION_DAYS", "14")
        cfg = get_config()
        assert cfg.retention_days == 14

    def test_api_host_env_override(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_API_HOST", "0.0.0.0")
        cfg = get_config()
        assert cfg.api_host == "0.0.0.0"

    def test_api_port_env_override(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_API_PORT", "8080")
        cfg = get_config()
        assert cfg.api_port == 8080

    def test_bool_env_override_true(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_API_ENABLED", "true")
        cfg = get_config()
        assert cfg.api_enabled is True

    def test_bool_env_override_false(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_API_ENABLED", "false")
        cfg = get_config()
        assert cfg.api_enabled is False

    def test_bool_env_override_1(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_PROMETHEUS_ENABLED", "1")
        cfg = get_config()
        assert cfg.prometheus_enabled is True

    def test_invalid_env_var_uses_default(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_MAX_SESSIONS", "not_a_number")
        cfg = get_config()
        assert cfg.max_sessions == 50  # default preserved

    def test_multiple_env_overrides(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_MAX_SESSIONS", "200")
        monkeypatch.setenv("TPS_COUNTER_API_PORT", "3000")
        monkeypatch.setenv("TPS_COUNTER_RETENTION_DAYS", "30")
        cfg = get_config()
        assert cfg.max_sessions == 200
        assert cfg.api_port == 3000
        assert cfg.retention_days == 30

    def test_rate_limit_env_overrides(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_REQUESTS_PER_MINUTE", "120")
        monkeypatch.setenv("TPS_COUNTER_BURST_SIZE", "25")
        cfg = get_config()
        assert cfg.requests_per_minute == 120
        assert cfg.burst_size == 25


class TestTOMLConfig:
    """Test TOML config file loading."""

    def test_toml_file_loaded(self, config_dir):
        toml_content = 'max_sessions = 25\nretention_days = 14\n'
        config_file = config_dir / "config.toml"
        config_file.write_text(toml_content)
        cfg = get_config(config_path=config_file)
        assert cfg.max_sessions == 25
        assert cfg.retention_days == 14

    def test_toml_api_section(self, config_dir):
        toml_content = '[api]\nhost = "0.0.0.0"\nport = 8080\nenabled = true\n'
        config_file = config_dir / "config.toml"
        config_file.write_text(toml_content)
        cfg = get_config(config_path=config_file)
        assert cfg.api_host == "0.0.0.0"
        assert cfg.api_port == 8080
        assert cfg.api_enabled is True

    def test_toml_prometheus_section(self, config_dir):
        toml_content = '[prometheus]\nenabled = true\n'
        config_file = config_dir / "config.toml"
        config_file.write_text(toml_content)
        cfg = get_config(config_path=config_file)
        assert cfg.prometheus_enabled is True

    def test_toml_flat_rate_limit_fields(self, config_dir):
        toml_content = 'requests_per_minute = 90\nburst_size = 15\n'
        config_file = config_dir / "config.toml"
        config_file.write_text(toml_content)
        cfg = get_config(config_path=config_file)
        assert cfg.requests_per_minute == 90
        assert cfg.burst_size == 15

    def test_toml_api_rate_limit_section(self, config_dir):
        toml_content = '[api.rate_limit]\nrequests_per_minute = 75\nburst_size = 8\n'
        config_file = config_dir / "config.toml"
        config_file.write_text(toml_content)
        cfg = get_config(config_path=config_file)
        assert cfg.requests_per_minute == 75
        assert cfg.burst_size == 8

    def test_toml_file_missing_no_error(self, config_dir):
        missing_path = config_dir / "nonexistent.toml"
        cfg = get_config(config_path=missing_path)
        assert cfg.max_sessions == 50  # defaults used

    def test_toml_malformed_no_error(self, config_dir):
        config_file = config_dir / "config.toml"
        config_file.write_text("this is not valid toml [[[")
        cfg = get_config(config_path=config_file)
        assert cfg.max_sessions == 50  # defaults used


class TestMergePrecedence:
    """Test that merge order is: defaults < TOML < env vars < ctx."""

    def test_env_overrides_toml(self, config_dir, monkeypatch):
        toml_content = 'max_sessions = 25\n'
        config_file = config_dir / "config.toml"
        config_file.write_text(toml_content)
        monkeypatch.setenv("TPS_COUNTER_MAX_SESSIONS", "100")
        cfg = get_config(config_path=config_file)
        assert cfg.max_sessions == 100  # env wins over TOML

    def test_ctx_overrides_env(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_MAX_SESSIONS", "100")
        ctx = MagicMock()
        ctx.get_config.return_value = {"max_sessions": 200}
        cfg = get_config(ctx=ctx)
        assert cfg.max_sessions == 200  # ctx wins over env

    def test_toml_overrides_defaults(self, config_dir):
        toml_content = 'max_sessions = 30\n'
        config_file = config_dir / "config.toml"
        config_file.write_text(toml_content)
        cfg = get_config(config_path=config_file)
        assert cfg.max_sessions == 30  # TOML wins over default 50


class TestCtxOverrides:
    """Test Hermes context config overrides."""

    def test_ctx_get_config(self):
        ctx = MagicMock()
        ctx.get_config.return_value = {"db_path": "/custom/path.db", "api": {"port": 4000}}
        cfg = get_config(ctx=ctx)
        assert cfg.db_path == "/custom/path.db"
        assert cfg.api_port == 4000

    def test_ctx_direct_rate_limit_fields(self):
        ctx = MagicMock()
        ctx.get_config.return_value = {"requests_per_minute": 33, "burst_size": 4}
        cfg = get_config(ctx=ctx)
        assert cfg.requests_per_minute == 33
        assert cfg.burst_size == 4

    def test_ctx_nested_api_rate_limit_fields(self):
        ctx = MagicMock()
        ctx.get_config.return_value = {"api": {"rate_limit": {"requests_per_minute": 44, "burst_size": 5}}}
        cfg = get_config(ctx=ctx)
        assert cfg.requests_per_minute == 44
        assert cfg.burst_size == 5

    def test_ctx_with_prometheus(self):
        ctx = MagicMock()
        ctx.get_config.return_value = {"prometheus": {"enabled": True}}
        cfg = get_config(ctx=ctx)
        assert cfg.prometheus_enabled is True

    def test_ctx_none_no_error(self):
        cfg = get_config(ctx=None)
        assert cfg.max_sessions == 50

    def test_ctx_no_get_config_attr(self):
        ctx = MagicMock(spec=[])  # no get_config attribute
        cfg = get_config(ctx=ctx)
        assert cfg.max_sessions == 50


class TestThreadSafety:
    """Test thread-safe lazy initialization."""

    def test_concurrent_get_config(self):
        results = []
        errors = []

        def worker():
            try:
                cfg = get_config()
                results.append(cfg)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        # All should be the same singleton instance
        assert all(r is results[0] for r in results)


class TestValidation:
    """Test config validation with clear error messages."""

    def test_max_sessions_clamped_to_minimum(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_MAX_SESSIONS", "0")
        cfg = get_config()
        assert cfg.max_sessions == 1

    def test_retention_days_clamped_to_minimum(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_RETENTION_DAYS", "0")
        cfg = get_config()
        assert cfg.retention_days == 1

    def test_api_port_out_of_range_resets(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_API_PORT", "99999")
        cfg = get_config()
        assert cfg.api_port == 9127  # reset to default

    def test_rate_limit_values_clamped_to_minimum(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_REQUESTS_PER_MINUTE", "0")
        monkeypatch.setenv("TPS_COUNTER_BURST_SIZE", "-3")
        cfg = get_config()
        assert cfg.requests_per_minute == 1
        assert cfg.burst_size == 1


class TestAutoCreateDir:
    """Test that config directory auto-creation works."""

    def test_toml_load_with_missing_parent_dir(self, config_dir):
        """Loading a TOML from a path with missing parents should not error."""
        nested_path = config_dir / "deep" / "nested" / "config.toml"
        cfg = get_config(config_path=nested_path)
        assert cfg.max_sessions == 50  # gracefully falls back to defaults


class TestResetConfig:
    """Test reset_config for test isolation."""

    def test_reset_allows_reinitialization(self, monkeypatch):
        monkeypatch.setenv("TPS_COUNTER_MAX_SESSIONS", "100")
        cfg1 = get_config()
        assert cfg1.max_sessions == 100

        reset_config()
        monkeypatch.delenv("TPS_COUNTER_MAX_SESSIONS")
        cfg2 = get_config()
        assert cfg2.max_sessions == 50  # fresh defaults
