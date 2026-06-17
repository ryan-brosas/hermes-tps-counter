---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-cbe

## Task Metadata

```yaml
id: "her-cbe"
depends_on: []
parallel: false
conflicts_with:
  - "Any concurrent task editing root __init__.py, tests/test_*.py, plugin.yaml, or pyproject.toml"
files:
  - "__init__.py"
  - "tps_counter/*.py"
  - "tests/conftest.py"
  - "tests/test_*.py"
  - "plugin.yaml"
  - "pyproject.toml"
estimated_minutes: 66
```

## 1. Setup and Inventory

### 1.1 Confirm current boundaries and public API

```yaml
depends_on: []
parallel: false
conflicts_with: []
files: ["__init__.py", "plugin.yaml", "pyproject.toml", "tests/test_*.py"]
estimated_minutes: 10
```

- [ ] Identify privacy-related symbols, constants, and helpers in root `__init__.py`.
- [ ] Identify session state symbols: `_SessionTPS`, `_SESSIONS`, `_STATE_LOCK`, `_get_session`, `get_tps_stats`.
- [ ] Identify observability contract symbols: `_PLUGIN_NAME`, `_PLUGIN_VERSION`, `_OBSERVABILITY_CONTRACT_VERSION`, `get_observability_contract`.
- [ ] Identify hook/registration symbols: `_on_post_api_request`, `register`, logger usage, and status snapshot behavior.
- [ ] List all names imported by tests so `tps_counter/__init__.py` can re-export both public API and test-required internals.

### 1.2 Create package scaffold

```yaml
depends_on: ["1.1"]
parallel: false
conflicts_with: []
files:
  - "tps_counter/__init__.py"
  - "tps_counter/privacy.py"
  - "tps_counter/session.py"
  - "tps_counter/contract.py"
  - "tps_counter/hooks.py"
estimated_minutes: 10
```

- [ ] Create `tps_counter/` directory.
- [ ] Add module files matching the PRD module map.
- [ ] Keep initial imports dependency-directed to avoid cycles: `hooks` may import `privacy`, `session`, and `contract`; lower-level modules must not import `hooks`.

## 2. Core Decomposition

### 2.1 Extract privacy policy and redaction helpers

```yaml
depends_on: ["1.2"]
parallel: true
conflicts_with: ["2.4"]
files: ["tps_counter/privacy.py", "__init__.py"]
estimated_minutes: 10
```

- [ ] Move privacy env constants, `_PrivacyPolicy`, `_OmittedValue`, `_OMITTED`, env parsing helpers, redaction helpers, and `get_privacy_diagnostics` into `tps_counter/privacy.py`.
- [ ] Preserve exact treatment normalization, pseudonym format, omitted sentinel behavior, and diagnostic output shape.
- [ ] Do not introduce dependencies beyond Python stdlib.

### 2.2 Extract session state and stats API

```yaml
depends_on: ["1.2"]
parallel: true
conflicts_with: ["2.4"]
files: ["tps_counter/session.py", "__init__.py"]
estimated_minutes: 10
```

- [ ] Move `_SessionTPS`, `_SESSIONS`, `_STATE_LOCK`, `_get_session`, and `get_tps_stats` into `tps_counter/session.py`.
- [ ] Preserve `_STATE_LOCK` protection for `_SESSIONS` dict access.
- [ ] Preserve rounding, zero-duration behavior, call count increments, freshness metadata, and all current stat keys.

### 2.3 Extract observability contract

```yaml
depends_on: ["1.2"]
parallel: true
conflicts_with: ["2.4"]
files: ["tps_counter/contract.py", "__init__.py"]
estimated_minutes: 10
```

- [ ] Move plugin metadata constants and `get_observability_contract()` into `tps_counter/contract.py` unless constants need a separate shared module.
- [ ] Preserve JSON-serializable shape and plugin metadata alignment with `plugin.yaml`.
- [ ] Avoid importing hook code from the contract module.

### 2.4 Extract hook callback and registration

```yaml
depends_on: ["2.1", "2.2", "2.3"]
parallel: false
conflicts_with: ["2.1", "2.2", "2.3"]
files: ["tps_counter/hooks.py", "tps_counter/__init__.py", "__init__.py"]
estimated_minutes: 10
```

- [ ] Move `_on_post_api_request` and `register` into `tps_counter/hooks.py`.
- [ ] Import session and privacy helpers from their new modules.
- [ ] Preserve all behavior for token extraction, duration handling, session lookup, agent status snapshot updates, logging, and hook registration.
- [ ] Ensure `register` remains the plugin entry point exported from `tps_counter`.

### 2.5 Wire package exports

```yaml
depends_on: ["2.4"]
parallel: false
conflicts_with: []
files: ["tps_counter/__init__.py"]
estimated_minutes: 8
```

- [ ] Re-export public API names: `register`, `get_tps_stats`, `get_observability_contract`, `get_privacy_diagnostics`.
- [ ] Re-export internal names currently used by tests: `_SessionTPS`, `_SESSIONS`, `_STATE_LOCK`, `_get_session`, `_on_post_api_request`, privacy policy/sentinel helpers as needed.
- [ ] Define `__all__` intentionally so root shim imports the required API surface.
- [ ] Verify direct package import succeeds.

## 3. Compatibility and Tests

### 3.1 Replace root `__init__.py` with compatibility shim

```yaml
depends_on: ["2.5"]
parallel: false
conflicts_with: []
files: ["__init__.py"]
estimated_minutes: 5
```

- [ ] Replace the root monolith with a thin shim: docstring plus `from tps_counter import *`.
- [ ] Preserve backward compatibility for existing `from __init__ import ...` consumers.
- [ ] Do not keep duplicate business logic in the root file.

### 3.2 Extract shared test fixture

```yaml
depends_on: ["2.5"]
parallel: false
conflicts_with: ["3.3"]
files: ["tests/conftest.py", "tests/test_*.py"]
estimated_minutes: 8
```

- [ ] Create `tests/conftest.py` with the autouse `clear_sessions` fixture.
- [ ] Import `_STATE_LOCK` and `_SESSIONS` from `tps_counter` in the fixture.
- [ ] Remove duplicated `clear_sessions` fixture definitions from individual test files.
- [ ] Ensure fixture cleanup runs before and after each test.

### 3.3 Update test import paths

```yaml
depends_on: ["3.1", "3.2"]
parallel: false
conflicts_with: ["3.2"]
files: ["tests/test_api.py", "tests/test_hook.py", "tests/test_privacy.py", "tests/test_session_tps.py", "tests/test_thread_safety.py"]
estimated_minutes: 8
```

- [ ] Change test imports from `from __init__ import ...` to `from tps_counter import ...`.
- [ ] Keep test assertions unchanged.
- [ ] If a test needs an internal symbol, re-export it from `tps_counter/__init__.py` rather than reaching into deeper modules unless a deeper import is clearer and stable.

## 4. Packaging and Verification

### 4.1 Verify `plugin.yaml` and `pyproject.toml`

```yaml
depends_on: ["3.3"]
parallel: false
conflicts_with: []
files: ["plugin.yaml", "pyproject.toml"]
estimated_minutes: 5
```

- [ ] Confirm `plugin.yaml` still advertises `post_api_request` and the loader can resolve exported `register` through the package/shim path used by Hermes.
- [ ] Update `pyproject.toml` only if setuptools/package discovery requires explicit package configuration for `tps_counter`.
- [ ] Avoid unrelated metadata changes.

### 4.2 Run focused import checks

```yaml
depends_on: ["4.1"]
parallel: false
conflicts_with: []
files: []
estimated_minutes: 3
```

- [ ] `python3 -c "from tps_counter import get_tps_stats, register, get_observability_contract, get_privacy_diagnostics"`
- [ ] `python3 -c "from __init__ import get_tps_stats"`

### 4.3 Run full test suite

```yaml
depends_on: ["4.2"]
parallel: false
conflicts_with: []
files: []
estimated_minutes: 7
```

- [ ] `python3 -m pytest tests/ -v`
- [ ] Confirm all 60 tests pass.
- [ ] Record verification evidence in the `/verify` phase, not during this plan-only phase.
