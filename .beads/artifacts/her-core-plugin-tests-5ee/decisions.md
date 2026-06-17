---
purpose: Decision log for a bead
updated: 2026-06-16
---

# Decisions: her-core-plugin-tests-5ee

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Create new test file `tests/test_core.py` rather than extending existing files | Core TPS behavior is a distinct concern from usage parsing, API endpoints, or provider aggregation. Separate file improves discoverability and follows existing pattern (one file per concern). | High |
| 2 | Use autouse fixture to clear global state (_SESSIONS, _MODELS, _PROVIDERS) | Prevents test pollution. Follows pattern from test_provider_tps.py and test_usage_parsing.py. | High |
| 3 | Mock hermes_cli module at module level | Required for import compatibility. All existing test files do this. | High |
| 4 | Use tempfile for DB in hydration/persistence tests | Follows pattern from test_api.py. Avoids test interference with real DB. | High |
| 5 | Skip property-based testing (hypothesis) | TPS calculations are deterministic arithmetic. Standard example-based tests are sufficient and don't add a dependency. | Medium |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Extend test_persistence.py with hydration tests | Different concern — persistence tests focus on SQLite store, not plugin hydration logic | Low risk, but conflates concerns |
| 2 | Use pytest-cov to identify exact uncovered lines | Overkill for this task — the gaps are obvious from reading the code | No risk, just unnecessary tooling |
| 3 | Test status bar integration end-to-end | Requires patching hermes_cli deeply; unit-level snapshot test is sufficient | Medium risk — end-to-end could catch wiring bugs |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | `_SessionTPS` is only instantiated inside `_get_session()` | Validated — no external instantiation | Tests can focus on the hook→_get_session→record path |
| 2 | `MAX_SESSIONS` is module-level constant (not configurable) | Validated — hardcoded to 50 | Tests can set it directly for eviction testing |
| 3 | `_STORE` global is set once during `register()` | Validated — set in register(), used by _hydrate_from_db/_persist_state | Tests can set _STORE directly for hydration tests |
