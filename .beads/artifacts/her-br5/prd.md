---
purpose: Product Requirements Document for a bead
updated: 2026-06-17
---

# PRD: Add bounded in-memory session retention controls

**Bead:** her-br5 | **Type:** feature | **Priority:** P2
**Created:** 2026-06-17 | **Estimate:** 60 minutes

## Problem

WHEN hermes-tps-counter observes many distinct sessions in a long-lived Hermes process THEN `_SESSIONS` grows without an explicit bound BECAUSE the current implementation keeps every observed session in memory until process exit.

**Who is affected?** Long-running Hermes CLI or daemon users, plugin maintainers, and observability consumers that rely on stable in-process TPS helpers.
**Why now?** The project has added status snapshots, privacy diagnostics, observability contract metadata, and planned persistence/export work; unbounded in-memory retention is now the next reliability gap for long-lived deployments.

## Scope

### In Scope
- Add dependency-free retention controls for the in-memory `_SESSIONS` store.
- Support a configurable maximum number of retained sessions with a safe default that preserves current behavior unless explicitly enabled.
- Support age-based pruning using monotonic or otherwise robust timestamps so stale sessions can be removed without affecting active sessions.
- Ensure pruning runs opportunistically during normal hook/helper calls; do not add background threads, daemons, schedulers, or external dependencies.
- Preserve `get_tps_stats(session_id)` semantics for missing/pruned sessions: return zero counters without raising.
- Extend observability/privacy contract metadata so consumers can see whether retention is enabled and what pruning policy is active without exposing raw session identifiers.
- Cover pruning with deterministic tests that avoid real sleeps where practical.

### Out of Scope
- SQLite persistence, historical exports, or retention for persisted rows.
- REST, WebSocket, Prometheus, or dashboard APIs.
- Sampling of call events or SQLite write amplification controls covered by `her-6od`.
- Monolith/package decomposition covered by `her-cbe`.
- Batch session stats endpoint work covered by `her-feat-batch-session-stats-ojy`.
- Any changes to Hermes core status-bar rendering.

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Provide opt-in max-session retention for `_SESSIONS`. | MUST | Setting a documented env var to a positive integer causes the plugin to retain no more than that many inactive sessions after pruning. |
| 2 | Provide opt-in stale-session age pruning. | MUST | Setting a documented env var to a positive age removes sessions older than that age while preserving sessions updated within the threshold. |
| 3 | Preserve default behavior. | MUST | With no retention env vars set, existing tests and public helper behavior remain backward-compatible. |
| 4 | Preserve missing-session semantics. | MUST | `get_tps_stats()` returns the existing zero-value structure for pruned sessions and never recreates pruned sessions merely by reading stats. |
| 5 | Keep retention dependency-free and non-invasive. | MUST | No external packages, background threads, REST servers, schedulers, or process-wide timers are introduced. |
| 6 | Make policy visible to consumers. | SHOULD | `get_observability_contract()` or related diagnostics expose enabled/disabled state, env var names, and active numeric limits without raw session identifiers. |
| 7 | Keep privacy guarantees intact. | MUST | Retention diagnostics do not expose raw session IDs, model names, provider names, salts, or other sensitive identifiers. |
| 8 | Cover concurrency edge cases. | SHOULD | Tests exercise pruning while reads/writes occur and confirm no crashes or inconsistent public return shapes. |

## Technical Context

Relevant current files:

- `__init__.py`
  - `_SESSIONS: Dict[str, _SessionTPS]` is the only in-memory session store.
  - `_STATE_LOCK` guards `_SESSIONS` dictionary creation/read access.
  - `_SessionTPS.record()` updates counters but no retention metadata exists today.
  - `_on_post_api_request()` calls `_get_session(session_id)` and records successful calls.
  - `get_tps_stats(session_id)` reads `_SESSIONS` and returns zero counters for absent sessions.
  - `get_observability_contract()` already exposes dependency-free static/dynamic metadata for consumer expectations.
- `tests/test_thread_safety.py` verifies concurrent reads/writes do not crash.
- `tests/test_api.py` verifies missing-session zero return shape and contract behavior.
- Project conventions require stdlib-only Python 3.11+, type hints, and explicit locking around shared session state.

## Approach

Add a small retention policy layer inside the plugin that reads environment variables on demand, mirrors the existing privacy-env style, and prunes `_SESSIONS` while holding `_STATE_LOCK`. Track a last-updated monotonic timestamp per session (or equivalent metadata) and use it for age pruning. Apply pruning opportunistically after successful writes and optionally before stats reads, while ensuring a stats read never creates a session. For max-session pruning, evict the oldest inactive sessions first and never evict the session currently being recorded if avoidable.

Suggested env names:

- `HERMES_TPS_MAX_SESSIONS`: positive integer; unset/zero/invalid means unbounded.
- `HERMES_TPS_SESSION_TTL_SECONDS`: positive float/integer; unset/zero/invalid means no TTL pruning.

**Alternatives considered:**

- Background cleanup thread: rejected because the plugin is currently dependency-free and passive; background work complicates tests and process shutdown.
- Rely only on future SQLite retention: rejected because the current in-memory store remains active even if persistence is added later.
- Always enforce a hard default limit: rejected because it could surprise existing consumers relying on process-lifetime stats.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Pruning active sessions causes missing TPS during status display. | Medium | Medium | Evict oldest inactive sessions and preserve the currently recorded session during write-triggered pruning. |
| Retention metadata changes public or test-facing shapes. | Medium | Medium | Keep new fields internal unless documented in contract diagnostics; preserve `get_tps_stats()` shape. |
| Lock contention increases hook latency. | Low | Medium | Keep pruning O(number of sessions), run opportunistically, and skip entirely when limits are disabled. |
| Invalid env var values cause crashes or surprising behavior. | Medium | Medium | Treat invalid, negative, zero, or non-numeric values as disabled and expose sanitized diagnostics. |
| Privacy leak through retention diagnostics. | Low | High | Report only policy numbers and counts, never session identifiers. |

## Tasks (for epics)

Not an epic. Task decomposition will be produced by bead-fix during `/plan`.

## Success Criteria

- [ ] Retention is disabled by default and existing TPS/session behavior remains compatible.
    - Verify: `python3 -m pytest tests/ -v` during `/verify` phase.
- [ ] Enabling `HERMES_TPS_MAX_SESSIONS` prunes the in-memory session dictionary to the configured bound.
    - Verify: deterministic unit test with multiple synthetic sessions.
- [ ] Enabling `HERMES_TPS_SESSION_TTL_SECONDS` prunes stale sessions without sleeping in real time.
    - Verify: time/monotonic patch-based unit test.
- [ ] Pruned sessions return the existing zero-value stats shape.
    - Verify: unit test for `get_tps_stats(pruned_session_id)`.
- [ ] Retention policy is documented in the observability contract or diagnostics without exposing sensitive identifiers.
    - Verify: JSON-serializable contract test and privacy diagnostic assertion.
- [ ] No external dependencies, background threads, package manager commands, or Hermes core changes are required.
    - Verify: code inspection and unchanged dependency metadata.
