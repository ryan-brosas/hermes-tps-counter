# PRD: Decompose `__init__.py` monolith into `tps_counter/` package

## Problem

The entire plugin lives in a 531-line `__init__.py` flat module at the repo root. This creates:

1. **Maintainability wall** — every feature (privacy, observability, session TPS, hook callback) is in one file with no clear boundaries
2. **Import confusion** — `from __init__ import ...` in tests is a code smell; Python package conventions expect `from tps_counter import ...`
3. **Feature integration blocker** — 28 closed feature beads (SQLite persistence, REST API, Prometheus, dashboard, WebSocket, config module, event storage) cannot land cleanly without module boundaries
4. **Test fixture duplication** — no `conftest.py`; each test file repeats `clear_sessions` fixture

## Goal

Restructure the flat `__init__.py` into a proper `tps_counter/` Python package with logical module boundaries, while preserving 100% backward compatibility for existing consumers and all 60 passing tests.

## Success Criteria

1. **Package structure**: `tps_counter/` directory with `__init__.py`, `privacy.py`, `session.py`, `contract.py`, `hooks.py` (or equivalent decomposition)
2. **Root `__init__.py`** re-exports all public API names so `from __init__ import X` still works (backward compat shim)
3. **All 60 tests pass** without modification to test assertions
4. **Test imports updated** to use `from tps_counter import ...` (preferred) or keep working via re-exports
5. **Shared `conftest.py`** at `tests/conftest.py` with the `clear_sessions` fixture, removing duplication from individual test files
6. **`plugin.yaml`** continues to work (plugin entry point is `register` from the package)
7. **`pyproject.toml`** updated if needed for the new package layout
8. **No behavioral changes** — this is pure refactoring, zero new features

## Scope

- **In-scope**: File decomposition, import reorganization, conftest.py extraction, backward-compat re-exports
- **Out-of-scope**: New features, API changes, performance optimizations, adding missing features from closed beads

## Proposed Module Map

```
tps_counter/
├── __init__.py          # Public API re-exports + register()
├── privacy.py           # _PrivacyPolicy, _OmittedValue, env parsing, redaction helpers
├── session.py           # _SessionTPS, _SESSIONS, _STATE_LOCK, _get_session, get_tps_stats
├── contract.py          # get_observability_contract()
└── hooks.py             # _on_post_api_request, register()
```

Root `__init__.py` becomes a thin backward-compat shim:
```python
"""Backward-compat shim — prefer `from tps_counter import ...`"""
from tps_counter import *  # re-exports all public names
```

## Risks

| Risk | Mitigation |
|------|-----------|
| Import path breakage for tests | Root shim re-exports everything; update tests to use `tps_counter` |
| Plugin loader can't find `register()` | Verify `plugin.yaml` entry point; test with Hermes plugin loading |
| Circular imports between modules | Session and privacy have no cross-deps; hooks imports from session + privacy |
| Test fixture breakage during migration | Migrate one test file at a time, run after each |

## Verification

```bash
python3 -m pytest tests/ -v   # All 60 tests pass
python3 -c "from tps_counter import get_tps_stats, register, get_observability_contract, get_privacy_diagnostics"
python3 -c "from __init__ import get_tps_stats"  # Backward compat shim works
```
