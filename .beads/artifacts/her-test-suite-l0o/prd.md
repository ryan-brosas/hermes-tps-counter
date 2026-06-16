# PRD: Add Comprehensive pytest Test Suite for tps-counter Plugin

## Problem
The tps-counter plugin (169 lines) has zero test coverage. Any modification is a blind edit. Thread safety, edge cases, and API contracts are unverified.

## Goal
Add a comprehensive pytest test suite that validates all public and internal behavior of the tps-counter plugin.

## Scope
- In: Unit tests, integration tests, thread safety tests, edge cases
- Out: Performance benchmarks, mocking Hermes core (we test plugin logic only)

## Affected Files
- `tests/__init__.py` (new)
- `tests/test_session_tps.py` (new) — _SessionTPS class tests
- `tests/test_hook.py` (new) — _on_post_api_request hook tests
- `tests/test_api.py` (new) — get_tps_stats + register tests
- `tests/test_thread_safety.py` (new) — concurrent access tests
- `pytest.ini` or `pyproject.toml` (new) — pytest config

## Functional Requirements
1. Tests must pass with `pytest` (no external deps beyond pytest)
2. Tests must cover all methods of `_SessionTPS`
3. Tests must cover `_on_post_api_request` with various kwargs
4. Tests must cover thread safety with concurrent calls
5. Tests must cover edge cases (zero tokens, zero duration, missing fields)
6. Tests must cover `get_tps_stats` public API
7. Tests must cover `register` function

## Success Criteria
- [ ] `pytest` runs green with 0 failures
- [ ] All `_SessionTPS` methods tested (record, avg_tps, turn_tps, summary_line, _fmt_tokens, reset_turn)
- [ ] Hook callback tested with valid, partial, and missing kwargs
- [ ] Thread safety verified with concurrent _get_session calls
- [ ] Edge cases: zero tokens, zero duration, missing session_id, empty usage dict
- [ ] `get_tps_stats` tested for existing and non-existing sessions
- [ ] `register` tested for hook registration

## Non-Goals
- Testing Hermes core integration (status bar patches)
- Testing the plugin loader mechanism
- Performance/load testing

## Risks
- Risk: Plugin imports from `hermes_cli` — need to mock this import
  - Mitigation: Use unittest.mock to patch the import
- Risk: Thread tests may be flaky under load
  - Mitigation: Use threading.Barrier for synchronization
