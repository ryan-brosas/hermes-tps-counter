---
purpose: Product Requirements Document for a bead
updated: 2026-06-17
---

# PRD: Add configurable call event sampling to bound SQLite write amplification

**Bead:** her-6od | **Type:** feature | **Priority:** P2
**Created:** 2026-06-17 | **Estimate:** 75 minutes

## Problem

WHEN Hermes Agent produces high-frequency LLM calls or long-running automated workflows THEN the TPS plugin writes one `call_events` row for every successful call BECAUSE historical event storage currently prioritizes complete time-series capture over bounded write volume.

**Who is affected?** Operators running Hermes in automation-heavy sessions, dashboard users relying on responsive local SQLite reads, and maintainers diagnosing plugin overhead.
**Why now?** Persistence, historical export, dashboards, Prometheus, and API rate limits already exist; the remaining operational risk is hook-path write amplification during high-volume runs.

## Scope

### In Scope
- Add configuration for call event sampling that is disabled-by-default or lossless-by-default for backward compatibility.
- Support deterministic, bounded sampling decisions on the hook path without external dependencies.
- Preserve aggregate session TPS counters even when individual historical events are sampled.
- Surface sampling metadata so exports, diagnostics, and observability contract consumers can tell whether event history is complete or sampled.
- Add tests for default compatibility, configured sampling, metadata, and edge cases.

### Out of Scope
- Changing the existing session aggregate TPS math.
- Replacing SQLite, adding queue workers, or introducing external storage dependencies.
- Modifying dashboard UX beyond exposing already-available metadata for consumers.
- Implementing `/plan`, code changes, PRs, commits, or verification in this bead-production phase.

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Preserve existing behavior by default | MUST | With default config, every valid call event that is currently persisted remains persisted and existing tests/contracts stay compatible. |
| 2 | Provide configurable event sampling | MUST | Config supports an explicit sampling mode/rate with validation, documented bounds, and no external dependencies. |
| 3 | Keep session aggregates lossless | MUST | `last_tps`, `avg_tps`, `peak_tps`, total tokens, and duration remain based on every valid hook event regardless of historical sampling. |
| 4 | Bound hook-path overhead | MUST | Sampling decision uses O(1) in-memory logic and does not require extra SQLite reads before deciding whether to write an event row. |
| 5 | Mark sampled history clearly | MUST | Historical export/API/contract metadata can report sampling mode/rate and whether returned call-event history may be incomplete. |
| 6 | Count sampled/skipped events | SHOULD | Diagnostics or operational metrics expose how many event rows were skipped due to sampling without leaking sensitive identifiers. |
| 7 | Cover configuration and edge cases | SHOULD | Tests cover disabled/default behavior, rate validation, always/never sample boundaries, deterministic decisions, and metadata output. |

## Technical Context

Relevant current surfaces:
- `__init__.py` handles hook ingestion, in-memory session aggregates, privacy redaction, persistence calls, and status snapshots.
- `store.py` is expected to own SQLite `call_events` persistence and export/query helpers from prior closed beads.
- `config.py` owns typed config defaults, environment overrides, TOML support, and validation.
- `api.py` exposes REST, WebSocket, export, health, and diagnostics surfaces.
- `prometheus_metrics.py` may contain operational counters if Prometheus is available.
- `README.md` and `get_observability_contract()` document public behavior and compatibility rules.

Constraints:
- Stdlib-only implementation unless Ryan explicitly approves a dependency.
- Do not break privacy redaction guarantees: raw session/model/provider identifiers must not leak through sampling metadata.
- Do not duplicate existing API rate limiting, historical export, privacy redaction, or health diagnostics beads.
- The active monolith decomposition bead may move code; implementation should be planned after checking current file layout.

## Approach

Add an explicit call-event sampling policy in configuration, applied only to historical `call_events` persistence. The hook should always update in-memory/session aggregates, then decide whether to persist the per-call event using a fast deterministic policy. Export and contract surfaces should expose metadata indicating the configured sampling policy and completeness semantics.

Recommended implementation shape for the later `/plan` phase:
1. Extend config with fields such as `event_sampling_enabled`, `event_sampling_rate`, and optionally a deterministic seed/scope.
2. Add a small helper for sampling decisions using counters or deterministic hashing rather than randomness that is hard to test.
3. Wire the helper immediately before per-call event insertion only; do not skip aggregate updates.
4. Add counters/diagnostics for skipped sampled events.
5. Add metadata to export responses and observability contract so downstream consumers do not misinterpret sampled history as complete.
6. Document behavior and default compatibility.

**Alternatives considered:**
- Sampling all stats, including aggregate TPS: rejected because it would make core TPS stats inaccurate.
- Random sampling with `random.random()`: rejected because it is harder to test and reproduce.
- Background batching only: useful later, but it does not by itself bound total write volume.
- Relying only on retention cleanup: rejected because retention limits storage over time, not write amplification during bursts.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Users assume sampled exports are complete | Med | High | Add explicit response/contract metadata and README wording. |
| Sampling introduces bias in trend analysis | Med | Med | Prefer deterministic evenly-distributed sampling and clearly document limitations. |
| Implementation accidentally skips aggregate stats | Low | High | Tests must assert aggregate counters include sampled-out events. |
| Config naming conflicts with existing config module | Med | Low | Inspect current `config.py` before final names in `/plan`. |
| Prometheus/diagnostics surface is unavailable in minimal installs | Low | Low | Sampling must work without prometheus_client and expose metadata through core helpers/API where possible. |

## Success Criteria

- [ ] Default configuration persists complete historical call-event rows as before.
    - Verify: focused tests compare default persisted event count with valid hook count.
- [ ] Configured sampling reduces persisted historical rows while keeping aggregate session stats exact.
    - Verify: tests assert aggregate totals count all valid events and stored event rows are sampled.
- [ ] Sampling policy is documented in API/export/contract metadata.
    - Verify: focused tests assert metadata fields and README sections exist.
- [ ] Invalid sampling configuration fails predictably with clear validation errors.
    - Verify: config validation tests.
- [ ] No regressions in privacy redaction, API response compatibility, or plugin registration.
    - Verify: affected tests selected during `/plan` and `/verify` phases.
