---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-chore-docs-quickstart-sj2

## Objective

Update `README.md` only to provide a concise quickstart and troubleshooting guide for installing `tps-counter`, integrating `agent._tps_snapshot` into the Hermes status bar, and using/understanding current observability and privacy surfaces.

## Key Patterns

- `Documentation-only bead` — The PRD explicitly forbids code changes, new tests, package manager/build commands, commits, PRs, and bead closure. Implementation should edit `README.md` only. Reference: `.beads/artifacts/her-chore-docs-quickstart-sj2/prd.md`.
- `Plugin metadata` — Document plugin identity and hook exactly as `plugin.yaml`: `name: tps-counter`, version `1.0.0`, hook `post_api_request`. Reference: `plugin.yaml`.
- `Status snapshot producer` — `_on_post_api_request` records successful calls only when `session_id` exists and `output_tokens > 0` and `api_duration > 0`, then injects `_redact_payload(snapshot, privacy_policy)` into the active CLI agent as `agent._tps_snapshot`. Reference: `__init__.py`.
- `Snapshot field contract` — Required current snapshot fields are `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `updated_at`, `updated_monotonic`, and `session_id`; optional `model` and `provider` are present when provided to the hook. Reference: `__init__.py` and `tests/test_api.py`.
- `Freshness and session safety` — Consumers must calculate age with `time.monotonic() - snapshot["updated_monotonic"]` and suppress/clear stale values or session mismatches. Use the same privacy treatment when comparing active session ID against a privacy-treated snapshot. Reference: `get_observability_contract()` in `__init__.py`.
- `In-process observability only on this branch` — `get_tps_stats(session_id)` and `get_observability_contract()` are available. REST observability route, WebSocket stream, and Prometheus exporter are unavailable and marked `available: false`. Reference: `__init__.py`, `tests/test_api.py`, and `tests/test_privacy.py`.
- `Privacy diagnostics are secret-safe` — Privacy env vars are `HERMES_TPS_PRIVACY_MODE`, `HERMES_TPS_PRIVACY_SALT`, `HERMES_TPS_PRIVACY_SCOPE`, `HERMES_TPS_PRIVACY_FIELDS`, and `HERMES_TPS_PRIVACY_TREATMENTS`. Contract/diagnostics must not expose salts or raw secrets. Reference: `__init__.py` and `tests/test_privacy.py`.
- `Troubleshooting table style` — Prefer concise symptom/cause/check/remediation rows over long prose, and link symptoms back to quickstart/status/observability sections. Reference: PRD success criteria.

## Constraints

1. Write only within `.beads/artifacts/her-chore-docs-quickstart-sj2/` during `/plan`; during `/ship`, implementation edits are limited to `README.md` unless the plan is explicitly revised.
2. Do not create a new bead; use `her-chore-docs-quickstart-sj2` only.
3. Do not implement or modify plugin code, Hermes status-bar code, REST routes, WebSocket streams, Prometheus exporters, dashboards, alerts, tests, public API behavior, privacy behavior, metric names, hook names, or rendering logic.
4. Do not run `npm`, `pip`, `cargo`, package-manager installs, builds, or close/commit/PR workflow steps.
5. Do not claim unsupported endpoints or exporters exist. If mentioning REST/WebSocket/Prometheus, say they are unavailable on this branch when the contract marks them unavailable.
6. Use current code as source of truth. README examples must use field names, helper names, hook names, plugin metadata, and privacy env vars that exist in current files.
7. Verification for implementation is inspection-based: README diff, source-name cross-checks, and bead hygiene commands.
8. No sub-agent delegation is authorized by the user request; all work should be done in the main session.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Plan artifacts | `.beads/artifacts/her-chore-docs-quickstart-sj2/plan.md`, `.beads/artifacts/her-chore-docs-quickstart-sj2/tasks.md`, `.beads/artifacts/her-chore-docs-quickstart-sj2/context-capsule.md` — create/update plan phase artifacts | Any repository source file during `/plan` |
| Source-of-truth review | `README.md`, `plugin.yaml`, `__init__.py`, `tests/test_api.py`, `tests/test_privacy.py` — read only | Editing code/tests/config during this bead |
| README quickstart | `README.md` — edit documentation in `/ship` | `__init__.py`, `plugin.yaml`, tests, package files, lockfiles, Hermes core files |
| Status-bar docs | `README.md` — edit documentation/examples in `/ship` | Implementing status-bar patches in Hermes or changing plugin hook behavior |
| Observability/privacy docs | `README.md` — edit documentation in `/ship` | Adding REST/WebSocket/Prometheus modules, changing privacy policy, changing contract shape |
| Troubleshooting docs | `README.md` — edit documentation table in `/ship` | Adding tests or scripts unless a later plan revision authorizes them |
| Verification | Read/diff files and run `br`/`bv` hygiene commands | Package managers, builds, commits, PRs, bead closure |

## Graph Context

- **Tracks:** `bv --robot-plan` shows `track-A` containing only `her-chore-docs-quickstart-sj2` and `track-B` containing `her-feat-batch-session-stats-ojy`. This bead can proceed independently but should not take on track-B work.
- **Blast radius:** `bv --robot-impact her-chore-docs-quickstart-sj2` reports low risk, score 0, no affected beads, and no warnings. The intended implementation blast radius is `README.md` only.
- **Impact network:** Single isolated node, zero edges, no clusters; no downstream or upstream dependency coordination needed.
- **Blocker chain:** Not blocked; chain length 0; actionable root node.
- **Forecast:** 52 minutes, confidence 0.45; fits one focused docs session.
- **Capacity:** 2 actionable open issues, 137 total minutes across repo; this bead is one of the two actionable items. Do not expand scope.
- **Hot files:** None reported by `bv --robot-file-hotspots`.
- **Next pick:** `bv --robot-next` confirms this bead is the top pick and currently unclaimed/open.
- **Related beads:** No direct dependency-tree relatives. Conceptual context comes from already-present code/tests for observability contract, status freshness, and privacy redaction.
- **File history:** No file-bead hotspots are reported for this bead; still treat `README.md` as the only implementation file because PRD success criteria are README-specific.

## /ship Handoff

Start from these tasks:

1. Read `README.md`, `plugin.yaml`, `__init__.py`, `tests/test_api.py`, and `tests/test_privacy.py` for exact names and behaviors.
2. Edit `README.md` into a user-flow order: quickstart, status-bar integration/freshness, observability surfaces, privacy, troubleshooting.
3. Ensure troubleshooting covers: no TPS display, stale TPS, cross-session mismatch, zero stats, privacy redaction confusion, absent optional REST/WebSocket/Prometheus surfaces, and plugin registration failures.
4. Verify with inspection/diff only; do not run package managers/builds/tests unless the plan is revised.
5. Leave bead open; do not commit, close, or create a PR.
