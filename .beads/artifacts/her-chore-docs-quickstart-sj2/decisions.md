---
purpose: Decision log for a bead
updated: 2026-06-17
---

# Decisions: her-chore-docs-quickstart-sj2

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Treat this bead as a README documentation-only quickstart/troubleshooting chore. | The bead type is chore, title is docs-focused, and user constraints explicitly forbid code implementation. | High |
| 2 | Document only currently available surfaces: `agent._tps_snapshot`, `get_tps_stats(session_id)`, `get_observability_contract()`, and privacy diagnostics/configuration. | `__init__.py` and tests show these are the stable in-process surfaces on this branch. | High |
| 3 | State REST observability route, WebSocket events, and Prometheus metrics as unavailable unless the contract marks them available. | `get_observability_contract()` currently marks those optional surfaces unavailable, and docs must not over-promise. | High |
| 4 | Make freshness/session mismatch guidance a required part of status-bar documentation. | README and contract both identify `updated_monotonic` and `session_id` as the consumer controls for stale or cross-session TPS display. | High |
| 5 | Include privacy redaction troubleshooting and env var guidance without showing secret values. | The plugin supports outbound privacy transformations and diagnostics, but secret material must remain unexposed. | High |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Create a new bead for the docs work. | The user stated the bead already exists and must not be recreated. | Duplicate tracking, inconsistent br graph, and violation of repair task constraints. |
| 2 | Implement missing REST/WebSocket/Prometheus surfaces as part of docs repair. | The bead is documentation-focused and user constraints prohibit implementation. | Scope creep, unverified code changes, and misleading create-phase artifacts. |
| 3 | Run package managers, test suites, or builds to validate docs. | User explicitly forbade npm, pip, cargo, and build commands; this phase only repairs create artifacts. | Violates task constraints and may mutate environment unexpectedly. |
| 4 | Promise future endpoint paths as if they exist today. | Current contract marks the route unavailable and recommends the Python helper instead. | Consumers may integrate against nonexistent surfaces and report false regressions. |
| 5 | Split quickstart into a separate docs site or generated artifact. | The bead title specifically targets README quickstart/troubleshooting, and a separate site is unnecessary for this chore. | Extra maintenance surface and incomplete README improvement. |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | README is the primary file to modify in the later implementation phase. | Validated by repository structure and bead title. | If more docs files appear, the plan phase should include them while preserving docs-only scope. |
| 2 | The plugin remains a minimal in-process Hermes plugin on this branch. | Validated by `plugin.yaml`, `__init__.py`, and tests. | If optional API/exporter modules are added before implementation, docs must update availability statements from the contract. |
| 3 | Status-bar consumers can read `agent._tps_snapshot` after Hermes-side integration patches. | Validated by existing README guidance and `_on_post_api_request` injection behavior. | If Hermes core changes the integration point, quickstart examples must be revised to the new API. |
| 4 | Privacy redaction defaults to disabled/raw-compatible behavior. | Validated by `__init__.py` policy defaults and privacy tests. | If defaults change, install and troubleshooting guidance must emphasize changed comparison semantics. |
| 5 | Create-phase artifact repair should not add plan/tasks artifacts. | Validated by user final instruction that a later bead-fix pass handles `plan.md` and `tasks.md`. | Writing plan artifacts here would violate scope and could conflict with later repair passes. |
