---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-feat-status-snapshot-freshness-mdz

**Goal:** Add additive freshness metadata (timestamps + session_id) to every TPS status snapshot so consumers can suppress stale or cross-session values without plugin-side background work.

## Graph Context

- **Blast radius:** None — isolated bead, no files currently linked to other beads.
- **Unblocks:** None downstream.
- **Blocked by:** None.
- **Critical path:** No (slack = 1, no downstream dependents).
- **Forecast:** ~85 min estimated (45 min bead estimate × 1.3 feature factor).

## Observable Truths

1. After `_on_post_api_request(session_id="s", usage={"output_tokens": 100}, api_duration=2.0)`, `agent._tps_snapshot` contains `updated_at` (float), `updated_monotonic` (float), and `session_id` (str) in addition to all existing keys.
2. Existing `tests/test_hook.py` assertions for `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `input_tokens`, `total_tokens`, `alert_state`, `alert_threshold`, `alert_indicator` still pass unchanged.
3. No new threads, timers, polling loops, or unbounded storage are introduced — all changes stay in the existing `_on_post_api_request` hook path.
4. README documents the new fields and recommended stale-threshold / session-mismatch handling.

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| PRD | Requirements + acceptance criteria | `prd.md` | Done |
| Plan | Wave sequencing | `plan.md` | This file |
| Tasks | Task decomposition | `tasks.md` | Writing now |
| Context capsule | Ship-phase agent context | `context-capsule.md` | Writing now |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | T1.1 (Add freshness fields to snapshot dict) | No | PRD reviewed | Existing tests pass after change |
| 2 | T2.1 (Add freshness test assertions) | No | Wave 1 done — fields exist | `pytest tests/test_hook.py tests/test_api.py tests/test_session_tps.py` |
| 3 | T3.1 (Update README docs) | No | Wave 1 done — fields finalized | README contains stale/session guidance |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Acceptance Criteria

- [ ] `agent._tps_snapshot` contains `updated_at`, `updated_monotonic`, `session_id` after a hook call.
- [ ] All existing snapshot keys remain present and unchanged.
- [ ] No new threads, timers, or polling loops in `__init__.py`.
- [ ] Tests for freshness fields pass alongside existing snapshot tests.
- [ ] README documents the new fields and stale/session-mismatch guidance.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
pytest tests/test_hook.py tests/test_api.py tests/test_session_tps.py
# Code review: confirm no new imports of threading/timer/sleep in __init__.py
```
