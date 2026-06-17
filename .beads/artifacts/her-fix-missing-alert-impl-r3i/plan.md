---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-fix-missing-alert-impl-r3i

**Goal:** Implement the TPS threshold alerting code in `__init__.py` that was lost during merge of PR #28, making all 19 `test_threshold_alerting.py` tests pass with zero regressions.

## Graph Context

- **Blast radius:** `__init__.py` (primary), `tests/test_api.py` (register test already expects `tps_alert` hook)
- **Unblocks:** None (orphan bead, no downstream dependencies)
- **Blocked by:** None (no upstream dependencies, slack=1, actionable)
- **Critical path:** No (independent, no edges in graph)
- **Forecast:** ~60 min estimated (bv forecast: 66 min, confidence 0.35). Realistic for one session.

## Observable Truths

What must be TRUE for the goal to be achieved:

1. `python -m pytest tests/test_threshold_alerting.py` — 19/19 pass, zero errors
2. `python -m pytest tests/test_api.py::TestRegister::test_register_calls_ctx_register_hook` — passes (tps_alert hook registered)
3. `python -m pytest tests/` — all previously-passing tests still pass (no regressions)
4. `from __init__ import _ALERT_CONFIG, _evaluate_alert, _ALERT_HOOK_MANAGER` succeeds
5. `_SessionTPS` instances have `alert_state`, `alert_threshold`, `alert_fired_at`, `alert_resolved_at`, `cold_start_samples`, `recent_tps_samples`
6. `get_tps_stats("sid")` returns `alert_state` and `alert_threshold` keys
7. `agent._tps_snapshot` includes `alert_state`, `alert_threshold`, `alert_indicator`

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| PRD | Requirements, scope, success criteria | `.beads/artifacts/her-fix-missing-alert-impl-r3i/prd.md` | Done |
| Test file | Executable specification (19 tests) | `tests/test_threshold_alerting.py` | Done |
| Implementation | Alerting code | `__init__.py` | Need |
| register fix | tps_alert hook registration | `__init__.py` (register()) | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | 1.1–1.4 (globals, slots, _evaluate_alert, _emit_alert) | No (single file) | None | `python -c "from __init__ import _ALERT_CONFIG, _ALERT_HOOK_MANAGER, _evaluate_alert, _emit_alert; print(dir(_SessionTPS))"` |
| 2 | 2.1–2.3 (integrate into hook, snapshot, get_tps_stats) | No (single file) | Wave 1 complete | `python -m pytest tests/test_threshold_alerting.py -q --tb=short` — imports work, tests run |
| 3 | 3.1–3.2 (register env vars, hook, test_api pass) | No (single file) | Wave 1 complete | `python -m pytest tests/test_api.py::TestRegister -q` |
| 4 | 4.1–4.2 (full test verification) | No | Waves 1-3 complete | Full suite passes |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
python -m pytest tests/test_threshold_alerting.py -v
python -m pytest tests/test_api.py::TestRegister -v
python -m pytest tests/ -q --tb=short
```
