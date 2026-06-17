---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-fix-missing-alert-impl-r3i

## Objective

Implement the TPS threshold alerting feature in `__init__.py` that was lost during merge of PR #28. The tests (`test_threshold_alerting.py`, 398 lines, 19 tests) were merged but the implementation was dropped. Make all 19 tests pass with zero regressions on the other 340+ tests.

## Key Patterns

- `_SessionTPS.__slots__` — All instance fields must be declared in the `__slots__` tuple. Add 6 new fields: `alert_state`, `alert_threshold`, `alert_fired_at`, `alert_resolved_at`, `cold_start_samples`, `recent_tps_samples`. Reference: `__init__.py:363`
- `_STATE_LOCK` — All shared state mutation (including alert evaluation) must happen inside `threading.Lock(). Reference: `__init__.py:74,631`
- `register(ctx)` — Plugin entry reads env vars, registers hooks, captures references. Must register `tps_alert` hook name. Reference: `__init__.py:823`
- `_on_post_api_request()` — Alert evaluation must be called INSIDE the existing `_STATE_LOCK` block, after `state.record()`. Reference: `__init__.py:608-631`
- `agent._tps_snapshot` — Status bar payload dict. Add `alert_state`, `alert_threshold`, `alert_indicator` (⚠ emoji when firing). Reference: `__init__.py:686-711`
- `get_tps_stats()` — Public API return dict. Add `alert_state` and `alert_threshold`. Reference: `__init__.py:1044`
- `_extract_provider(model)` — Already exists. Do NOT re-add or modify. Reference: `__init__.py:409`
- Zero-token filtering — `output_tokens <= 0 or duration <= 0` early-return guard at top of `_on_post_api_request`. Alert evaluation happens AFTER this guard, inside the lock. Reference: `__init__.py:626-628`

## Constraints

1. **Lock discipline**: `_evaluate_alert()` is called INSIDE `_STATE_LOCK` in `_on_post_api_request`. It must NOT acquire the lock itself (would deadlock). It trusts the caller holds the lock.
2. **No new files**: All implementation in `__init__.py`. Tests already exist in `tests/test_threshold_alerting.py`.
3. **No structural changes**: Do not refactor `__init__.py` architecture. Add alerting code as a contained feature alongside existing patterns.
4. **Backward compatibility**: `get_tps_stats()` must still return all existing fields. New fields are additive.
5. **Hook payload shape**: Tests verify `{session_id, state, tps, threshold, timestamp}` with `isinstance(timestamp, float)`.
6. **Cold-start semantics**: First N calls (default 10) collect baseline TPS samples. No alert fires during cold start. Auto-threshold = mean(cold_start_samples) × 0.5.
7. **Fixed threshold override**: When `TPS_THRESHOLD` env var is set, skip cold start and use the fixed value immediately.
8. **Rolling window**: Only last N calls (default 5) are evaluated for alert. `recent_tps_samples` is capped at `eval_window` length.
9. **Do NOT modify**: `prometheus_metrics.py`, `api.py`, `store.py`, `config.py`, `dashboard.py`, `README.md`, `.beads/beads.db`, `.env.local`, credentials.
10. **test_api.py register test**: Already expects `tps_alert` in hook_names. The register function must register this hook.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Alert globals + constants | `__init__.py` — add `_ALERT_CONFIG`, `_ALERT_HOOK_MANAGER` after existing globals (~line 98) | Any other file |
| SessionTPS slots/init | `__init__.py` — extend `_SessionTPS.__slots__` and `__init__` | Changing existing slots or removing fields |
| _evaluate_alert + _emit_alert | `__init__.py` — new functions before `_on_post_api_request` or after `_SessionTPS` class | Inline in other functions |
| _on_post_api_request integration | `__init__.py` — inside `_STATE_LOCK` block after `state.record()` | Before record(), outside lock, modifying guard conditions |
| agent._tps_snapshot | `__init__.py` — add 3 fields to snapshot dict | Removing existing snapshot fields |
| get_tps_stats | `__init__.py` — add 2 fields to return dict + fallback dict | Removing existing stats fields |
| register() | `__init__.py` — add env var reading, hook registration, manager capture | Changing existing hook registrations (post_api_request, on_session_end) |
| test_api.py | `tests/test_api.py` — only if register test needs adjustment (likely not) | Changing unrelated tests |

## Graph Context

- **Blast radius:** `__init__.py` (primary, ~1140 lines → ~1400 lines after), `tests/test_api.py` (register test already expects `tps_alert`)
- **Related beads:** `her-feat-tps-threshold-alerting-how` (original feature, closed — implementation lost in merge)
- **File history:** `__init__.py` touched by 3 prior beads (all closed): her-input-token-tracking-z7h, her-test-suite-l0o, her-session-lifecycle-cleanup-ot1
- **No blockers, no downstream dependencies** — this is an orphan bead, can be worked immediately
