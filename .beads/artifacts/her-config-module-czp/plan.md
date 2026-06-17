---
purpose: Wave-sequenced implementation plan
updated: 2026-06-16
---

# Plan: her-config-module-czp

**Goal:** Create a centralized `config.py` module that consolidates all hardcoded defaults into a typed dataclass with env var overrides and optional TOML config file support.

## Graph Context

- **Blast radius:** `config.py` (new), `__init__.py`, `store.py`, `tests/test_config.py` (new)
- **Unblocks:** No downstream beads currently depend on this (leaf node)
- **Blocked by:** None
- **Critical path:** No — leaf node with no downstream dependencies
- **Forecast:** ~66 minutes estimated (single session achievable)

## Observable Truths

What must be TRUE for the goal to be achieved:

1. `from config import TPSConfig, get_config` works without error
2. `get_config().max_sessions == 50` when no overrides are set (backward compat)
3. `TPS_COUNTER_MAX_SESSIONS=100 python3 -c "from config import get_config; assert get_config().max_sessions == 100"` succeeds
4. A TOML file at `~/.hermes/plugins/tps-counter/config.toml` is loaded when present, silently skipped when absent
5. `__init__.py` reads MAX_SESSIONS, db_path, api_host, api_port from config instead of hardcoded values
6. `store.py` reads retention_days from config instead of hardcoded 604800
7. All existing tests pass unchanged (`pytest tests/ -x --ignore=tests/test_config.py`)
8. New `tests/test_config.py` covers all merge paths (defaults, TOML, env vars, ctx overrides)

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| config.py | Typed config dataclass + merged singleton | `config.py` | Need |
| test_config.py | Config test coverage | `tests/test_config.py` | Need |
| __init__.py update | Config integration in plugin | `__init__.py` | Need |
| store.py update | Retention from config | `store.py` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | Create config.py with TPSConfig + get_config() | No | None | `python3 -c "from config import TPSConfig, get_config"` |
| 2 | Write tests/test_config.py | No | Wave 1 complete | `pytest tests/test_config.py -v` |
| 3 | Update __init__.py to use config | No | Wave 1 complete | `pytest tests/ -x --ignore=tests/test_config.py` |
| 4 | Update store.py to accept retention from config | No | Wave 3 complete | `pytest tests/ -x` |
| 5 | Full test suite + lint | No | Waves 2-4 complete | `pytest tests/ -v` |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
# Verify config module imports
python3 -c "from config import TPSConfig, get_config; c = get_config(); assert c.max_sessions == 50; print('OK:', c)"

# Verify env var override
TPS_COUNTER_MAX_SESSIONS=100 python3 -c "from config import get_config; assert get_config().max_sessions == 100; print('Env override OK')"

# Run all tests
pytest tests/ -v

# Verify no regressions in existing tests
pytest tests/ -x --ignore=tests/test_config.py
```
