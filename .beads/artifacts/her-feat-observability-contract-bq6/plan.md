---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-feat-observability-contract-bq6

**Goal:** Add an additive, machine-readable observability contract for current TPS snapshot/API surfaces, with explicit metadata for REST/WebSocket/Prometheus surfaces that are present or absent on the implementation branch.

## Graph Context

- **Blast radius:** `bv --robot-impact her-feat-observability-contract-bq6` reports low risk and no existing bead/file links. `br show` allows `api.py`, `__init__.py`, `prometheus_metrics.py`, `plugin.yaml`, `README.md`, and `tests/` for implementation, but current repo inspection shows only `__init__.py`, `plugin.yaml`, `README.md`, and tests are present.
- **Unblocks:** None downstream (`blocks_count=0`, impact network has one isolated node).
- **Blocked by:** None (`bv --robot-blocker-chain` says actionable, chain length 0; `br dep tree` has only this bead).
- **Critical path:** Low graph coupling. `bv --robot-capacity` lists this bead on a length-1 critical path only because there are two independent actionable items and no dependency edges.
- **Forecast:** `bv --robot-forecast` estimates 85 minutes, confidence 0.45, from the 60 minute feature estimate with label velocity factors.

## Observable Truths

What must be TRUE for the goal to be achieved:

1. A JSON-compatible helper, preferably `get_observability_contract()`, returns a dict with stable top-level sections for contract metadata, compatibility guidance, status snapshot schema, API/helper payload metadata, WebSocket metadata, and Prometheus metric metadata.
2. The status snapshot section describes the current `_tps_snapshot` fields from `__init__.py`: `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `updated_at`, `updated_monotonic`, and `session_id`, including scalar types, units, and stale/session mismatch semantics.
3. The API/helper section describes current in-process `get_tps_stats(session_id)` output fields exactly as implemented: `calls`, `avg_tps`, `last_tps`, `peak_tps`, `total_output_tokens`, and `total_duration` when a session exists; it must not change `get_tps_stats` behavior.
4. REST, WebSocket, and Prometheus sections are present in the contract. If `api.py`, WebSocket support, or `prometheus_metrics.py` are absent on the branch, those sections explicitly say `available: false` or equivalent and do not claim nonexistent endpoints or metrics.
5. If an API route layer is present on the implementation branch, `/api/v1/observability/contract` or the repository's nearest existing route convention serves the helper output read-only. If no route layer exists, the helper is the stable contract surface and README documents that limitation.
6. Tests assert contract shape and representative fields/metrics/availability metadata without importing optional Prometheus/FastAPI dependencies.
7. Existing plugin behavior remains additive-only: `register()` still registers only `post_api_request`; `_on_post_api_request` still records TPS and injects the same snapshot keys; `get_tps_stats` output remains backward compatible.
8. README documents where to read the contract, the contract version, compatibility rules, and consumer guidance to ignore unknown fields.

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| PRD | Product requirements and acceptance criteria | `.beads/artifacts/her-feat-observability-contract-bq6/prd.md` | Done |
| Plan | Wave sequencing and implementation constraints | `.beads/artifacts/her-feat-observability-contract-bq6/plan.md` | This file |
| Tasks | Detailed task decomposition with dependency tracking | `.beads/artifacts/her-feat-observability-contract-bq6/tasks.md` | This phase |
| Context capsule | Spawn context for `/ship` implementation agents | `.beads/artifacts/her-feat-observability-contract-bq6/context-capsule.md` | This phase |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | 1.1 Inspect current observability surfaces; 1.2 lock contract skeleton and versioning | Yes | PRD reviewed; branch file inventory checked | Notes identify present/absent `api.py`, WebSocket, Prometheus surfaces before code changes |
| 2 | 2.1 Add static contract helper; 2.2 add optional API-route adapter only if route layer exists | Conditional | Wave 1 complete | Helper output is JSON-serializable and does not inspect sessions or optional modules |
| 3 | 3.1 Add focused contract tests; 3.2 preserve existing public API tests | Yes after Wave 2 | Helper and optional route exist | `pytest tests/test_api.py tests/test_hook.py tests/test_session_tps.py tests/test_thread_safety.py` |
| 4 | 4.1 Update README consumer guidance; 4.2 final compatibility review | Yes after Wave 2 | Contract shape stable | README includes helper/route location, versioning, unknown-field guidance, and branch-availability caveats |
| 5 | 5.1 Run full bead verification and bead hygiene checks | No | Waves 1-4 complete | `br lint her-feat-observability-contract-bq6 --json`; `bv --robot-suggest`; `br dep cycles --blocking-only --json`; `br sync --flush-only` |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Acceptance Criteria

- [ ] `get_observability_contract()` or the selected branch-equivalent helper returns JSON-compatible contract metadata with contract version and plugin version.
- [ ] Contract top-level sections include `contract`, `compatibility`, `status_snapshot`, `api`, `websocket`, and `prometheus`.
- [ ] Snapshot metadata documents `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `updated_at`, `updated_monotonic`, and `session_id` with types, units, freshness semantics, and session mismatch guidance.
- [ ] API/helper metadata documents current `get_tps_stats(session_id)` fields and absent-session zero behavior without changing the function's return contract.
- [ ] REST/WebSocket/Prometheus sections truthfully represent actual branch surfaces, marking absent optional surfaces unavailable instead of over-promising closed-bead features.
- [ ] README documents helper/route location, contract versioning, unknown-field tolerance, and Prometheus cardinality guidance.
- [ ] Existing hook, stats, snapshot, and thread-safety tests pass alongside focused contract tests.

## Delegation Packets for /ship

Do not delegate during this `/plan` phase. For `/ship`, if the operator chooses to spawn focused workers, use these packets and verify their output directly:

1. **Contract helper packet** — Implement `get_observability_contract()` in `__init__.py` with static JSON-compatible metadata. Keep it dependency-free, read-only, and close to the existing TPS field producers. Include branch-availability flags for REST/WebSocket/Prometheus when files/modules are absent.
2. **Optional route packet** — Only if an API routing module exists on the implementation branch, add a GET route for `/api/v1/observability/contract` that returns the helper output. Do not introduce FastAPI or Prometheus dependencies solely for this bead.
3. **Tests packet** — Add tests that import the helper from `__init__.py`, assert required top-level sections, representative snapshot fields, `get_tps_stats` metadata, branch-availability flags, JSON serializability, and no mutation of session state. Keep existing hook/API tests passing.
4. **Docs packet** — Update README with a concise observability contract section. Document contract versioning, helper/route location, stale/session mismatch guidance, label cardinality notes, and the rule that consumers must ignore unknown fields.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter
pytest tests/test_api.py tests/test_hook.py tests/test_session_tps.py tests/test_thread_safety.py
python3 - <<'PY'
import json
from __init__ import get_observability_contract
contract = get_observability_contract()
json.dumps(contract, sort_keys=True)
for key in ["contract", "compatibility", "status_snapshot", "api", "websocket", "prometheus"]:
    assert key in contract, key
PY
br lint her-feat-observability-contract-bq6 --json
bv --robot-suggest
br dep cycles --blocking-only --json
br sync --flush-only
```
