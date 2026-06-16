---
purpose: Decision log for a bead
updated: 2026-06-17
---

# Decisions: her-br5

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Create a new P2 feature bead for bounded in-memory session retention. | Existing active/open beads cover monolith decomposition, SQLite sampling, and batch stats; none cover unbounded `_SESSIONS` growth. Long-lived Hermes processes need a reliability guardrail before broader observability surfaces expand. | High |
| 2 | Make retention opt-in by default. | The current public behavior retains per-session stats for process lifetime. A default hard limit could surprise existing in-process consumers and invalidate status/helper expectations. | High |
| 3 | Use environment-variable configuration modeled after existing privacy controls. | The project already uses `HERMES_TPS_PRIVACY_*` env vars for dependency-free runtime policy. Retention controls can follow the same pattern without introducing config files or dependencies. | High |
| 4 | Prefer opportunistic pruning over background cleanup. | The plugin currently runs passively from hooks and helpers. Opportunistic pruning avoids threads, schedulers, lifecycle complexity, and shutdown concerns. | High |
| 5 | Expose retention policy, not session identities, through diagnostics/contract metadata. | Consumers need to know whether pruning can happen, but diagnostics must preserve the project's privacy posture. | High |
| 6 | Defer implementation sequencing to bead-fix `/plan`. | Phanes is only responsible for `/brainstorm` → `/create`; plan/tasks/context-capsule artifacts are intentionally out of scope for this phase. | High |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Add a background sweeper thread. | Adds concurrency and lifecycle complexity to a plugin that currently has no background work. | Harder shutdown semantics, flaky tests, and surprise runtime overhead. |
| 2 | Always enforce a default maximum session count. | Changes backward-compatible process-lifetime stats behavior without explicit operator opt-in. | Existing users may see sessions disappear unexpectedly. |
| 3 | Depend on future SQLite retention instead of addressing in-memory state. | Persistence and historical export are separate concerns; `_SESSIONS` can still grow in current and future versions. | Long-lived processes remain vulnerable to memory growth. |
| 4 | Implement REST/admin endpoints for clearing sessions as part of this bead. | REST/API surfaces are explicitly absent in the current contract and would expand scope beyond retention controls. | Scope creep into server routing, auth, and API compatibility. |
| 5 | Duplicate `her-6od` by sampling recorded calls. | Sampling targets persisted call event write amplification; it does not bound live session dictionary size. | Confuses storage optimization with memory-retention policy. |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | `_SESSIONS` remains the authoritative in-memory store for live session TPS during this bead. | Validated by current `__init__.py` and tests. | If `her-cbe` lands first, implementation paths move into package modules but requirements remain valid. |
| 2 | Operators prefer current behavior unless retention is explicitly enabled. | Inferred from existing backward-compatible privacy defaults and API tests. | If a hard default is desired, PRD requirements must be amended before implementation. |
| 3 | Retention can be implemented with stdlib-only code. | Validated by current project conventions and simple policy needs. | Any dependency proposal would require separate approval and likely a new bead. |
| 4 | Pruned sessions should behave exactly like never-observed sessions to public helpers. | Validated by existing missing-session helper behavior. | If consumers need tombstone diagnostics, contract and privacy requirements must be expanded. |
| 5 | Planning and wave decomposition will be handled by bead-fix. | Stated directly in the user instructions. | If no separate planning phase occurs, implementation agents will need to derive tasks from PRD only. |
