# Solve Ledger: her-br5

## Wave 1 — Baseline review and test seams
- Loaded pi workflow and project instructions.
- Reviewed plan, tasks, context capsule, existing `__init__.py`, `tests/test_api.py`, and `tests/test_thread_safety.py`.
- Confirmed zero-value missing-session shape is `{"calls": 0, "avg_tps": 0, "last_tps": 0, "peak_tps": 0, "total_output_tokens": 0}`.
- Used deterministic monotonic-time seams via `monkeypatch.setattr(tps_counter.time, "monotonic", ...)`.

## Wave 2 — Core retention implementation
- Added `HERMES_TPS_MAX_SESSIONS` and `HERMES_TPS_SESSION_TTL_SECONDS` retention env constants.
- Added on-demand positive int/float parsing where unset, blank, invalid, zero, and negative values are disabled.
- Added `_RetentionPolicy`, retention diagnostics, `_SessionTPS.last_updated_monotonic`, and `_prune_sessions_locked()`.
- Integrated opportunistic pruning after successful `post_api_request` records while preserving the current session when max-count pruning can do so.

## Wave 3 — Contract/privacy metadata
- Added additive `retention` metadata to `get_observability_contract()`.
- Exposed only env var names, enabled flags, sanitized numeric limits/status, and process-local/opportunistic behavior.
- Did not expose session IDs, per-session timestamps, salts, model names, provider names, or live session listings.

## Wave 4 — Concurrency and regression coverage
- Added deterministic API tests for default disabled behavior, max-session pruning, TTL pruning, pruned stats reads, invalid envs, and contract privacy.
- Added concurrency test exercising readers and writers while max-session pruning is active.

## Wave 5 — Verification
- `python3 -m pytest tests/test_api.py -v` — 25 passed.
- `python3 -m pytest tests/test_thread_safety.py -v` — 6 passed.
- `python3 -m pytest tests/ -v` — 74 passed.
- Dependency/background inspection passed: no forbidden markers in `__init__.py`.
- `br lint her-br5 --json` passed after adding bead acceptance criteria metadata.
