---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-privacy-redaction-pis

**Goal:** Add one configurable, dependency-free privacy redaction policy for TPS observability identifiers so outbound snapshots, helper responses, contract metadata, logs, docs, and any present optional observability surfaces can suppress raw `session_id`, `model`, `provider`, and future identifier-like fields while disabled mode remains backward compatible.

## Graph Context

- **Blast radius:** `bv --robot-impact her-privacy-redaction-pis` reports low risk, risk score 0, no affected beads, and no linked implementation files yet. `br show` allows `__init__.py`, `config.py`, `api.py`, `dashboard.py`, `prometheus_metrics.py`, `store.py`, `README.md`, and `tests/`; current repo inspection shows active core files are `__init__.py`, `README.md`, `tests/test_hook.py`, and `tests/test_api.py`, with optional route/dashboard/export/metrics modules absent unless `/ship` re-checks and finds them.
- **Unblocks:** None recorded (`blocks_count=0`; impact network contains only this bead as an isolated node).
- **Blocked by:** None (`bv --robot-blocker-chain her-privacy-redaction-pis` says actionable, chain length 0; `br dep tree` has only this bead).
- **Critical path:** Graph coupling is low. `bv --robot-capacity` lists this bead on a length-1 critical path because there are two independent actionable items and no dependency edges, not because it blocks a chain.
- **Forecast:** `bv --robot-forecast her-privacy-redaction-pis` estimates 85 minutes, confidence 0.35, from median 60m feature estimate, feature multiplier, depth multiplier, config-label velocity, and one agent.
- **Parallel tracks:** `bv --robot-plan` shows two independent tracks: Track A `her-feat-batch-session-stats-ojy` and Track B `her-privacy-redaction-pis`. Work inside this bead should still serialize changes to `__init__.py`, but docs/tests can proceed once the policy shape is stable.
- **Hotspots:** `bv --robot-file-hotspots` reports no hotspots and no files with multiple bead links. Treat `__init__.py` as the practical hot file anyway because it owns hook behavior, state, contract metadata, public helpers, and logging.
- **Next-work signal:** `bv --robot-next` selects `her-privacy-redaction-pis` as the top pick because of graph centrality and unclaimed status.

## Observable Truths

What must be TRUE for the goal to be achieved:

1. A single shared privacy policy/helper exists, either in `__init__.py` or a lightweight local `config.py`/privacy module, and all outbound identifier treatment goes through it rather than ad hoc per-surface string manipulation.
2. Disabled/default-compatible mode preserves current public behavior: `_tps_snapshot["session_id"]` remains raw, `get_tps_stats(session_id)` lookup behavior and response fields stay unchanged, `register()` still registers only the post-API hook, and current contract/tests remain compatible with additive metadata.
3. Enabled mode prevents raw covered identifiers from leaving trusted in-process state through every available outbound surface on the implementation branch: status snapshot, in-process helper/API response data, observability contract diagnostics/metadata, debug logs, README examples, and any present `api.py`, WebSocket, dashboard, Prometheus, or export modules.
4. Deterministic pseudonyms are stable for the same raw value plus configured scope/salt, differ for distinct raw values, and do not contain raw source substrings. HMAC or keyed standard-library hashing is used; no external packages, network calls, background workers, or unbounded scans are introduced.
5. Secret/salt material is accepted only as configuration input and is never emitted in logs, snapshots, API/helper payloads, contract output, exports, tests snapshots, or README examples.
6. The observability contract exposes privacy mode and per-field treatment metadata such as `raw`, `pseudonymized`, `redacted`, or `omitted` without exposing raw identifiers or secrets, and it does not claim unavailable REST/WebSocket/Prometheus/dashboard/export surfaces exist.
7. Tests prove disabled-mode compatibility, deterministic pseudonym behavior, enabled-mode absence of raw `session_id`/`model`/`provider` on outbound surfaces available in this branch, no secret leakage, and unchanged TPS counters.
8. README or contract docs explain modes, defaults, field treatment, deterministic grouping guarantees, migration guidance for consumers that compare `session_id`, and cardinality guidance for future metrics labels.

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| PRD | Product requirements, acceptance criteria, technical context, and risks | `.beads/artifacts/her-privacy-redaction-pis/prd.md` | Done |
| Plan | Graph-informed wave sequencing and implementation constraints | `.beads/artifacts/her-privacy-redaction-pis/plan.md` | This file |
| Tasks | Detailed task decomposition with dependencies, parallelism, and file ownership | `.beads/artifacts/her-privacy-redaction-pis/tasks.md` | This phase |
| Context capsule | Spawn context for `/ship` implementation with patterns, constraints, and file boundaries | `.beads/artifacts/her-privacy-redaction-pis/context-capsule.md` | This phase |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | 1.1 Re-check current surfaces and branch files; 1.2 define privacy configuration contract and field-treatment matrix | Yes | PRD reviewed; no implementation edits started | Written notes/task checklist identifies present/absent surfaces and default disabled semantics before code changes |
| 2 | 2.1 Implement shared redaction policy/helper; 2.2 thread policy through current status snapshot and debug logging | Mostly no | Wave 1 complete | Local smoke check can instantiate policy, preserve raw output when disabled, and produce deterministic non-raw pseudonyms when enabled |
| 3 | 3.1 Apply policy to public helpers/contract metadata; 3.2 apply policy to optional surfaces only if present on branch | Conditional parallel after 2.1 | Core helper exists | Contract remains JSON-serializable, static/cheap, and truthfully marks absent optional surfaces unavailable |
| 4 | 4.1 Add disabled/enabled policy tests; 4.2 add outbound surface/log/contract no-leak tests; 4.3 update README/docs | Yes after Wave 3 API shape stabilizes | Redaction behavior implemented | Focused pytest selection covers `tests/test_api.py` and `tests/test_hook.py`; README documents modes without secrets |
| 5 | 5.1 Run final compatibility and privacy verification; 5.2 run bead hygiene checks | No | Waves 1-4 complete | Focused tests, no raw-leak smoke checks, `br lint`, `bv --robot-suggest`, `br dep cycles`, and `br sync --flush-only` pass or produce actionable known issues |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Acceptance Criteria

- [ ] One shared redaction policy/helper governs identifier fields including `session_id`, `model`, `provider`, and configured future identifier-like fields.
- [ ] Disabled/default-compatible mode preserves existing `_tps_snapshot`, `get_tps_stats`, `register`, and observability contract behavior except for additive metadata.
- [ ] Enabled mode does not emit raw covered identifiers on available outbound surfaces: status snapshot, public helper/API payloads, observability contract diagnostics/metadata, debug logs, README examples, and any present optional route/dashboard/prometheus/export modules.
- [ ] Deterministic pseudonyms are stable under the same configuration and do not contain raw values; different raw values remain distinguishable enough for grouping.
- [ ] Salt/secret configuration is never emitted in diagnostics, logs, contract output, snapshots, API/helper payloads, exports, or README examples.
- [ ] Hook-path overhead remains bounded and dependency-free: standard library only, no network, no background workers, no scanning all sessions for one hook call.
- [ ] Contract/docs state active privacy mode and per-field treatment (`raw`, `pseudonymized`, `redacted`, `omitted`) without over-promising unavailable surfaces.
- [ ] Focused tests prove disabled compatibility, enabled no-leak behavior, deterministic pseudonyms, and unchanged TPS counters.

## Delegation Packets for /ship

Do not delegate during this `/plan` phase. The user also requested no delegation for this repair. If a future `/ship` operator chooses to split work manually, these are the implementation packets to keep file ownership clear and must be verified directly by the main agent:

1. **Policy/helper packet** — Add a small dependency-free privacy policy and redaction helper in `__init__.py` or a local `config.py`/privacy helper. It must define disabled/raw-compatible behavior, enabled pseudonym/redact/omit behavior, covered fields, deterministic HMAC/keyed-hash pseudonyms, and secret-safe diagnostics. Do not change internal `_SESSIONS` keys or raw lookup inputs.
2. **Current surfaces packet** — Use the shared helper immediately before outbound exposure in `_on_post_api_request` status snapshot injection and debug logging. Preserve raw internal `session_id` for `_get_session(session_id)` and disabled-mode snapshot compatibility. Keep `get_tps_stats(session_id)` lookup semantics; redact only any identifiers the function returns now or in future.
3. **Contract/optional surfaces packet** — Update `get_observability_contract()` with privacy metadata and per-field treatment. If `api.py`, `dashboard.py`, `prometheus_metrics.py`, WebSocket support, or export/store modules exist on the implementation branch, apply the same helper to their outbound payloads/labels/exports; if absent, leave contract availability false and document policy for future surfaces only.
4. **Tests packet** — Add focused tests for policy behavior, deterministic pseudonyms, disabled-mode compatibility, enabled-mode absence of raw identifiers in snapshot/contract/log surfaces, no secret leakage, and unchanged TPS counters. Prefer `tests/test_api.py` and `tests/test_hook.py`; add a dedicated privacy test file only if that keeps fixtures clearer.
5. **Docs packet** — Update README privacy/redaction guidance near status snapshot/API/observability contract docs. Explain default disabled compatibility, enabled mode behavior, field treatment, deterministic grouping scope, migration for `session_id` comparisons, and no-secret examples.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
pytest tests/test_api.py tests/test_hook.py
python3 - <<'PY'
import json
from __init__ import get_observability_contract
contract = get_observability_contract()
json.dumps(contract, sort_keys=True)
assert "privacy" in contract or "privacy" in json.dumps(contract).lower()
PY
python3 - <<'PY'
# Adapt names to the final helper chosen in /ship. This smoke check should verify:
# 1. disabled mode returns raw identifiers;
# 2. enabled mode returns deterministic non-raw pseudonyms;
# 3. secret/salt material is absent from diagnostic/contract payloads.
PY
br lint her-privacy-redaction-pis --json
bv --robot-suggest
br dep cycles --blocking-only --json
br sync --flush-only
```
