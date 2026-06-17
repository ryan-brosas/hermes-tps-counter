# Tasks: her-test-suite-l0o

## Task 1: Create pytest config
**File:** pyproject.toml
**Action:** Create pyproject.toml with `[tool.pytest.ini_options]` section.
**Verification:** `pytest --co` collects 0 tests (no tests yet)
**Parallel:** No
**Depends on:** None

## Task 2: Create tests directory structure
**File:** tests/__init__.py
**Action:** Create `tests/__init__.py`.
**Verification:** `python -c "import tests"` succeeds
**Parallel:** No
**Depends on:** Task 1

## Task 3: _SessionTPS class tests
**File:** tests/test_session_tps.py
**Action:** Create tests for: record() with valid tokens/duration, record() with zero tokens (no-op), record() with zero duration (no-op), avg_tps property, avg_tps with zero duration, turn_tps property, turn_tps with zero elapsed, reset_turn() updates markers, summary_line() format, summary_line() empty, _fmt_tokens() for <1K/>=1K/>=1M, peak_tps tracking, call_count increments.
**Verification:** `pytest tests/test_session_tps.py -v`
**Parallel:** Yes
**Depends on:** Task 2

## Task 4: Hook callback tests
**File:** tests/test_hook.py
**Action:** Create tests for: _on_post_api_request with valid kwargs, missing session_id (no-op), zero output_tokens (no-op), zero duration (no-op), empty usage dict (no-op), non-dict usage (no-op), injects _tps_snapshot on agent, handles hermes_cli import failure, multiple calls accumulate stats.
**Verification:** `pytest tests/test_hook.py -v`
**Parallel:** Yes
**Depends on:** Task 2

## Task 5: Public API tests
**File:** tests/test_api.py
**Action:** Create tests for: get_tps_stats for existing session, non-existing session returns zeros, returns all expected keys, register() calls ctx.register_hook with correct args, register() hook name is "post_api_request".
**Verification:** `pytest tests/test_api.py -v`
**Parallel:** Yes
**Depends on:** Task 2

## Task 6: Thread safety tests
**File:** tests/test_thread_safety.py
**Action:** Create tests for: concurrent _get_session calls return same instance, concurrent record() calls don't lose data, concurrent get_tps_stats calls don't crash, lock contention under high concurrency (100 threads).
**Verification:** `pytest tests/test_thread_safety.py -v`
**Parallel:** No
**Depends on:** Task 3, Task 4, Task 5

## Task 7: Full suite run
**File:** (verification only)
**Action:** Run complete test suite.
**Verification:** `pytest -v --tb=short` — all green
**Parallel:** No
**Depends on:** Task 6
