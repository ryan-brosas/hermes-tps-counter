---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-chore-docs-quickstart-sj2

**Goal:** Reorganize and expand `README.md` into a concise documentation-only quickstart and troubleshooting guide for installing `tps-counter`, integrating status-bar TPS, and understanding current observability/privacy surfaces.

## Graph Context

- **Blast radius:** `README.md` is the intended implementation file. `bv --robot-impact her-chore-docs-quickstart-sj2` returned `risk_level: low`, `risk_score: 0`, no affected beads, and no file-linked conflicts. The graph command reported `files: ["her-chore-docs-quickstart-sj2"]`, so the bead currently has no explicit file links; treat the PRD's README-only scope as authoritative.
- **Unblocks:** None. `bv --robot-plan` lists this bead in `track-A` with `unblocks: null`; `bv --robot-impact-network` shows a single isolated node with zero edges.
- **Blocked by:** None. `bv --robot-blocker-chain her-chore-docs-quickstart-sj2` returned `is_blocked: false`, `chain_length: 0`, `actionable: true`.
- **Critical path:** Low-risk leaf work. `bv --robot-capacity` lists this bead on the current critical path only because there is one item in that lane; dependency graph has no blockers and no downstream edges.
- **Forecast:** `bv --robot-forecast her-chore-docs-quickstart-sj2` estimates 52 minutes with confidence 0.45. PRD estimate is 45 minutes, so this is realistic for one focused documentation session.
- **Execution tracks:** `bv --robot-plan` exposes two parallel-safe tracks: `track-A` = this docs bead; `track-B` = `her-feat-batch-session-stats-ojy`. For this bead, work is serial because all implementation edits converge on `README.md`.
- **Capacity:** `bv --robot-capacity` reports 2 actionable open issues, 137 total minutes, 52 serial minutes, 85 parallel minutes, 62.0% parallelizable across the repo. This session should only plan this bead.
- **Next:** `bv --robot-next` confirms `her-chore-docs-quickstart-sj2` is the single top pick and currently unclaimed/open.
- **Hot files:** `bv --robot-file-hotspots` returned no hotspots; no risky shared files are flagged.

## Observable Truths

What must be TRUE for the goal to be achieved:

1. `README.md` contains a short install/restart/verify quickstart that names the plugin directory copy flow and does not imply unsupported tooling.
2. `README.md` documents status-bar integration through `agent._tps_snapshot`, the active CLI instance expectation, snapshot fields, and display behavior for positive/zero TPS values.
3. `README.md` instructs consumers to calculate snapshot age with `time.monotonic() - snapshot["updated_monotonic"]` and suppress/clear stale or session-mismatched displays.
4. `README.md` accurately describes current observability surfaces: `agent._tps_snapshot`, `get_tps_stats(session_id)`, `get_observability_contract()`, and `get_privacy_diagnostics()`/privacy diagnostics; REST/WebSocket/Prometheus are explicitly unavailable when the contract marks them unavailable.
5. `README.md` includes a practical troubleshooting table covering no TPS display, stale TPS, cross-session mismatch, zero stats, privacy redaction confusion, absent optional surfaces, and plugin registration failures.
6. The implementation diff is documentation-only and should only change `README.md` unless a later plan update explicitly authorizes another documentation file.
7. Verification compares README examples against `__init__.py`, `plugin.yaml`, `tests/test_api.py`, and `tests/test_privacy.py`; no package managers, builds, code changes, commits, PRs, or bead closure occur.

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| PRD | Requirements, scope, constraints, success criteria | `.beads/artifacts/her-chore-docs-quickstart-sj2/prd.md` | Done |
| Plan | Wave sequence, graph context, verification gates | `.beads/artifacts/her-chore-docs-quickstart-sj2/plan.md` | Done |
| Tasks | Detailed task decomposition and dependencies | `.beads/artifacts/her-chore-docs-quickstart-sj2/tasks.md` | Done |
| Context capsule | Spawn/ship context, patterns, constraints, file ownership | `.beads/artifacts/her-chore-docs-quickstart-sj2/context-capsule.md` | Done |
| Implementation target | User-facing quickstart/troubleshooting docs | `README.md` | Need in /ship |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | 1.1 Confirm source-of-truth contract and README structure | No | PRD and graph context available | Manual read of `README.md`, `plugin.yaml`, `__init__.py`, `tests/test_api.py`, `tests/test_privacy.py` |
| 2 | 2.1 Rewrite/organize quickstart and install verification; 2.2 Rewrite/organize status-bar/freshness guidance; 2.3 Rewrite/organize observability/privacy guidance; 2.4 Add troubleshooting guide | No for actual editing, because all tasks touch `README.md`; conceptually separable sections | Wave 1 complete | `git diff -- README.md` inspection confirms all required sections exist and no unsupported surfaces are promised |
| 3 | 3.1 Documentation consistency review; 3.2 Documentation-only blast-radius check | No | Wave 2 complete | Compare README field/env/hook names to code/tests; `git diff --name-only` shows only approved docs file(s) for implementation |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Delegation Packets for /ship

No sub-agent delegation is authorized by this bead request; `/ship` should execute the packets directly in the main session.

### Packet A — README quickstart and installation flow

- **Objective:** Add/reshape a concise top-level quickstart covering copy/install, restart, and basic verification of TPS behavior.
- **Allowed files:** `README.md` only.
- **Source of truth:** `plugin.yaml` (`name: tps-counter`, version `1.0.0`, hook `post_api_request`), existing README install snippet, PRD requirements 1 and 6.
- **Must include:** copy to a Hermes plugins directory, restart Hermes, trigger/use an LLM call to produce TPS, and check that the plugin registered/produced status/API stats.
- **Must avoid:** new tooling, package managers, generated install scripts, code changes, commits.

### Packet B — Status-bar, freshness, and session-mismatch guide

- **Objective:** Make the status-bar section easy to follow and explicitly safe against stale or cross-session display.
- **Allowed files:** `README.md` only.
- **Source of truth:** `__init__.py` lines around `_on_post_api_request` and `get_observability_contract()` status snapshot metadata.
- **Must include:** active CLI instance expectation, `agent._tps_snapshot`, fields `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `updated_at`, `updated_monotonic`, `session_id`, optional `model`/`provider`, and `time.monotonic() - snapshot["updated_monotonic"]` age checks.
- **Must avoid:** claiming Hermes core already renders TPS without the documented status-bar patch points.

### Packet C — Observability and privacy guide

- **Objective:** Summarize available and unavailable observability surfaces accurately.
- **Allowed files:** `README.md` only.
- **Source of truth:** `get_tps_stats(session_id)`, `get_observability_contract()`, `get_privacy_diagnostics()`, `tests/test_api.py`, `tests/test_privacy.py`.
- **Must include:** in-process helpers available; REST route, WebSocket stream, and Prometheus exporter unavailable on this branch when the contract marks them unavailable; privacy env vars `HERMES_TPS_PRIVACY_MODE`, `HERMES_TPS_PRIVACY_SALT`, `HERMES_TPS_PRIVACY_SCOPE`, `HERMES_TPS_PRIVACY_FIELDS`, `HERMES_TPS_PRIVACY_TREATMENTS`; no secret material emitted.
- **Must avoid:** documenting unsupported endpoints/exporters as usable.

### Packet D — Troubleshooting and final docs review

- **Objective:** Add a symptom/cause/check table and verify the change remains documentation-only and code-consistent.
- **Allowed files:** `README.md` only.
- **Must cover:** no TPS display, stale TPS display, cross-session mismatch, zero stats, privacy-redacted identifiers, missing optional REST/WebSocket/Prometheus surfaces, and plugin registration failures.
- **Verification:** inspect README sections; compare names/fields/env vars to `__init__.py`, `plugin.yaml`, and tests; run no package manager/build commands.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
# Inspect only; this is a documentation-only bead.
git diff -- README.md
git diff --name-only
# Cross-check README examples manually against:
# - plugin.yaml
# - __init__.py
# - tests/test_api.py
# - tests/test_privacy.py
# Bead hygiene only when phase is complete:
br lint her-chore-docs-quickstart-sj2 --json
bv --robot-suggest
br dep cycles --blocking-only --json
br sync --flush-only
```
