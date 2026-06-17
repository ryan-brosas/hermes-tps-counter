# PRD: Centralized Configuration Module

**Bead:** her-config-module-czp
**Type:** task
**Priority:** P2

## Problem

**WHEN** a user wants to customize the TPS counter plugin behavior (session limits, retention, API port),
**THEN** they must edit source code directly because all settings are hardcoded,
**BECAUSE** there is no centralized configuration module — defaults are scattered across `__init__.py` (MAX_SESSIONS=50, db_path default) and `store.py` (retention=7 days).

### Current Hardcoded Values

| Setting | Current Value | Location |
|---------|--------------|----------|
| MAX_SESSIONS | 50 | `__init__.py:77` |
| db_path default | `~/.hermes/plugins/tps-counter/tps.db` | `__init__.py:463` |
| Event retention | 7 days (604800s) | `store.py:357` |
| API host | `127.0.0.1` | `__init__.py:492` |
| API port | 9127 | `__init__.py:493` |

## Scope

### In
- New `config.py` module with typed dataclass
- Environment variable overrides via `TPS_COUNTER_` prefix
- Optional TOML config file at `~/.hermes/plugins/tps-counter/config.toml`
- Merge precedence: defaults < config file < env vars < ctx.get_config()
- Replace hardcoded values in `__init__.py` and `store.py`
- Tests for config loading, merging, validation, env var overrides

### Out
- Runtime config reload (hot-reload) — future work
- CLI commands for config management
- Config UI / dashboard integration
- Per-session config overrides

## Requirements

| # | Requirement | Priority |
|---|-------------|----------|
| R1 | `config.py` module with `TPSConfig` dataclass containing all settings | MUST |
| R2 | `get_config()` function returning merged config singleton | MUST |
| R3 | Environment variable overrides: `TPS_COUNTER_MAX_SESSIONS`, `TPS_COUNTER_DB_PATH`, `TPS_COUNTER_RETENTION_DAYS`, `TPS_COUNTER_API_HOST`, `TPS_COUNTER_API_PORT` | MUST |
| R4 | Optional TOML config file at `~/.hermes/plugins/tps-counter/config.toml` | MUST |
| R5 | Merge precedence: defaults < TOML < env vars < ctx overrides | MUST |
| R6 | All current hardcoded values preserved as defaults | MUST |
| R7 | `__init__.py` uses config module instead of hardcoded values | MUST |
| R8 | `store.py` accepts retention from config | MUST |
| R9 | Thread-safe lazy initialization | MUST |
| R10 | Config validation with clear error messages | SHOULD |
| R11 | Auto-create config directory if missing | SHOULD |
| R12 | Comprehensive tests for all config paths | MUST |

## Technical Context

### Files to Modify
- `config.py` (NEW) — config module
- `__init__.py` — replace hardcoded MAX_SESSIONS, db_path, API host/port
- `store.py` — accept retention_seconds from config
- `tests/test_config.py` (NEW) — config tests

### Patterns to Follow
- Existing codebase uses `__slots__` for memory efficiency
- Thread safety via `threading.Lock()` pattern
- Type hints throughout
- pytest for testing with `tmp_path` fixture

### Dependencies
- `tomllib` (stdlib in Python 3.11+) for TOML parsing
- No new external dependencies

## Approach

1. Create `config.py` with `TPSConfig` dataclass
2. Implement `_load_from_toml()`, `_load_from_env()`, `_apply_ctx_overrides()`
3. Implement `get_config()` with lazy singleton and lock
4. Update `__init__.py` to import and use config
5. Update `store.py` to accept retention from config
6. Write comprehensive tests

## Risks

| Risk | Mitigation |
|------|-----------|
| Breaking existing ctx.get_config() integration | Merge ctx overrides last (highest priority) |
| TOML not available on Python < 3.11 | Project already requires 3.11+, tomllib is stdlib |
| Thread safety on config load | Use threading.Lock for lazy init |

## Success Criteria

1. All 5 previously hardcoded values accessible via config
2. `TPS_COUNTER_MAX_SESSIONS=100` env var overrides default
3. TOML config file loaded if present, skipped if absent
4. Existing tests pass without modification
5. New tests cover all merge paths
6. Zero new external dependencies

## Acceptance Criteria

- [ ] `config.py` exists with `TPSConfig` dataclass and `get_config()` function
  - Verify: `python3 -c "from config import TPSConfig, get_config; c = get_config(); print(c)"`
- [ ] `TPSConfig` fields: `max_sessions` (int=50), `db_path` (str), `retention_days` (int=7), `api_host` (str="127.0.0.1"), `api_port` (int=9127)
  - Verify: `python3 -c "from config import get_config; c = get_config(); assert c.max_sessions == 50"`
- [ ] Setting `TPS_COUNTER_MAX_SESSIONS=100` in environment changes `max_sessions` to 100
  - Verify: `TPS_COUNTER_MAX_SESSIONS=100 python3 -c "from config import get_config; assert get_config().max_sessions == 100"`
- [ ] TOML file at config path overrides defaults when present
  - Verify: Create test TOML, load config, assert values match
- [ ] `ctx.get_config("tps_counter", {})` overrides all other sources
  - Verify: Mock ctx with custom values, assert they win over defaults
- [ ] All existing tests pass unchanged
  - Verify: `pytest tests/ -x --ignore=tests/test_config.py`
- [ ] New `tests/test_config.py` covers all merge paths
  - Verify: `pytest tests/test_config.py -v`
