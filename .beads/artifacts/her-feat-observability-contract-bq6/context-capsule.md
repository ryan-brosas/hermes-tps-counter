---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-feat-observability-contract-bq6

## Objective

Add a cheap, additive, machine-readable observability contract describing the hermes-tps-counter status snapshot, in-process API/helper payloads, and REST/WebSocket/Prometheus metadata for only the surfaces present on the implementation branch.

## Key Patterns

- `Status snapshot injection` — `_on_post_api_request` records per-session TPS and injects `agent._tps_snapshot` with `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `updated_at`, `updated_monotonic`, and `session_id`. Preserve these keys and document them rather than changing their behavior. Reference: `__init__.py:108-140`.
- `Public helper API` — `get_tps_stats(session_id)` is the current in-process consumer API and returns rounded TPS stats without requiring an API server. Contract metadata should describe this output exactly and must not alter it. Reference: `__init__.py:159-173`.
- `Plugin registration` — `register(ctx)` registers only the `post_api_request` hook. This bead must not add registration side effects or mutate plugin lifecycle behavior. Reference: `__init__.py:153-156`.
- `Plugin version source` — `plugin.yaml` declares `name: tps-counter` and `version: "1.0.0"`; the contract must not contradict these values. Reference: `plugin.yaml:1-2`.
- `Freshness documentation` — README already explains `updated_at`, `updated_monotonic`, `session_id`, stale thresholds, and session mismatch handling. New docs should link/extend this guidance, not replace it with conflicting advice. Reference: `README.md:62-98`.
- `Existing tests` — tests currently cover hook behavior, status snapshot freshness, public stats API, session accounting, and thread safety. Add contract tests alongside these without weakening existing assertions. References: `tests/test_api.py`, `tests/test_hook.py`, `tests/test_session_tps.py`, `tests/test_thread_safety.py`.

## Constraints

1. This bead is additive-only. Do not rename, remove, or change existing `_tps_snapshot` keys, `get_tps_stats` output keys, hook registration, or README status-bar integration semantics.
2. Contract generation must be static or cheap: no iteration over all sessions, no SQLite scans, no network calls, no background threads, no timers, and no mutation of `_SESSIONS` or agent state.
3. Do not import optional FastAPI/Prometheus/WebSocket dependencies from the contract helper. If optional modules are absent, represent those surfaces as unavailable in the returned contract.
4. Current repo inspection shows no `api.py`, WebSocket module, or `prometheus_metrics.py`; `/ship` must re-check the branch before deciding whether to add a route. Do not over-promise closed-bead features that are not present in code.
5. If a route layer is present, the endpoint should be read-only and return the same helper output. If absent, the stable surface for this bead is the Python helper and README must document helper-only availability.
6. Consumers must be told to tolerate unknown fields and validate by `contract_version`; future additive metadata must not break old consumers.
7. The `/plan` phase wrote only `.beads/artifacts/her-feat-observability-contract-bq6/`. `/ship` may touch only implementation files allowed by `br show` unless the bead is explicitly updated.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Contract helper | `__init__.py` — add `get_observability_contract()` and any small constants needed for metadata | Existing hook/stat behavior changes; new background processing; session scans |
| Optional route | `api.py` or existing route module — add read-only contract route only if already present | Creating a new web framework dependency; changing existing REST/WebSocket payload contracts |
| Prometheus metadata | `prometheus_metrics.py` only if present — read names/types/labels for metadata consistency | Adding new metrics, changing labels, changing metric cardinality behavior |
| Tests | `tests/test_api.py` primarily; other tests only for compatibility assertions if needed | Weakening or deleting existing tests for hook/API/session behavior |
| Documentation | `README.md` — add observability contract usage/versioning/consumer guidance | Removing existing status-bar freshness guidance or claiming absent endpoints exist |
| Bead artifacts | `.beads/artifacts/her-feat-observability-contract-bq6/` — plan/tasks/context only | New bead creation, bead closure, PR creation, git commits during plan phase |

## Graph Context

- **Blast radius:** `bv --robot-impact her-feat-observability-contract-bq6` reports low risk, no affected beads, and no linked files. `bv --robot-file-hotspots` reports no hotspots.
- **Related beads:** The impact network contains only this bead; `br dep tree` has no dependencies. `bv --robot-plan` shows another independent track (`her-feat-batch-session-stats-ojy`) but no dependency relation.
- **File history:** Bead history indicates prior work around REST API, WebSocket streaming, Prometheus exporter/cardinality guardrails, health diagnostics, freshness, export, dashboard, and batch stats, but current branch inspection only found core plugin files. Implement only against actual files present on the branch or mark absent surfaces explicitly.
- **Forecast/capacity:** Forecast is 85 minutes with 0.45 confidence. Capacity says two open actionable items are independent, 50% parallelizable, and this bead is a valid `bv --robot-next` pick.
