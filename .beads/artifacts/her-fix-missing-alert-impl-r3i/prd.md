# PRD: Implement Missing TPS Threshold Alerting Code

## Problem

**WHEN** the `her-feat-tps-threshold-alerting-how` bead was merged via PR #28 (commit `019c0d6`), only the test file (`tests/test_threshold_alerting.py`, 398 lines, 19 tests) and `test_api.py` edits were merged into `main`.

**THEN** the actual `__init__.py` implementation (258 lines of alerting logic from commit `acaf285` on branch `feat/her-feat-tps-threshold-alerting-how`) was lost due to merge conflicts or incomplete merge.

**BECAUSE** of this, 19 tests fail with `ImportError: cannot import name '_ALERT_CONFIG' from '__init__'` — imports (`_ALERT_CONFIG`, `_evaluate_alert`, `_ALERT_HOOK_MANAGER`) and `_SessionTPS` attributes (`alert_state`, `alert_threshold`, `alert_fired_at`, `alert_resolved_at`, `cold_start_samples`, `recent_tps_samples`) don't exist in the current `__init__.py`.

The bead was **closed prematurely** — marked "Implemented, verified, reviewed: 66/66 tests pass" when the implementation was never in `main`.

## Scope

### In
- Add `_ALERT_CONFIG` dict (threshold, eval_window, cold_start_calls, cold_start_factor)
- Add `_ALERT_HOOK_MANAGER` global reference
- Add 6 alert fields to `_SessionTPS.__slots__` and `__init__`
- Implement `_evaluate_alert()` — cold-start auto-threshold + rolling window evaluation + state machine
- Implement `_emit_alert()` — fires `tps_alert` hook
- Integrate alert evaluation into `_on_post_api_request()` under `_STATE_LOCK`
- Update `register()` for env var config, `tps_alert` hook registration, manager capture
- Add alert fields to `agent._tps_snapshot` (alert_state, alert_threshold, alert_indicator)
- Add alert fields to `get_tps_stats()` return dict
- Fix `test_api.py` register tests (check for `tps_alert` hook registration)

### Out
- No new test files (existing tests are sufficient)
- No changes to `prometheus_metrics.py`, `api.py`, `store.py`, `config.py`, `dashboard.py`
- No README changes (documentation bead exists separately)
- No structural changes to the `__init__.py` architecture

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | `_ALERT_CONFIG` dict exists with defaults: threshold=None, eval_window=5, cold_start_calls=10, cold_start_factor=0.5 | MUST |
| R2 | `_ALERT_HOOK_MANAGER` global exists (set during `register()`) | MUST |
| R3 | `_SessionTPS` has alert slots: alert_state, alert_threshold, alert_fired_at, alert_resolved_at, cold_start_samples, recent_tps_samples | MUST |
| R4 | `_evaluate_alert()` implements cold-start auto-threshold (first N calls establish baseline × factor) | MUST |
| R5 | `_evaluate_alert()` implements rolling window evaluation (last N calls above/below threshold) | MUST |
| R6 | Alert state machine: idle → firing (when rolling avg < threshold) → resolved (when rolling avg >= threshold) | MUST |
| R7 | `_emit_alert()` fires `tps_alert` hook with {session_id, state, tps, threshold, timestamp} | MUST |
| R8 | `register()` reads `TPS_THRESHOLD` and `TPS_EVAL_WINDOW` env vars | MUST |
| R9 | `register()` registers `tps_alert` hook and captures `_ALERT_HOOK_MANAGER` | MUST |
| R10 | `_on_post_api_request()` calls `_evaluate_alert()` inside `_STATE_LOCK` after `state.record()` | MUST |
| R11 | `agent._tps_snapshot` includes alert_state, alert_threshold, alert_indicator | MUST |
| R12 | `get_tps_stats()` returns alert_state and alert_threshold | MUST |
| R13 | All 19 tests in `test_threshold_alerting.py` pass | MUST |
| R14 | All other test files pass (no regressions) | MUST |
| R15 | No breakage of existing features (privacy, retention, model/provider tracking, persistence, Prometheus, WebSocket, dashboard, rate limiting, observability contract) | MUST |

## Success Criteria

1. `python -m pytest tests/test_threshold_alerting.py` — 19/19 pass
2. `python -m pytest tests/` — all 340+ tests pass, 0 regressions
3. `_evaluate_alert()` correctly auto-calculates threshold from first 10 calls
4. Alert fires when rolling TPS drops below threshold
5. Alert resolves when rolling TPS recovers above threshold
6. Status bar snapshot includes `alert_indicator: "⚠ TPS ALERT"` when firing

## Risks

- **Merge conflict risk:** Current `__init__.py` is ~1100 lines with many features; integrating alert code must not break existing functionality
- **Lock ordering:** Alert evaluation must happen inside existing `_STATE_LOCK` in `_on_post_api_request()`
- **Test compatibility:** Existing tests in `test_api.py` were patched to expect `tps_alert` hook registration
