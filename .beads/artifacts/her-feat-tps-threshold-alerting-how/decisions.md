---
purpose: Decision log for a bead
updated: 2026-06-17
---

# Decisions: her-feat-tps-threshold-alerting-how

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Synchronous in-hook evaluation (no background threads) | Follows existing plugin pattern; zero infrastructure overhead; thread safety via existing `_STATE_LOCK` | High |
| 2 | Rolling window of last N calls (default 5) | Balances responsiveness (detects degradation quickly) vs stability (avoids false positives from single-call variance) | High |
| 3 | Auto-calculated threshold from first 10 calls | Cold-start friendly; users don't need to configure threshold to get value; 50% degradation is a reasonable default | Medium |
| 4 | Alert state machine: idle → firing → resolved | Clean state transitions; enables downstream consumers to react to both degradation and recovery | High |
| 5 | Hook-based event emission (`tps_alert`) | Follows existing `ctx.register_hook` pattern; no new infrastructure; downstream plugins can subscribe | High |
| 6 | Environment variable configuration (TPS_THRESHOLD, TPS_EVAL_WINDOW) | Consistent with Hermes config patterns; easy to set per-session; no config file required | High |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Background thread for periodic evaluation | Adds complexity; thread management overhead; existing pattern is synchronous hooks | Could cause thread safety issues; increases plugin footprint |
| 2 | SQLite-backed alert history | Overkill for Phase 1; persistence can be added later; adds dependency on store module | Increases scope; delays delivery |
| 3 | Per-model thresholds from day one | Adds complexity to state management; global threshold is sufficient for initial value; per-model is a natural extension | Scope creep; delays core alerting |
| 4 | Webhook/HTTP alert delivery | Out of scope for a plugin; hook emission is sufficient; delivery is a separate concern | Coupling; increases plugin responsibility |
| 5 | Percentage-based threshold (relative to baseline) | Harder to reason about; absolute threshold is simpler and more predictable for users | Confusion about what "50% degradation" means in practice |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | Users want proactive alerting, not just reactive display | Validated by gap analysis: project has strong data collection but no actionable intelligence | Would reduce bead value; might need different approach |
| 2 | 5-call rolling window is sufficient for detection | Unknown — may need tuning based on real-world usage | Would require configurable window (already in scope) |
| 3 | 50% degradation threshold is a reasonable default | Unknown — may be too sensitive or too lax | Would require user configuration (already supported via env var) |
| 4 | Synchronous evaluation adds negligible latency | Validated by code review: O(1) arithmetic on small window | Would require async evaluation (rejected alternative) |
| 5 | Hook emission is sufficient for downstream consumption | Validated by existing hook pattern in plugin | Would require additional delivery mechanisms (out of scope) |
