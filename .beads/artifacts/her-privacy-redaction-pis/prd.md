---
purpose: Product Requirements Document for a bead
updated: 2026-06-17
---

# PRD: Add configurable privacy redaction for TPS identifiers across observability outputs

**Bead:** her-privacy-redaction-pis | **Type:** feature | **Priority:** P2
**Created:** 2026-06-17 | **Estimate:** 75 minutes

## Problem

WHEN TPS observability data is surfaced through status snapshots, Python helpers, future REST/WebSocket surfaces, Prometheus labels, dashboard JSON, logs, or exports THEN raw identifiers such as `session_id`, `model`, `provider`, and future identifier-like fields can leak into shareable telemetry BECAUSE the plugin currently emits those values directly or documents them as consumer-facing fields without a centralized configurable redaction policy.

**Who is affected?** Hermes users sharing screenshots/logs/exports, operators exposing TPS data to dashboards or Prometheus, and maintainers extending the plugin with new observability surfaces.
**Why now?** Recent observability work added freshness metadata and a machine-readable contract. The graph places this bead as an independent Track C security/config/observability feature with high centrality; adding privacy semantics now prevents new consumers from standardizing on raw identifiers.

## Scope

### In Scope
- Add a single configurable redaction policy for TPS observability identifiers, initially covering `session_id`, `model`, `provider`, and future identifier-like metadata.
- Support deterministic pseudonymous values so consumers can group records without seeing raw identifiers.
- Preserve current behavior and public response contracts when privacy redaction is disabled.
- Apply redaction consistently before data leaves trusted in-process state through `_tps_snapshot`, `get_tps_stats`-style API responses, the observability contract, logs, dashboard data, future REST/WebSocket payloads, Prometheus labels, and historical exports when those surfaces are present.
- Keep implementation dependency-free and low overhead on the hook path.
- Document which fields are raw, redacted, hashed/pseudonymous, or omitted under each privacy mode.
- Add focused tests for disabled-mode compatibility, deterministic pseudonyms, and coverage of every available outbound surface.

### Out of Scope
- Implementing new REST routes, WebSocket streams, Prometheus exporters, dashboard features, or historical export endpoints that are not present on the implementation branch.
- Replacing the TPS calculation model or changing `last_tps`, `avg_tps`, `peak_tps`, token counters, freshness timestamps, or session accumulation behavior.
- Encrypting stored data at rest or introducing an external secrets service.
- Removing internal raw identifiers needed for in-process session lookup and correctness.
- Renaming existing public keys in disabled mode.

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Provide one shared redaction policy for TPS identifier fields. | MUST | A documented helper/config path governs `session_id`, `model`, `provider`, and future identifier-like fields instead of duplicating ad hoc transformations per surface. |
| 2 | Preserve backward compatibility when redaction is disabled. | MUST | With privacy mode off/default-compatible, existing `get_tps_stats`, `_tps_snapshot`, registration, and current tests continue to observe existing raw values and field names. |
| 3 | Support deterministic pseudonymous identifiers. | MUST | The same raw value maps to the same non-raw value for a stable configured scope/salt, while different raw values remain distinguishable enough for grouping. |
| 4 | Prevent raw identifiers from leaving trusted state when redaction is enabled. | MUST | Status snapshots, Python helper/API results, observability contract metadata, debug logs, dashboard payloads, future REST/WebSocket payloads, Prometheus labels, and exports use redacted/hashed/omitted values for covered fields when available. |
| 5 | Avoid leaking secrets in configuration or diagnostics. | MUST | Any salt/secret used for pseudonyms is not emitted in logs, contract output, snapshots, API responses, exports, or README examples. |
| 6 | Keep hook-path overhead low and dependency-free. | MUST | Redaction uses standard-library primitives and bounded per-field work; no network calls, background workers, or external packages are introduced. |
| 7 | Make privacy mode discoverable without exposing raw identifiers. | SHOULD | The observability contract or diagnostics indicate the active redaction mode and per-field treatment (`raw`, `redacted`, `pseudonymized`, `omitted`) without showing secret material. |
| 8 | Support per-field policy evolution. | SHOULD | The design allows allowlist/denylist or per-field overrides so future identifier-like fields can be added safely. |
| 9 | Document consumer-facing behavior. | SHOULD | README or contract docs explain modes, defaults, field treatment, deterministic grouping guarantees, and migration guidance. |
| 10 | Cover privacy behavior with focused tests. | SHOULD | Tests assert deterministic pseudonyms, disabled-mode backward compatibility, no raw IDs in enabled outbound surfaces, and unchanged TPS counters. |

## Acceptance Criteria

- Existing disabled/default-compatible behavior remains backward compatible for `_tps_snapshot`, `get_tps_stats`, registration, and the observability contract.
- When redaction is enabled, raw `session_id`, `model`, `provider`, and configured identifier-like fields are not emitted by available outbound observability surfaces.
- Deterministic pseudonyms are stable for the same configured scope and do not contain the raw source value.
- Redaction configuration and diagnostics never expose salts, secrets, or reversible material.
- Documentation and/or contract metadata clearly state per-field treatment under each privacy mode.
- Focused tests cover disabled compatibility, deterministic pseudonyms, enabled-mode outbound redaction, and unchanged TPS counters.

## Technical Context

Relevant current files and patterns:
- `__init__.py` owns `_on_post_api_request`, per-session `_SESSIONS`, `_tps_snapshot` injection, `get_tps_stats(session_id)`, `get_observability_contract()`, and debug logging.
- `_on_post_api_request` currently reads raw `session_id` from hook kwargs, uses it as the internal state key, writes it into `agent._tps_snapshot`, and logs `session_id[:8]` at debug level.
- `get_tps_stats(session_id)` currently accepts a raw session id as lookup input and returns aggregate counters. It does not currently echo the session id, but future response surfaces may.
- `get_observability_contract()` currently describes `status_snapshot.fields.session_id` as raw source identity and marks REST/WebSocket/Prometheus surfaces unavailable on this branch.
- `README.md` documents status snapshot freshness and session mismatch handling using `snapshot["session_id"]` as the active-session comparison value.
- `tests/test_hook.py` asserts injected snapshot values including `session_id`; `tests/test_api.py` asserts contract fields and absent optional surfaces.
- The bead context allows future files such as `config.py`, `api.py`, `dashboard.py`, `prometheus_metrics.py`, `store.py`, `README.md`, and `tests/`, but the current branch may only contain the core plugin files.

Graph context:
- `bv --robot-plan` places `her-privacy-redaction-pis` in Track C as a single actionable P2 feature with no blocked dependencies.
- `bv --robot-suggest` notes a possible relationship to `her-feat-observability-contract-bq6`; implementation should use the observability contract as the metadata location for privacy semantics when present.
- `bv --robot-search` confirms the exact bead is the matching existing work item; no new bead should be created.

## Approach

Keep raw identifiers inside trusted state for correctness, but introduce a shared outbound redaction layer used immediately before data is exposed. Prefer a small policy/helper in the core plugin or a lightweight config module that:
- Defines modes such as disabled/raw-compatible and enabled pseudonymized/redacted behavior.
- Treats fields by name so `session_id`, `model`, `provider`, and future identifier-like fields have explicit outcomes.
- Uses deterministic standard-library hashing/HMAC with a configurable salt/secret for pseudonyms, while never exposing the salt.
- Lets callers redact a single value or a nested payload before returning/logging/exporting it.
- Separates lookup inputs from output payloads: callers may still pass raw `session_id` to retrieve stats, but returned/shared data should follow the configured privacy policy.
- Updates `get_observability_contract()`/README to describe redaction modes and active field treatment without promising unavailable surfaces.

**Alternatives considered:** README-only privacy guidance: rejected because it does not prevent accidental leakage in code. Per-surface redaction snippets: rejected because drift would be likely as observability surfaces grow. Fully opaque random IDs per event: rejected because consumers need deterministic grouping across snapshots/metrics. Removing identifiers entirely: rejected as too limiting for session-mismatch checks and aggregate observability; omission can remain a per-field option where grouping is not needed.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Redaction breaks current consumers that compare raw `session_id`. | Med | High | Keep disabled mode backward-compatible and document enabled-mode migration; tests must cover both paths. |
| Raw identifiers leak through one outbound surface. | Med | High | Centralize redaction and add tests for every available surface, including logs and contract metadata. |
| Pseudonyms are reversible or vulnerable to dictionary attacks. | Med | High | Use keyed standard-library hashing/HMAC with a configurable secret/salt and never expose it. |
| Prometheus label cardinality increases through pseudonyms. | Med | Med | Keep label guidance explicit; allow omission or coarse redaction for high-cardinality labels. |
| Hook-path latency increases. | Low | Med | Use bounded per-field transformations and avoid scanning all sessions or doing I/O in the hook path. |
| Contract overstates unavailable REST/WebSocket/Prometheus surfaces. | Low | Med | Mark absent surfaces unavailable and document privacy behavior as a policy for current and future outbound data. |

## Tasks (for epics)

Not an epic.

## Success Criteria

- [ ] A single redaction policy/helper exists for identifier-like TPS observability fields.
    - Verify: code review confirms outbound surfaces call the shared helper instead of duplicating transformations.
- [ ] Disabled/default-compatible mode preserves existing public behavior.
    - Verify: focused tests show current `_tps_snapshot`, `get_tps_stats`, and contract expectations remain compatible when redaction is disabled.
- [ ] Enabled mode does not expose raw covered identifiers in outbound data.
    - Verify: tests inspect status snapshot, contract/diagnostics, logs, and every available API/dashboard/export/metrics surface for absence of raw `session_id`, `model`, and `provider` values.
- [ ] Pseudonyms are deterministic and non-raw.
    - Verify: repeated redaction of the same value with the same configuration returns the same pseudonym; different inputs differ; raw substrings are absent.
- [ ] Documentation explains privacy modes and field treatment.
    - Verify: README or observability contract docs list covered fields, modes, and whether values are raw/redacted/pseudonymized/omitted.
- [ ] No regressions in TPS tracking or observability contracts.
    - Verify: relevant hook/API/contract tests pass in the implementation phase.
