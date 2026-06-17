---
purpose: Agent spawn context for a bead
updated: 2026-06-16
---

# Context Capsule: her-core-plugin-tests-5ee

## Objective

Create `tests/test_core.py` with comprehensive pytest coverage for the core plugin behavior: `_SessionTPS`, `_ModelTPS`, `get_model_stats`, `get_tps_stats`, `_get_session`, `_evict_if_needed`, `_on_session_end`, status bar snapshot, and persistence integration.

## Key Patterns

- `mock_hermes_cli` autouse fixture — Required for all test files. Creates fake `hermes_cli` module with `_ACTIVE_CLI_INSTANCE = None`. Reference: `tests/test_provider_tps.py:15-21`
- `clean_state` fixture — Clear `_SESSIONS`, `_MODELS`, `_PROVIDERS` under `_STATE_LOCK` before/after each test. Reference: `tests/test_provider_tps.py:177-179`
- `tempfile.mkstemp` for temp DB — Pattern from `tests/test_api.py:28-37`
- Mock CLI with agent — `MagicMock()` with `.agent._tps_snapshot = {}`. Reference: `tests/test_provider_tps.py:163-167`
- Direct global manipulation — Set `_SESSIONS["id"] = _SessionTPS()` directly for unit tests, clean up after. Reference: `tests/test_provider_tps.py:270-276`

## Constraints

1. NEVER modify `__init__.py`, `store.py`, `api.py` — tests only
2. All global state must be cleaned in fixtures — no test pollution
3. Thread safety tests should use `threading.Barrier` for synchronization
4. Follow existing test style: class-based grouping, descriptive method names
5. Each test file needs `sys.path.insert(0, ...)` for import compatibility

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| All tasks | `tests/test_core.py` — create and write | `__init__.py` — read only |
| All tasks | `tests/conftest.py` — read only | `store.py` — read only |
| All tasks | `__init__.py` — read for understanding | `api.py` — not needed |

## Graph Context

- **Blast radius:** `tests/test_core.py` (new file, no conflicts)
- **Related beads:** None (unique concern)
- **File history:** No prior beads touch test_core.py (new file)
