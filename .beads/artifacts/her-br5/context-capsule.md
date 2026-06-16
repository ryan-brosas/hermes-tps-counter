---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-br5

## Objective

Implement opt-in max-count and TTL pruning for the in-memory `_SESSIONS` store in `hermes-tps-counter` without changing default behavior, public missing-session semantics, privacy guarantees, dependency footprint, or passive/no-background runtime model.

## Key Patterns

- `Env-var policy parsing` — Mirror the existing privacy configuration style: constants near other env names, read env on demand, normalize invalid/blank/zero/negative values to disabled, and expose only sanitized diagnostics. Reference: `__init__.py` lines 29-38 and 162-178.
- `State lock boundary` — `_STATE_LOCK` is the dictionary-level guard for `_SESSIONS`; any create/read/delete/prune operation on the dictionary must happen under this lock. Reference: `__init__.py` lines 21-23, 274-278, and 518-523.
- `Session-local counters` — `_SessionTPS.record()` mutates per-session counters and currently has no per-session lock; add last-update metadata carefully and keep existing counter semantics unchanged. Reference: `__init__.py` lines 196-250.
- `Read-only missing-session behavior` — `get_tps_stats(session_id)` must return the existing zero-value shape for absent sessions and must not create a session. Pruned sessions should be indistinguishable from never-seen sessions to this helper. Reference: `__init__.py` lines 517-531 and `tests/test_api.py` lines 27-35.
- `Additive observability contract` — `get_observability_contract()` is dependency-free, JSON-serializable, and additive; add retention policy metadata without scanning live sessions or leaking identifiers. Reference: `__init__.py` lines 342-514 and `tests/test_api.py` lines 61-129.
- `Thread-safety regression style` — Existing tests use barriers and shared errors lists to prove concurrent reads/writes do not crash. Extend this pattern for pruning instead of adding sleeps. Reference: `tests/test_thread_safety.py`.

## Constraints

1. Write code only in this repository during `/ship`; for this `/plan` repair phase, write only under `.beads/artifacts/her-br5/`.
2. Do not create a new bead, close beads, create PRs, commit, or run package/build commands as part of planning.
3. Keep runtime stdlib-only: no external dependencies, package manager invocations, REST servers, WebSockets, Prometheus exporters, SQLite persistence, background threads, daemons, schedulers, or process-wide timers.
4. Retention is disabled by default. Unset, blank, zero, negative, and invalid env values must preserve current behavior.
5. Supported env vars from the PRD are `HERMES_TPS_MAX_SESSIONS` and `HERMES_TPS_SESSION_TTL_SECONDS`.
6. Use monotonic timestamps for stale-age decisions; deterministic tests should patch time instead of sleeping.
7. Do not expose raw session IDs, model names, provider names, salts, or per-session listings in retention diagnostics or contract metadata.
8. Avoid evicting the session currently being recorded when max-session pruning runs, unless the configured bound makes retention impossible otherwise.
9. Preserve `get_tps_stats()` return shapes and existing status snapshot behavior except for additive internal retention behavior.
10. Coordinate with active work conceptually: `her-cbe` may move files in a future refactor, but this bead should target the current flat `__init__.py` layout unless the repo has changed by `/ship` time.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Planning artifact repair | `.beads/artifacts/her-br5/plan.md`, `.beads/artifacts/her-br5/tasks.md`, `.beads/artifacts/her-br5/context-capsule.md` — create/replace plan artifacts | Any source/test/dependency file — plan phase only |
| Retention implementation | `__init__.py` — private helpers, `_SessionTPS` metadata, pruning integration, additive contract metadata | `plugin.yaml`, Hermes core files, package/dependency metadata unless a later PRD update explicitly requires it |
| API/contract tests | `tests/test_api.py` or a focused new `tests/test_retention.py` — env parsing, pruning, missing-session, contract/privacy assertions | Tests that require real sleeps, network, package managers, or external services |
| Concurrency tests | `tests/test_thread_safety.py` — pruning with concurrent readers/writers using barriers | Background daemons, nondeterministic timing loops, or tests that depend on wall-clock sleeps |
| Verification evidence | `.beads/artifacts/her-br5/completion-evidence.json` during `/verify` | Closing bead, PR creation, commits, or artifacts outside this bead directory unless instructed by phase |

## Graph Context

- **Blast radius:** `bv --robot-impact her-br5` returned low risk with no prior bead file touches; expected code/test files are `__init__.py`, `tests/test_api.py`, and `tests/test_thread_safety.py`.
- **Related beads:** PRD calls out `her-6od` (SQLite write sampling), `her-cbe` (monolith/package decomposition), and `her-feat-batch-session-stats-ojy` (batch stats endpoint) as out of scope. Avoid duplicating those efforts.
- **File history:** Current project memory says `__init__.py` is the 531-line plugin entry point; tests use pytest and an autouse fixture clears `_SESSIONS` between tests.
