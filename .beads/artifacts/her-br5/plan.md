---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-br5

**Goal:** Add opt-in, dependency-free retention controls that bound the in-memory `_SESSIONS` store by session count and/or age while preserving default behavior, missing-session semantics, thread safety, and privacy-safe observability metadata.

## Graph Context

- **Blast radius:** `bv --robot-impact her-br5` reports low risk/no prior bead file touches; expected implementation blast radius is `__init__.py`, `tests/test_api.py`, and `tests/test_thread_safety.py` with possible focused new tests under `tests/` if clearer.
- **Unblocks:** None reported by bv.
- **Blocked by:** None reported by bv.
- **Critical path:** No; P2 feature and leaf-node forecast, but it is a reliability guardrail for long-lived processes.
- **Forecast:** `bv --robot-forecast her-br5` estimates 85 minutes with confidence 0.45.

## Observable Truths

What must be TRUE for the goal to be achieved:

1. With no retention env vars set, `_SESSIONS` remains process-lifetime/unbounded and existing `get_tps_stats()`, status snapshot, privacy, and thread-safety behavior stays backward-compatible.
2. Setting `HERMES_TPS_MAX_SESSIONS` to a positive integer prunes old inactive sessions so `_SESSIONS` does not exceed the configured bound after normal write-triggered pruning, without evicting the session currently being recorded when avoidable.
3. Setting `HERMES_TPS_SESSION_TTL_SECONDS` to a positive numeric age removes stale sessions according to monotonic last-update metadata while preserving recently updated sessions.
4. Reading stats for a missing or pruned session returns the existing zero-value shape and does not create a new `_SESSIONS` entry.
5. `get_observability_contract()` or diagnostics expose sanitized retention policy state, env var names, and active numeric limits without raw session IDs, model names, provider names, salts, or session listings.
6. Deterministic unit tests cover max pruning, TTL pruning without real sleeps, missing/pruned reads, contract privacy, invalid/disabled env values, and concurrent reads/writes during pruning.

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Retention policy helpers | Env parsing, disabled defaults, sanitized diagnostics, pruning decisions | `__init__.py` | Need |
| Session last-update metadata | Monotonic timestamp used for TTL and oldest-first max-session pruning | `__init__.py` | Need |
| Opportunistic pruning integration | Pruning after successful writes, preserving read-only stats semantics | `__init__.py` | Need |
| Observability contract metadata | Consumer-visible retention policy without sensitive identifiers | `__init__.py` | Need |
| API/contract tests | Default behavior, zero-shape missing/pruned reads, env parsing, contract serialization/privacy | `tests/test_api.py` | Need |
| Thread/pruning tests | Concurrency regression coverage for pruning while reads/writes occur | `tests/test_thread_safety.py` | Need |
| Verification evidence | Full test suite and code-inspection evidence for no dependency/background changes | `.beads/artifacts/her-br5/completion-evidence.json` | Verify during `/verify` |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | Baseline review and retention policy/test seams | No | PRD and current code/tests read | Focused inspection confirms helpers can be added without external deps or public shape changes |
| 2 | Core retention implementation | No | Wave 1 complete | Focused retention tests for env parsing, max-count pruning, TTL pruning, and missing-session reads pass |
| 3 | Contract/privacy metadata | Yes after Wave 2 helpers exist | Wave 2 policy model available | Contract JSON serializes and exposes env names/active limits without identifiers/secrets |
| 4 | Concurrency and regression coverage | No | Waves 2-3 complete | Thread-safety tests pass, including pruning while readers/writers run |
| 5 | Full verification and inspection | No | Waves 1-4 complete | `python3 -m pytest tests/ -v` and inspection for no dependency/background/Hermes-core changes |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
python3 -m pytest tests/test_api.py -v
python3 -m pytest tests/test_thread_safety.py -v
python3 -m pytest tests/ -v
python3 - <<'PY'
from pathlib import Path
text = Path('__init__.py').read_text(encoding='utf-8')
for forbidden in ('requests', 'http.server', 'Thread(', 'threading.Thread', 'schedule', 'sqlite3'):
    assert forbidden not in text, forbidden
print('no forbidden dependency/background/persistence markers found')
PY
br lint her-br5 --json
```
