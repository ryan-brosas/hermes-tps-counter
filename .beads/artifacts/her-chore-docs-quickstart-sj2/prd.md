---
purpose: Product Requirements Document for a bead
updated: 2026-06-17
---

# PRD: Add README quickstart and troubleshooting guide for TPS plugin installation, status-bar integration, and observability surfaces

**Bead:** her-chore-docs-quickstart-sj2 | **Type:** chore | **Priority:** P3
**Created:** 2026-06-16 | **Estimate:** 45 minutes

## Problem

WHEN Hermes users install or evaluate the `tps-counter` plugin THEN they must piece together the install path, status-bar patch points, privacy/freshness caveats, and available observability surfaces from dense README sections BECAUSE the repository lacks a concise quickstart and troubleshooting guide that reflects the current plugin contract.

**Who is affected?** Hermes Agent users installing the plugin, maintainers validating status-bar integration, operators checking TPS visibility, and consumers integrating against `agent._tps_snapshot`, `get_tps_stats(session_id)`, or `get_observability_contract()`.
**Why now?** The graph identifies this bead as the open docs quick win on track A. The implementation already includes core TPS tracking, status snapshot injection, freshness metadata, privacy redaction, and a machine-readable observability contract; documentation should now make those surfaces easier to install, verify, and troubleshoot without adding code.

## Scope

### In Scope
- Revise README documentation to include a short installation quickstart for copying/enabling the plugin and restarting Hermes.
- Clarify the required Hermes status-bar integration patches and how `agent._tps_snapshot` should be consumed.
- Document freshness and session-mismatch handling for `updated_monotonic`, `updated_at`, and `session_id`.
- Summarize public observability surfaces currently present in this branch: `_tps_snapshot`, `get_tps_stats(session_id)`, `get_observability_contract()`, privacy diagnostics, and unavailable REST/WebSocket/Prometheus surfaces marked by the contract.
- Add a troubleshooting section covering no TPS display, stale TPS display, cross-session mismatch, zero stats, privacy redaction confusion, and absent optional API/Prometheus/WebSocket endpoints.
- Keep docs aligned with `__init__.py`, `plugin.yaml`, and existing tests.

### Out of Scope
- Implementing plugin code, status-bar code, REST routes, WebSocket streams, Prometheus exporters, dashboards, alerts, or new tests.
- Changing the plugin contract, public API behavior, privacy policy, metric names, hook names, or status-bar rendering logic.
- Running package managers, build commands, or closing/committing/PR workflow steps.
- Replacing all README prose with a separate documentation site.

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Provide a concise README quickstart | MUST | README has a clear copy/install/restart/verify flow for installing the plugin into a Hermes plugins directory without implying new tooling. |
| 2 | Document status-bar integration accurately | MUST | README identifies `agent._tps_snapshot`, the active CLI instance hook expectation, snapshot fields, and recommended status-bar display behavior. |
| 3 | Explain stale and cross-session suppression rules | MUST | README instructs consumers to calculate age with `time.monotonic() - snapshot["updated_monotonic"]` and to suppress/clear values when stale or session-mismatched. |
| 4 | Summarize observability surfaces and availability | MUST | README describes `get_tps_stats(session_id)`, `get_observability_contract()`, privacy diagnostics/redaction behavior, and explicitly says REST/WebSocket/Prometheus surfaces are unavailable when the contract marks them unavailable. |
| 5 | Add practical troubleshooting guidance | MUST | README includes symptoms, likely causes, and checks for no TPS, stale TPS, privacy-redacted identifiers, zero stats, missing optional surfaces, and plugin registration failures. |
| 6 | Preserve documentation/code consistency | SHOULD | README examples use field names and env vars present in `__init__.py` and plugin metadata from `plugin.yaml`; no docs claim unsupported routes or exporters exist. |
| 7 | Keep the change documentation-only | SHOULD | Final diff changes only documentation files for this bead's implementation phase unless later planning explicitly authorizes otherwise. |

## Technical Context

Relevant current files and behavior:
- `README.md` already contains an install snippet, status-bar patch examples, stale/session-mismatch guidance, API helper usage, observability contract notes, and privacy redaction notes. The implementation phase should organize and expand this into a clearer quickstart/troubleshooting path rather than inventing new behavior.
- `plugin.yaml` declares `name: tps-counter`, version `1.0.0`, and the `post_api_request` hook.
- `__init__.py` registers `_on_post_api_request`, records per-session TPS, injects `agent._tps_snapshot`, exposes `get_tps_stats(session_id)`, `get_observability_contract()`, and `get_privacy_diagnostics()`, and supports privacy env vars `HERMES_TPS_PRIVACY_MODE`, `HERMES_TPS_PRIVACY_SALT`, `HERMES_TPS_PRIVACY_SCOPE`, `HERMES_TPS_PRIVACY_FIELDS`, and `HERMES_TPS_PRIVACY_TREATMENTS`.
- Current `get_observability_contract()` marks status snapshot and in-process API helper surfaces available, while REST observability route, WebSocket, and Prometheus surfaces are unavailable on this branch.
- Existing tests in `tests/test_api.py` and `tests/test_privacy.py` assert contract shape, snapshot fields, absent optional surfaces, and secret-safe privacy behavior; docs should not contradict those expectations.
- Graph context: `bv --robot-plan` places this bead alone in track A; it is a low-risk leaf chore and does not unblock downstream beads.

## Approach

Update the README as a documentation-only improvement centered around user flow: install, verify, integrate status bar, inspect observability surfaces, configure privacy if needed, and troubleshoot symptoms. Prefer short, copyable examples and tables of symptoms/checks. Treat current code as the source of truth: document available in-process helpers and contract-reported unavailability for REST/WebSocket/Prometheus rather than promising endpoints that do not exist on this branch.

**Alternatives considered:**
- Add new REST/Prometheus/WebSocket docs assuming future surfaces: rejected because the current branch marks those surfaces unavailable and this bead is docs-only.
- Create a separate docs site or multiple files: rejected as too broad for a 45-minute README quickstart chore.
- Rewrite implementation or tests to match desired docs: rejected by bead scope and user constraints; code behavior already exists and must not be changed here.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Docs over-promise unavailable observability endpoints | Med | High | Use `get_observability_contract()` semantics and explicitly call REST/WebSocket/Prometheus unavailable on this branch. |
| Quickstart omits required Hermes status-bar patch context | Med | Med | Keep status-bar integration section tied to `agent._tps_snapshot` and active CLI instance expectations. |
| Troubleshooting becomes too verbose for README | Med | Low | Use concise symptom/cause/check tables and link back to existing sections. |
| Privacy guidance exposes or encourages unsafe secrets | Low | High | Mention env var names and behavior only; never show real salts, and note contract/diagnostics do not expose secret material. |
| Documentation drifts from code | Med | Med | Cross-check README examples against `__init__.py`, `plugin.yaml`, and existing tests during implementation review. |

## Tasks (for epics)

Not an epic.

## Success Criteria

- [ ] README contains a quickstart that lets a Hermes user install, restart, and verify the plugin's basic TPS behavior.
    - Verify: inspect README sections for install/restart/verification steps and ensure they match `plugin.yaml` and current repository layout.
- [ ] README documents status-bar integration with freshness and session-mismatch rules.
    - Verify: compare documented fields against `_tps_snapshot` construction in `__init__.py`.
- [ ] README summarizes current observability surfaces without claiming absent endpoints exist.
    - Verify: compare documentation against `get_observability_contract()` availability flags.
- [ ] README includes a troubleshooting guide for common installation, display, stale data, privacy, and observability-surface issues.
    - Verify: inspect troubleshooting table for symptom, cause, and check/remediation entries.
- [ ] The eventual implementation remains documentation-only.
    - Verify: `git diff -- README.md` or equivalent shows no plugin behavior changes.
