# Plan: her-test-suite-l0o — Test Suite for tps-counter

## Wave 1: Setup (sequential)
### Task 1.1: Create pytest config
- Creates: pyproject.toml with [tool.pytest.ini_options]
- Touches: pyproject.toml
- Verification: `pytest --co` collects 0 tests (no tests yet)

### Task 1.2: Create tests directory structure
- Creates: tests/__init__.py
- Touches: tests/__init__.py
- Verification: `python -c "import tests"` succeeds

## Wave 2: Core unit tests (parallel — file-disjoint)
### Task 2.1: _SessionTPS class tests
- Creates: tests/test_session_tps.py
- Touches: tests/test_session_tps.py only
- Needs: Wave 1 complete
- Tests:
  - record() with valid tokens/duration
  - record() with zero tokens (no-op)
  - record() with zero duration (no-op)
  - avg_tps property (calculated correctly)
  - avg_tps with zero duration (returns 0)
  - turn_tps property (tokens since reset_turn)
  - turn_tps with zero elapsed (returns 0)
  - reset_turn() updates markers
  - summary_line() format with data
  - summary_line() empty when no data
  - _fmt_tokens() for <1K, >=1K, >=1M
  - peak_tps tracking
  - call_count increments
- Verification: `pytest tests/test_session_tps.py -v`

### Task 2.2: Hook callback tests
- Creates: tests/test_hook.py
- Touches: tests/test_hook.py only
- Needs: Wave 1 complete
- Tests:
  - _on_post_api_request with valid kwargs (records TPS)
  - _on_post_api_request with missing session_id (no-op)
  - _on_post_api_request with zero output_tokens (no-op)
  - _on_post_api_request with zero duration (no-op)
  - _on_post_api_request with empty usage dict (no-op)
  - _on_post_api_request with non-dict usage (no-op)
  - _on_post_api_request injects _tps_snapshot on agent
  - _on_post_api_request handles hermes_cli import failure gracefully
  - Multiple calls accumulate stats correctly
- Verification: `pytest tests/test_hook.py -v`

### Task 2.3: Public API tests
- Creates: tests/test_api.py
- Touches: tests/test_api.py only
- Needs: Wave 1 complete
- Tests:
  - get_tps_stats for existing session returns correct data
  - get_tps_stats for non-existing session returns zeros
  - get_tps_stats returns all expected keys
  - register() calls ctx.register_hook with correct args
  - register() hook name is "post_api_request"
- Verification: `pytest tests/test_api.py -v`

## Wave 3: Thread safety tests (sequential — needs all unit tests)
### Task 3.1: Thread safety tests
- Creates: tests/test_thread_safety.py
- Touches: tests/test_thread_safety.py only
- Needs: Wave 2 complete
- Tests:
  - Concurrent _get_session calls return same instance
  - Concurrent record() calls don't lose data
  - Concurrent get_tps_stats calls don't crash
  - Lock contention under high concurrency (100 threads)
- Verification: `pytest tests/test_thread_safety.py -v`

## Wave 4: Final verification (sequential)
### Task 4.1: Full suite run
- Needs: Wave 3 complete
- Verification: `pytest -v --tb=short` — all green

## File Ownership
| Wave | Files |
|------|-------|
| 1 | pyproject.toml, tests/__init__.py |
| 2 | tests/test_session_tps.py, tests/test_hook.py, tests/test_api.py |
| 3 | tests/test_thread_safety.py |
| 4 | (read-only verification) |

## Context Capsule
- Plugin code: /home/ryan/repos/hermes-tps-counter/__init__.py (169 lines)
- Plugin config: /home/ryan/repos/hermes-tps-counter/plugin.yaml
- Key classes: _SessionTPS (lines 23-98), _on_post_api_request (lines 108-146)
- Key functions: _get_session (101-105), register (149-152), get_tps_stats (156-169)
- Thread safety: _STATE_LOCK (line 19), _SESSIONS dict (line 20)
- External import: hermes_cli._ACTIVE_CLI_INSTANCE (line 125) — must mock
