# Solve Ledger: her-test-suite-l0o

## Decisions
1. **pytest over unittest** — pytest is simpler, more Pythonic, and the standard for modern Python testing
2. **Mock hermes_cli import** — The plugin tries to import hermes_cli._ACTIVE_CLI_INSTANCE; we mock this to avoid requiring Hermes core
3. **threading.Barrier for sync** — Use Barrier for deterministic concurrent test coordination, not sleep()
4. **One test file per concern** — test_session_tps.py, test_hook.py, test_api.py, test_thread_safety.py for clean separation
5. **No conftest.py needed yet** — Fixtures are simple enough to define per-file; add conftest.py if shared fixtures emerge

## Open Questions
- None. Plugin code is clear and self-contained.
