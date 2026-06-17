# Solve Ledger: her-cbe

## Implementation Date
2026-06-17

## Summary
Decomposed the 1,413-line `__init__.py` monolith into a `tps_counter/` Python package with four focused submodules, replacing the root `__init__.py` with a backward-compatible re-export shim. All 376 tests pass with zero test logic changes.

## Architecture Decision

**Mutable state ownership:** All mutable module-level globals (`_SESSIONS`, `_STATE_LOCK`, `_STORE`, `_prometheus_enabled`, `_ALERT_CONFIG`, etc.) are owned by `__init__.py` directly. Submodules (`tps_counter/session.py`, `tps_counter/hooks.py`) reference them via `sys.modules["__init__"]` at function execution time.

**Why:** Tests monkeypatch these values at runtime (e.g., `tps_counter._STORE = mock_store`, `patch("__init__._ALERT_HOOK_MANAGER", mock)`). A naive re-export shim that `from tps_counter.hooks import _STORE` creates separate name bindings — patching the shim's attribute doesn't reach the submodule's attribute. By owning the state in `__init__.py` and using `sys.modules` lookups, every function always reads the same object that tests patch.

## File Changes

### Created
- `tps_counter/__init__.py` — package docstring
- `tps_counter/privacy.py` — `_PrivacyPolicy`, `_OmittedValue`, `_OMITTED`, retention policy, env var constants, privacy helpers (leaf module, zero internal deps)
- `tps_counter/session.py` — `_SessionTPS`, `_ModelTPS`, `_ProviderTPS`, state management functions, public API (`get_tps_stats`, etc.). References mutable state from `__init__` via `sys.modules`.
- `tps_counter/contract.py` — `get_observability_contract`, imports from `tps_counter.privacy`
- `tps_counter/hooks.py` — `register`, hook callbacks, alert evaluation, API server lifecycle, usage extraction. References mutable state from `__init__` via `sys.modules`.

### Modified
- `__init__.py` — replaced 1,413-line monolith with re-export shim (~120 lines). Owns all mutable module-level state. Re-exports functions, classes, and immutable constants from submodules.

## Verification Evidence

- `python3 -c "import tps_counter.hooks"` — no circular imports ✅
- `python3 -c "from __init__ import register, ..., _STORE, _ALERT_CONFIG"` — all symbols re-exported ✅
- State singleton assertions: `_SESSIONS is session._SESSIONS` etc. — all pass ✅
- `pytest tests/ -v` — **376 passed, 0 failed** ✅
- Smoke test: `register(ctx)` with mock context — 3 hooks registered ✅
- `br dep cycles --blocking-only` — 0 cycles ✅
- `bv --robot-suggest` — no suggestions for this bead ✅

## Issues Encountered & Resolved

1. **Test monkeypatch incompatibility (14 failures):** Tests patch `__init__._ALERT_HOOK_MANAGER` and assign `tps_counter._STORE = mock`. With a simple `from submodule import name` shim, these only affected the shim's namespace, not the submodule globals. **Fix:** Moved all mutable globals to `__init__.py` and used `sys.modules["__init__"]` in submodule function bodies.

2. **Missing `time` module in shim (2 failures):** Tests do `monkeypatch.setattr(tps_counter.time, "monotonic", ...)`. **Fix:** Added `import time` (and `threading`, `os`, `logging`) to the shim.

## No Deviations from Plan

All 5 waves executed as planned. No new logic, no behavior changes. Every function, class, constant, and variable behaves identically to the monolith.
