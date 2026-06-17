---
purpose: Task decomposition with dependency tracking
updated: 2026-06-16
---

# Tasks: her-config-module-czp

## Task Metadata

```yaml
id: "1.1"
depends_on: []
parallel: false
conflicts_with: []
files: ["config.py"]
estimated_minutes: 20
```

## 1. Core Config Module

### 1.1 Create config.py with TPSConfig dataclass

```yaml
depends_on: []
parallel: false
files: ["config.py"]
estimated_minutes: 20
```

- [ ] Create `config.py` with `TPSConfig` dataclass containing fields:
  - `max_sessions: int = 50`
  - `db_path: str = os.path.expanduser("~/.hermes/plugins/tps-counter/tps.db")`
  - `retention_days: int = 7`
  - `api_host: str = "127.0.0.1"`
  - `api_port: int = 9127`
  - `prometheus_enabled: bool = False`
  - `api_enabled: bool = False`
- [ ] Implement `_load_from_toml(path: str) -> dict` — reads TOML file using `tomllib`, returns dict. Returns `{}` if file missing. Auto-creates parent dir if missing.
- [ ] Implement `_load_from_env() -> dict` — reads `TPS_COUNTER_*` env vars, maps to field names. Handles type coercion (int for port/max_sessions, bool for enabled flags, str for paths).
- [ ] Implement `get_config(ctx: Any = None) -> TPSConfig` — lazy singleton with `threading.Lock`. Merge order: defaults < TOML < env vars < ctx.get_config(). Validates types, logs warnings for invalid values.
- [ ] Add `_CONFIG_LOCK` and `_CONFIG_SINGLETON` module-level vars for thread-safe lazy init.
- [ ] Add docstrings for all public functions and the dataclass.

**Verification:** `python3 -c "from config import TPSConfig, get_config; c = get_config(); print(c)"`

## 2. Tests

### 2.1 Write tests/test_config.py

```yaml
depends_on: ["1.1"]
parallel: false
files: ["tests/test_config.py"]
estimated_minutes: 15
```

- [ ] Test default values match current hardcoded values (max_sessions=50, db_path ends with tps.db, retention_days=7, api_host=127.0.0.1, api_port=9127)
- [ ] Test env var override: set `TPS_COUNTER_MAX_SESSIONS=100`, assert `get_config().max_sessions == 100`
- [ ] Test env var override for all fields (db_path, retention_days, api_host, api_port)
- [ ] Test TOML file loading: create temp TOML file, assert values loaded
- [ ] Test TOML file missing: assert defaults used, no error
- [ ] Test merge precedence: TOML sets value, env var overrides it
- [ ] Test ctx override: mock ctx with custom config, assert it wins over env vars
- [ ] Test thread safety: concurrent `get_config()` calls return same instance
- [ ] Test invalid env var value: assert warning logged, default used
- [ ] Test auto-create config directory when TOML path parent doesn't exist
- [ ] Use `tmp_path` fixture for TOML file tests
- [ ] Use `monkeypatch` for env var tests

**Verification:** `pytest tests/test_config.py -v`

## 3. Integration

### 3.1 Update __init__.py to use config module

```yaml
depends_on: ["1.1"]
parallel: false
files: ["__init__.py"]
estimated_minutes: 15
```

- [ ] Import `get_config` from `config` module
- [ ] Replace `MAX_SESSIONS = 50` with config-sourced value in `_evict_if_needed()`
- [ ] Replace hardcoded `default_path` in `register()` with `config.db_path`
- [ ] Replace hardcoded API host/port in `register()` with `config.api_host` / `config.api_port`
- [ ] Replace prometheus config reading with `config.prometheus_enabled`
- [ ] Replace API enabled check with `config.api_enabled`
- [ ] Ensure `register()` calls `get_config(ctx)` to merge ctx overrides
- [ ] Keep backward compatibility: existing `ctx.get_config("tps_counter", {})` still works

**Verification:** `pytest tests/ -x --ignore=tests/test_config.py`

### 3.2 Update store.py to accept retention from config

```yaml
depends_on: ["3.1"]
parallel: false
files: ["store.py"]
estimated_minutes: 10
```

- [ ] In `record_event()`, replace hardcoded `7 * 86400` with config-sourced `retention_days * 86400`
- [ ] Pass retention_days to `PersistentSessionStore.__init__()` or read from config at call site
- [ ] Ensure `_delete_expired_events_unlocked()` uses the configured retention value
- [ ] Default behavior unchanged when config not available

**Verification:** `pytest tests/test_persistence.py tests/test_event_storage.py tests/test_store_delete.py -v`

## 4. Verification

### 4.1 Full test suite passes

```yaml
depends_on: ["2.1", "3.1", "3.2"]
parallel: false
estimated_minutes: 5
```

- [ ] `pytest tests/ -v` — all tests pass (new + existing)
- [ ] `python3 -c "from config import TPSConfig, get_config; c = get_config(); assert c.max_sessions == 50"` — defaults correct
- [ ] `TPS_COUNTER_MAX_SESSIONS=200 python3 -c "from config import get_config; assert get_config().max_sessions == 200"` — env override works
