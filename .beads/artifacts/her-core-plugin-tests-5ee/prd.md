---
purpose: Product Requirements Document for a bead
updated: 2026-06-16
---

# PRD: Add core plugin behavior tests for TPS calculation, session management, and lifecycle

**Bead:** her-core-plugin-tests-5ee | **Type:** task | **Priority:** P2
**Created:** 2026-06-16 | **Estimate:** 60 minutes

## Problem

WHEN a developer modifies the core TPS calculation logic (`_SessionTPS.record()`, `avg_tps`, `peak_tps`) or session lifecycle code (`_evict_if_needed`, `_cleanup_session`) THEN there are no tests to catch regressions BECAUSE the existing test suite only covers usage parsing, REST API endpoints, provider aggregation, persistence, and store delete/expire — the central plugin behavior is untested.

**Who is affected?** Any developer maintaining or extending the tps-counter plugin. Without core tests, refactoring is risky and bug introduction goes undetected.

**Why now?** 9 of 11 beads are closed and the plugin has substantial functionality (per-model tracking, per-provider aggregation, session lifecycle, status bar integration), but the core TPS engine has zero dedicated test coverage. This is the #1 quality risk.

## Scope

### In Scope
- `_SessionTPS` class: `record()`, `avg_tps`, `peak_tps`, `turn_tps`, `total_tokens`, `reset_turn`, `summary_line`, `_fmt_tokens`
- `_ModelTPS` class and `get_model_stats()` public API
- `_get_session()` with DB hydration path
- `_evict_if_needed()` LRU eviction logic
- `_on_session_end()` hook callback
- `get_tps_stats()` public API
- Status bar snapshot construction (models + providers included)
- `_hydrate_from_db()` and `_persist_state()` write-through

### Out of Scope
- REST API endpoints (covered by test_api.py)
- `_extract_usage` (covered by test_usage_parsing.py)
- `_extract_provider` and `_ProviderTPS` (covered by test_provider_tps.py)
- `PersistentSessionStore` delete/expire (covered by test_store_delete.py)
- SQLite persistence internals (covered by test_persistence.py)
- Changes to `store.py`, `api.py`, `README.md`, or `HERMES.md`

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Test `_SessionTPS.record()` with input/output tokens and duration | MUST | Calls increment call_count, accumulate tokens/duration, compute TPS |
| 2 | Test `avg_tps` property | MUST | Returns total_output_tokens / total_duration, 0 when duration is 0 |
| 3 | Test `peak_tps` tracking | MUST | Tracks maximum TPS across multiple record() calls |
| 4 | Test `turn_tps` and `reset_turn()` | MUST | Turn TPS reflects tokens since last reset; reset clears baseline |
| 5 | Test `total_tokens` property | MUST | Returns input + output tokens |
| 6 | Test `_fmt_tokens` static method | MUST | Formats K/M correctly, returns raw string for <1000 |
| 7 | Test `summary_line()` output | MUST | Returns pipe-delimited string with TPS, avg, peak, totals |
| 8 | Test `get_model_stats()` | MUST | Returns per-model dict with avg_tps, peak_tps, calls, tokens, duration |
| 9 | Test `get_tps_stats()` | MUST | Returns correct dict structure with all expected keys |
| 10 | Test `_get_session()` with DB hydration | MUST | Loads from persistent store when not in memory |
| 11 | Test `_evict_if_needed()` | MUST | Evicts oldest session when count exceeds MAX_SESSIONS |
| 12 | Test `_on_session_end()` hook | MUST | Removes session + model + provider state |
| 13 | Test status bar snapshot includes models/providers | MUST | Snapshot dict contains models and providers keys when data exists |
| 14 | Thread safety: concurrent hooks don't corrupt state | SHOULD | Multiple threads calling _on_post_api_request produce correct totals |
| 15 | Edge cases: zero tokens, zero duration, missing session_id | SHOULD | Hook returns early gracefully, no state corruption |

## Technical Context

**Key files:**
- `__init__.py` — Core plugin: `_SessionTPS`, `_ModelTPS`, `_on_post_api_request`, `_get_session`, `_evict_if_needed`, `_cleanup_session`, `get_tps_stats`, `get_model_stats`, `register`
- `store.py` — `PersistentSessionStore` (used by `_hydrate_from_db` and `_persist_state`)
- `tests/conftest.py` — Shared path setup
- `tests/test_provider_tps.py` — Pattern reference for fixtures (mock_hermes_cli, _STATE_LOCK cleanup)

**Key patterns:**
- All tests must mock `hermes_cli` module (see `mock_hermes_cli` autouse fixture)
- Global state (`_SESSIONS`, `_MODELS`, `_PROVIDERS`) must be cleaned up in fixtures
- Use `_STATE_LOCK` when directly manipulating global dicts
- Use `tempfile.mkstemp` for temp DB files (pattern from test_api.py)

**Dependencies:**
- pytest, unittest.mock (standard library)
- `store.PersistentSessionStore` for DB hydration tests

## Approach

Create `tests/test_core.py` with test classes organized by component:

1. **TestSessionTPS** — `_SessionTPS` class behavior (record, properties, summary_line, _fmt_tokens)
2. **TestModelTPS** — `_ModelTPS` class and `get_model_stats()` API
3. **TestGetSession** — `_get_session()` with in-memory and DB hydration paths
4. **TestEviction** — `_evict_if_needed()` LRU eviction
5. **TestSessionEnd** — `_on_session_end()` hook cleanup
6. **TestGetTpsStats** — `get_tps_stats()` public API
7. **TestStatusBarSnapshot** — Snapshot construction with models/providers
8. **TestPersistence** — `_hydrate_from_db()` and `_persist_state()` integration

**Alternatives considered:**
- Extending existing test files → Rejected: core behavior is a distinct concern, deserves its own file
- Property-based testing (hypothesis) → Rejected: overkill for deterministic arithmetic, adds dependency

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Global state leakage between tests | Medium | Medium | autouse fixture clears _SESSIONS, _MODELS, _PROVIDERS |
| DB file cleanup on test failure | Low | Low | tmp_path fixture or try/finally in fixture |
| Thread safety tests flaky | Medium | Low | Use threading.Barrier for synchronization, generous timeouts |

## Success Criteria

- [ ] `pytest tests/test_core.py -v` passes with 0 failures
- [ ] All 15 requirements have corresponding test methods
- [ ] `_SessionTPS.record()` tested with at least 3 call scenarios
- [ ] `get_model_stats()` tested with 2+ models
- [ ] `_evict_if_needed()` tested with sessions exceeding MAX_SESSIONS
- [ ] Status bar snapshot tested with model + provider data
- [ ] No existing tests regress: `pytest tests/ -v` all green
