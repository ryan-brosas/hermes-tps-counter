---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-cbe

## Objective

Refactor the current 531-line root `__init__.py` into a `tps_counter/` package with clear module boundaries while preserving every existing import, hook, privacy, observability, and session-stat behavior.

## Key Patterns

- `Backward-compatible package migration` — New code should live under `tps_counter/`, but root `__init__.py` must remain as a thin shim using `from tps_counter import *`. Reference: `.beads/artifacts/her-cbe/prd.md`
- `Session state lock discipline` — `_STATE_LOCK` protects the `_SESSIONS` dict; do not weaken thread-safety during extraction. Reference: `__init__.py`
- `Privacy policy is dependency-free` — Keep HMAC-SHA256 pseudonymization, redacted/omitted treatments, env-var parsing, and diagnostics shape exactly as-is. Reference: `__init__.py`
- `Tests prefer package imports` — Update tests to import from `tps_counter`, while preserving root shim compatibility for external consumers. Reference: `tests/test_api.py`, `tests/test_hook.py`, `tests/test_privacy.py`, `tests/test_session_tps.py`, `tests/test_thread_safety.py`
- `Shared pytest cleanup` — `clear_sessions` should live once in `tests/conftest.py` and clear `_SESSIONS` before and after tests under `_STATE_LOCK`. Reference: `tests/test_api.py`

## Constraints

1. This bead is pure refactoring: no new features, no public API behavior changes, no performance optimization work.
2. Keep stdlib-only implementation; do not add external dependencies or frameworks.
3. Preserve compatibility for `from __init__ import X` and prefer `from tps_counter import X` in tests.
4. Preserve plugin behavior: `register(ctx)` must still register the `post_api_request` hook and expose the same status/observability surfaces.
5. Avoid circular imports: `privacy`, `session`, and `contract` should be lower-level modules; `hooks` can compose them; `tps_counter/__init__.py` re-exports.
6. Do not modify unrelated project files. During implementation, expected write scope is root shim, new package files, tests, and only packaging metadata if required.
7. Plan-only artifact repair is limited to `.beads/artifacts/her-cbe/`; implementation must not happen in this phase.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Privacy extraction | `tps_counter/privacy.py` — move privacy constants/classes/helpers; `tps_counter/__init__.py` — re-export as needed | Behavior changes to redaction output or env var names |
| Session extraction | `tps_counter/session.py` — move session state/stats; `tps_counter/__init__.py` — re-export as needed | Removing `_STATE_LOCK`, changing stat key names, changing rounding semantics |
| Contract extraction | `tps_counter/contract.py` — move `get_observability_contract` and metadata | Changing JSON contract shape or plugin metadata values |
| Hook extraction | `tps_counter/hooks.py` — move `_on_post_api_request` and `register` | Changing hook name, token/duration extraction semantics, or status snapshot fields |
| Compatibility shim | `__init__.py` — replace with docstring and package re-export | Duplicating full implementation in both root and package |
| Test cleanup | `tests/conftest.py`, `tests/test_*.py` — centralize fixture and update imports | Changing test assertions or deleting behavioral coverage |
| Packaging verification | `pyproject.toml`, `plugin.yaml` — verify/update only if required | Unrelated metadata, dependency, or manifest changes |

## Graph Context

- **Blast radius:** `bv --robot-impact her-cbe` returned low risk with no beads found touching these files. Expected code blast radius is `__init__.py`, `tps_counter/*.py`, `tests/conftest.py`, `tests/test_*.py`, and possibly `pyproject.toml` / `plugin.yaml`.
- **Related beads:** Triage shows other active work: `her-feat-batch-session-stats-ojy` and `her-chore-docs-quickstart-sj2`; avoid overlapping edits if those tasks are active.
- **File history:** `bv --robot-file-hotspots` returned no hotspots; no file-level bead links were reported.
