---
purpose: Decision log for a bead
updated: 2026-06-17
---

# Decisions: her-feat-status-snapshot-freshness-mdz

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Treat freshness metadata as additive fields on the existing `agent._tps_snapshot` dictionary. | Preserves current status-bar and test consumers while giving new consumers enough information to detect stale data. | High |
| 2 | Include both source identity and update-time metadata in each snapshot. | Age alone cannot detect cross-session reuse, and session identity alone cannot detect long-idle stale values. Both are needed for reliable suppression. | High |
| 3 | Prefer monotonic timing for stale-age calculation, with wall-clock time useful for diagnostics. | Monotonic time is robust to system clock changes; wall-clock timestamps are easier to inspect in logs or debugging output. | High |
| 4 | Leave stale-threshold policy to status-bar consumers rather than enforcing it in the plugin. | The plugin only receives API-call events; consumers own rendering cadence and active-session context. This avoids background threads and preserves lightweight hook behavior. | High |
| 5 | Keep existing TPS and alert fields unchanged. | The bead explicitly requires backward compatibility for `_tps_snapshot` fields and no public API semantic break without migration notes. | High |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Clear or mutate `agent._tps_snapshot` from a plugin timer after a timeout. | Requires background scheduling or lifecycle hooks, adds race potential, and violates the lightweight/no-extra-thread constraint. | Can create flicker, races, thread-safety issues, and harder shutdown behavior. |
| 2 | Replace the snapshot with a versioned or nested schema. | Unnecessary for an additive metadata change and could break existing consumers expecting top-level keys. | Status bar integrations and tests may fail or silently stop rendering TPS. |
| 3 | Infer freshness from token totals, alert state, or changing TPS values. | Counters and alert state describe throughput, not observation age or source session. | Stale values may still appear current, especially when a session is idle. |
| 4 | Persist snapshot freshness state across restarts. | The problem concerns live status rendering; persistence is out of scope and may imply stale data after restart. | Consumers could display old process data as if it belonged to the current process. |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | `post_api_request` provides the producing `session_id`, and that value is safe to store in the local in-process snapshot. | Validated by existing `_on_post_api_request` implementation and tests. | If session IDs are unavailable or unsafe, use a less sensitive source identifier and adjust documentation. |
| 2 | Status-bar consumers can access their active session and current monotonic time when deciding whether to render TPS. | Unknown for all downstream consumers; README integration guidance can show expected behavior. | If consumers cannot access these values, plugin may need to expose a precomputed expiry/stale-after field. |
| 3 | Additive snapshot fields do not require a major public API migration. | Validated by the current dictionary-style consumer pattern in README and tests. | If consumers validate exact keys, documentation must include migration notes and tests may need compatibility fixtures. |
| 4 | No implementation should be performed during this artifact repair pass. | Validated by user rule. | Implementation belongs to a later phase and must not be mixed with create-phase artifact repair. |
