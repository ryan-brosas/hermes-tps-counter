---
purpose: Product Requirements Document for a bead
updated: 2026-06-17
---

# PRD: Add Configurable TPS Threshold Alerting

**Bead:** her-feat-tps-threshold-alerting-how | **Type:** feature | **Priority:** P2
**Created:** 2026-06-17 | **Estimate:** 90 minutes

## Problem

WHEN a user runs Hermes with the tps-counter plugin THEN they have no way to know when LLM performance degrades below acceptable levels BECAUSE the plugin only records and displays TPS data reactively — there is no threshold evaluation, alerting, or notification mechanism.

**Who is affected?** Hermes users who rely on TPS monitoring for production workflows, provider comparison, and capacity planning. Secondary: downstream plugins that could consume alert events for automated failover or logging.

**Why now?** The tps-counter plugin has mature data collection (per-session, per-model, per-provider) and exposition (REST API, dashboard, status bar), but lacks the "last mile" of actionable intelligence. Without alerting, users must manually watch the status bar or poll endpoints to detect degradation — defeating the purpose of automated monitoring.

## Scope

### In Scope
- Configurable global TPS threshold (tok/s minimum)
- Rolling evaluation window (last N API calls, default 5)
- Alert state machine: idle → firing → resolved with timestamps
- Hook event emission: `tps_alert` fired on state transitions
- Default threshold auto-calculated from first 10 calls (cold-start friendly)
- Status bar integration: alert indicator when firing
- Pytest tests for threshold crossing, state transitions, edge cases

### Out of Scope
- Per-model or per-provider thresholds (future bead)
- Webhook/HTTP delivery of alerts (future bead)
- UI configuration panel for thresholds (future bead)
- Persistent alert history across restarts (future bead)
- Multi-threshold (warning/critical) tiers (future bead)

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Configurable TPS threshold | MUST | User can set `TPS_THRESHOLD` env var or config value; defaults to auto-calculated |
| 2 | Rolling evaluation window | MUST | Evaluates TPS over last N calls (default 5); configurable via `TPS_EVAL_WINDOW` |
| 3 | Alert state machine | MUST | Tracks idle/firing/resolved states with transition timestamps |
| 4 | Hook event emission | MUST | `tps_alert` hook fires on state transitions with `{session_id, state, tps, threshold, timestamp}` |
| 5 | Cold-start auto-threshold | SHOULD | First 10 calls establish baseline; threshold = baseline * 0.5 (50% degradation) |
| 6 | Status bar alert indicator | SHOULD | When alert is firing, status bar shows ⚠ indicator |
| 7 | Thread safety | MUST | All state mutations protected by existing `_STATE_LOCK` |
| 8 | Tests | MUST | pytest covers: threshold crossing, alert firing/resolved, cold-start, edge cases |

## Technical Context

**Key files:**
- `__init__.py` — Plugin core: `_SessionTPS` class, `_on_post_api_request` hook, `register()` entry point
- `tests/test_hook.py` — Existing hook tests (pattern to follow)
- `README.md` — Plugin documentation

**Architecture:**
- Plugin uses `ctx.register_hook("post_api_request", callback)` pattern
- Per-session state in `_SESSIONS` dict with `_STATE_LOCK` threading lock
- Status bar integration via `agent._tps_snapshot` dict injection
- No background threads — all evaluation happens in the hook callback (synchronous, lightweight)

**Constraints:**
- Must not break existing status bar integration
- Must not add background threads (evaluation is synchronous in hook)
- Must be thread-safe (multiple sessions can call hook concurrently)
- Must not require configuration to work (sensible defaults)

## Approach

**Chosen: In-hook synchronous threshold evaluation**

After each API call recording, evaluate the rolling TPS average for the session against the configured threshold. If the average drops below threshold, transition alert state to "firing" and emit a `tps_alert` hook. When TPS recovers above threshold, transition to "resolved" and emit another hook.

**Why this approach:**
- Zero additional infrastructure (no threads, no timers, no external services)
- Follows existing plugin pattern (synchronous hook callback)
- Leverages existing `_STATE_LOCK` for thread safety
- Low overhead: threshold evaluation is O(1) with rolling window

**Alternatives considered:** See decisions.md

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Threshold evaluation adds latency to API calls | Low | Medium | Rolling window is small (5 calls); evaluation is O(1) arithmetic |
| False positives during provider warm-up | Medium | Low | Cold-start auto-threshold with 10-call baseline period |
| Alert state corruption under high concurrency | Low | High | All state mutations under existing `_STATE_LOCK` |
| Users confused by auto-calculated threshold | Low | Low | Log threshold value at INFO level on first calculation |

## Success Criteria

- [ ] TPS threshold configurable via env var or config
    - Verify: `TPS_THRESHOLD=50 hermes` sets threshold to 50 tok/s
- [ ] Alert fires when rolling TPS drops below threshold
    - Verify: Mock API calls with degrading TPS, assert `tps_alert` hook called with state="firing"
- [ ] Alert resolves when TPS recovers
    - Verify: Mock API calls with recovering TPS, assert `tps_alert` hook called with state="resolved"
- [ ] Cold-start auto-threshold works
    - Verify: First 10 calls establish baseline, threshold = baseline * 0.5
- [ ] All existing tests pass
    - Verify: `pytest tests/ -v` — no regressions
- [ ] New tests cover all state transitions
    - Verify: `pytest tests/test_threshold_alerting.py -v` — all pass
