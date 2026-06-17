---
purpose: Product Requirements Document for a bead
updated: 2026-06-17
---

# PRD: Add TPS status snapshot freshness metadata to prevent stale status bar display

**Bead:** her-feat-status-snapshot-freshness-mdz | **Type:** feature | **Priority:** P2
**Created:** 2026-06-17 | **Estimate:** 45 minutes

## Problem

WHEN the Hermes status bar reads `agent._tps_snapshot` after a session changes, a long idle period passes, or a stale plugin snapshot remains on the agent, THEN the status bar can continue displaying an old TPS value BECAUSE the current snapshot only contains throughput counters and alert fields, not machine-readable freshness metadata or session/source identity that lets consumers decide whether the data is still current.

**Who is affected?** Hermes users who rely on the TPS status bar for live throughput feedback; plugin and status-bar maintainers who need a stable snapshot contract.
**Why now?** The plugin already injects `_tps_snapshot` from `post_api_request`, and status-bar integration depends on that snapshot. Without freshness metadata, downstream consumers have no reliable way to suppress stale TPS values or detect cross-session leakage.

## Scope

### In Scope
- Extend the TPS status snapshot contract with freshness metadata while preserving all existing snapshot keys.
- Record enough timing information for consumers to compute whether the snapshot is current, such as wall-clock update time and/or monotonic update time.
- Include a safe session/source identifier so status-bar consumers can detect mismatches between the active session and the snapshot source.
- Keep the hook path lightweight and free of background refresh threads.
- Add/update tests covering snapshot freshness fields, backward compatibility, and stale/cross-session decision inputs.
- Document the snapshot freshness contract and recommended stale-threshold behavior for status-bar consumers.

### Out of Scope
- Changing the Hermes core status-bar rendering implementation beyond documenting the expected consumer behavior.
- Removing or renaming existing `_tps_snapshot` keys such as `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `input_tokens`, `total_tokens`, `alert_state`, `alert_threshold`, or `alert_indicator`.
- Persisting TPS snapshots across process restarts.
- Adding background timers, polling loops, external services, or unbounded historical snapshot storage.
- Implementing threshold alerting behavior beyond preserving existing alert fields in the snapshot.

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Preserve the existing `_tps_snapshot` data contract. | MUST | Existing keys and values used by current tests and README examples remain available after a valid `post_api_request` hook call. |
| 2 | Add machine-readable freshness metadata to every injected status snapshot. | MUST | A new snapshot includes an update timestamp suitable for stale-age calculation, preferably both `updated_at`/wall-clock seconds and `updated_monotonic` or equivalent monotonic timing input. |
| 3 | Add source identity to the snapshot. | MUST | A new snapshot includes `session_id` and/or a clearly named source identifier matching the `post_api_request` session that produced the data. |
| 4 | Enable downstream stale-status suppression without plugin-side background work. | MUST | Status-bar consumers can determine current age from snapshot fields; the plugin does not create background threads, timers, or polling loops. |
| 5 | Keep hook execution safe and lightweight. | MUST | Freshness metadata is populated in the existing `post_api_request` path using constant-time operations and does not introduce unbounded memory growth. |
| 6 | Cover freshness behavior with tests. | MUST | Tests assert freshness fields exist, are numeric/comparable, correspond to the update event, and do not break existing snapshot assertions. |
| 7 | Document the freshness contract. | SHOULD | README or integration docs describe the new fields and recommend how status-bar consumers should treat stale or session-mismatched snapshots. |
| 8 | Include migration notes for any new public semantics. | SHOULD | Documentation states that fields are additive and backward compatible; any consumer-side stale threshold is described as configurable or implementation-defined. |

## Acceptance Criteria

- Existing `_tps_snapshot` consumers continue to receive all current TPS and alert fields without renames or removals.
- Every newly injected snapshot includes numeric freshness metadata that a consumer can compare against current time to determine age.
- Every newly injected snapshot identifies the source session or equivalent producer identity.
- The implementation remains event-driven through `post_api_request` and does not add background threads, timers, polling loops, or unbounded state.
- Focused tests cover freshness metadata, source identity, and backward compatibility with existing snapshot assertions.
- Documentation describes the additive fields and recommended stale/session-mismatch handling for status-bar consumers.

## Technical Context

Relevant files:
- `__init__.py`: `_on_post_api_request` builds and assigns `agent._tps_snapshot` after recording `_SessionTPS` data. Current snapshot fields are `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `input_tokens`, `total_tokens`, plus alert fields added under `_STATE_LOCK`.
- `__init__.py`: `_SessionTPS` tracks per-session stats and has `created_at`, but it does not expose last update time or last update monotonic time in the snapshot.
- `tests/test_hook.py`: verifies valid hook calls record TPS and inject `_tps_snapshot` with existing keys.
- `tests/test_api.py` and `tests/test_session_tps.py`: verify public stats and session behavior that should remain compatible.
- `README.md`: documents status bar integration and currently shows status-bar consumers reading `agent._tps_snapshot` without stale checks.

Existing constraints from bead context:
- Preserve existing `_tps_snapshot` fields for backwards compatibility.
- Include machine-readable update time or monotonic age inputs.
- Avoid unbounded memory growth or extra background threads.
- Do not change public API semantics without migration notes.
- Prefer exposing `session_id` or source identifier when safe.
- Keep the hook path lightweight.
- Document stale-threshold behavior for status bar consumers.

## Approach

Add additive metadata when `_on_post_api_request` constructs the snapshot:
- Capture update time at snapshot creation, ideally with both `time.time()` for observability/logging and `time.monotonic()` for robust age calculations.
- Include the producing `session_id` in the snapshot so a consumer with active-session context can ignore mismatches.
- Keep all current TPS and alert fields unchanged.
- Do not add background cleanup or refresh work; freshness is a consumer decision based on snapshot metadata.
- Update tests around `test_injects_tps_snapshot_on_agent` or adjacent cases to assert new fields and preserve existing values.
- Update README status-bar integration guidance to show stale/session checks before rendering `tps_label`.

**Alternatives considered:**
- Plugin clears `agent._tps_snapshot` after a timeout: rejected because it requires timers or extra lifecycle hooks and can race with status rendering.
- Status bar infers freshness from total token changes or alert state: rejected because counters can remain unchanged during legitimate idle time and do not encode age.
- Rename or version the whole snapshot contract: rejected because the required change is additive and should remain backward compatible.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Consumers use wall-clock time for age and are affected by system clock changes. | Med | Med | Provide a monotonic timestamp or explicit monotonic age input in addition to wall-clock metadata. |
| New fields accidentally change existing snapshot values or break tests. | Low | High | Additive-only changes; keep existing assertions and add focused freshness assertions. |
| Session identifiers could expose more context than needed. | Low | Med | Use the existing hook `session_id` already passed through internal APIs; document it as source identity for local consumer checks. |
| Freshness threshold expectations differ across status-bar consumers. | Med | Low | Document recommended behavior without hard-coding policy in the plugin. |
| Reading state outside the lock creates inconsistent freshness/alert snapshots. | Low | Med | Build or finalize snapshot values in a small, lock-safe section while avoiding long operations under `_STATE_LOCK`. |

## Tasks (for epics)

| Task | Depends On | Parallel | Files |
|------|-----------|----------|-------|
| N/A — single feature bead. | N/A | N/A | N/A |

## Success Criteria

- [ ] `_tps_snapshot` includes additive freshness metadata on every successful TPS snapshot injection.
    - Verify: inspect `agent._tps_snapshot` after `_on_post_api_request(session_id="s", usage={"output_tokens": 100}, api_duration=2.0)` in a focused test.
- [ ] `_tps_snapshot` includes source identity for the session that produced the snapshot.
    - Verify: test asserts snapshot `session_id` or equivalent source field equals the hook `session_id`.
- [ ] Existing status snapshot fields remain present and semantically unchanged.
    - Verify: existing `tests/test_hook.py` assertions for `last_tps`, `avg_tps`, `peak_tps`, and token totals still pass.
- [ ] No background threads, timers, or unbounded storage are introduced.
    - Verify: code review of `__init__.py` confirms changes stay in the existing hook path and use constant-size metadata.
- [ ] Documentation explains how status-bar consumers should ignore stale or session-mismatched TPS snapshots.
    - Verify: README contains the new fields and recommended stale-threshold/session-check behavior.
- [ ] All relevant tests pass.
    - Verify: `pytest tests/test_hook.py tests/test_api.py tests/test_session_tps.py`.
- [ ] No regressions.
    - Verify: full plugin test suite passes in the implementation phase.
