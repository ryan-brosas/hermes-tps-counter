---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-cbe

**Goal:** Decompose the root `__init__.py` monolith into a proper `tps_counter/` package while preserving current plugin behavior, public API compatibility, and all 60 passing tests.

## Graph Context

- **Blast radius:** Low. `bv --robot-impact her-cbe` reported no beads found touching these files; implementation blast radius is expected to be `__init__.py`, new `tps_counter/` modules, test imports/fixtures, and possibly `pyproject.toml` / `plugin.yaml` verification.
- **Unblocks:** Architectural follow-on work for feature beads that need clean module boundaries; no explicit downstream blockers reported by `bv`.
- **Blocked by:** None reported by `br show her-cbe --json` or `bv --robot-triage`.
- **Critical path:** Yes — P1 architecture/package/refactor task; highest current top pick in triage.
- **Forecast:** 66 minutes, confidence 0.55, one agent, ETA window 2026-06-17 to 2026-06-18 from `bv --robot-forecast her-cbe`.

## Observable Truths

What must be TRUE for the goal to be achieved:

1. `from tps_counter import register, get_tps_stats, get_observability_contract, get_privacy_diagnostics` imports successfully from the new package.
2. `from __init__ import get_tps_stats` still imports successfully through the root backward-compatibility shim.
3. The plugin hook registration behavior remains unchanged: `register(ctx)` still registers `post_api_request` and exposes the same API/status surfaces.
4. Test files no longer need duplicated `clear_sessions` fixtures; `tests/conftest.py` owns the shared autouse cleanup.
5. `python3 -m pytest tests/ -v` passes all 60 tests with no assertion behavior changes.

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Package modules | Logical module boundaries for privacy, sessions, contract, and hooks | `tps_counter/__init__.py`, `tps_counter/privacy.py`, `tps_counter/session.py`, `tps_counter/contract.py`, `tps_counter/hooks.py` | Need |
| Backward-compat shim | Existing `from __init__ import ...` consumers continue to work | `__init__.py` | Need |
| Shared fixture | One canonical session cleanup fixture | `tests/conftest.py` | Need |
| Updated test imports | Tests exercise package import path instead of root module smell | `tests/test_*.py` | Need |
| Packaging/plugin validation | Confirms new layout is importable and plugin metadata still works | `pyproject.toml`, `plugin.yaml` | Verify/update only if needed |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | Map current monolith sections and create package/module scaffold | No | PRD exists; current tests known passing from project memory | `python3 -c "import pathlib; assert pathlib.Path('tps_counter').is_dir()"` |
| 2 | Move privacy, session, contract, and hook code into modules; wire `tps_counter.__init__` exports | Partially, by file ownership | Wave 1 scaffold complete | `python3 -c "from tps_counter import register, get_tps_stats, get_observability_contract, get_privacy_diagnostics"` |
| 3 | Replace root module with compatibility shim and migrate tests to package imports + shared fixture | No | Package imports verified | `python3 -c "from __init__ import get_tps_stats" && python3 -m pytest tests/ -v` |
| 4 | Verify package/plugin layout and full behavior parity | No | Waves 1-3 complete | `python3 -m pytest tests/ -v` plus import compatibility checks |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
python3 -c "from tps_counter import get_tps_stats, register, get_observability_contract, get_privacy_diagnostics"
python3 -c "from __init__ import get_tps_stats"
python3 -m pytest tests/ -v
```
