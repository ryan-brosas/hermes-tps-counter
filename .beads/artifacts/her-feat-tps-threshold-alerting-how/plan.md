---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-feat-tps-threshold-alerting-how

**Goal:** Add configurable TPS threshold alerting that evaluates rolling TPS averages in-hook and emits `tps_alert` hook events on state transitions (firing/resolved).

## Graph Context

- **Blast radius:** `__init__.py`, `tests/test_hook.py` (pattern), `README.md`
- **Unblocks:** None (leaf node in dependency graph)
- **Blocked by:** None (not blocked — fully actionable)
- **Critical path:** No (slack = 1, independent track alongside batch-session-stats)
- **Forecast:** 85 minutes (confidence: 0.35 — low velocity label "monitoring")
- **Graph position:** Isolated node (degree 0), no upstream/downstream edges

## Observable Truths

What must be TRUE for the goal to be achieved:

1. A user can set `TPS_THRESHOLD=50` and the plugin enforces that minimum tok/s
2. The rolling window of last N calls (default 5) is evaluated after each API call
3. Alert state transitions (idle→firing, firing→resolved) emit `tps_alert` hook events with `{session_id, state, tps, threshold, timestamp}`
4. Cold-start: first 10 calls establish baseline; threshold auto-set to baseline * 0.5
5. Status bar shows ⚠ indicator when alert is firing
6. All existing tests pass (no regressions)
7. New tests cover threshold crossing, state transitions, cold-start, and edge cases

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Threshold config | TPS_THRESHOLD + TPS_EVAL_WINDOW env vars, defaults | `__init__.py` | Need |
| Rolling window eval | O(1) average over last N TPS samples per session | `__init__.py` | Need |
| Alert state machine | idle/firing/resolved with timestamps per session | `__init__.py` | Need |
| Hook emission | `tps_alert` hook registered + fired on transitions | `__init__.py` | Need |
| Cold-start logic | First 10 calls → baseline → auto-threshold | `__init__.py` | Need |
| Status bar indicator | ⚠ in `_tps_snapshot` when firing | `__init__.py` | Need |
| Tests | Threshold crossing, state transitions, cold-start, edges | `tests/test_threshold_alerting.py` | Need |
| Documentation | README section for alerting config + hook contract | `README.md` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | 1.1 (threshold + rolling window + state machine + hook in `__init__.py`) | No | PRD exists | Code review: `_evaluate_alert()` callable |
| 2 | 2.1 (status bar indicator), 2.2 (tests) | Yes | Wave 1 complete | `pytest tests/test_threshold_alerting.py -v` |
| 3 | 3.1 (README docs), 3.2 (full verification) | No | Wave 2 complete | `pytest tests/ -v` — no regressions |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
pytest tests/test_threshold_alerting.py -v
pytest tests/ -v
# Confirm no regressions in existing tests
```
