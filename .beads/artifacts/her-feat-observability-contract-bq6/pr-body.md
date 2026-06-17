## Summary

Adds a cheap, additive machine-readable observability contract for hermes-tps-counter so dashboards, status-bar integrations, and compatibility checks can discover TPS snapshot fields, in-process helper response metadata, and optional REST/WebSocket/Prometheus availability without scraping README prose.

## What Changed

- Added `get_observability_contract()` with contract version, plugin metadata, compatibility guidance, status snapshot field metadata, `get_tps_stats` metadata, and optional surface availability metadata.
- Marked REST/WebSocket/Prometheus surfaces unavailable on this branch because no route, streaming, or exporter modules are present.
- Added focused tests for JSON serializability, required sections, representative fields, plugin metadata, optional-surface flags, and no session-state mutation.
- Documented helper usage, versioning, unknown-field tolerance, stale/session mismatch guidance, and Prometheus label-cardinality guidance.

## Acceptance Criteria

- [x] Expose a stable machine-readable observability contract — `get_observability_contract()` returns JSON-compatible metadata with contract version and plugin metadata.
- [x] Define TPS status snapshot schema — documents `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `updated_at`, `updated_monotonic`, and `session_id`.
- [x] Define API/WebSocket payload metadata — documents `get_tps_stats(session_id)` fields and explicitly marks WebSocket unavailable on this branch.
- [x] Define Prometheus metric metadata — Prometheus section is present, unavailable on this branch, with label-cardinality guidance.
- [x] Preserve backward compatibility — existing hook/API/session/thread-safety tests passed unchanged.
- [x] Keep runtime overhead low — helper is static and test-covered to avoid session-state mutation.
- [x] Document consumer guidance — README covers helper location, versioning, unknown fields, freshness/session mismatch, and cardinality.
- [x] Add focused coverage — contract tests added in `tests/test_api.py`.

## Review

**Verdict:** APPROVE
**Findings:** 0 blocking findings.

## Changed Files

- `.beads/artifacts/her-feat-observability-contract-bq6/*`
- `README.md`
- `__init__.py`
- `tests/test_api.py`

## Verification

- `pytest tests/test_api.py tests/test_hook.py tests/test_session_tps.py tests/test_thread_safety.py` — 54 passed
- Contract smoke check — JSON serialization and required top-level sections passed
- `br lint her-feat-observability-contract-bq6 --json` — no issues
- `br dep cycles --blocking-only --json` — no cycles

## Artifacts

- PRD: `.beads/artifacts/her-feat-observability-contract-bq6/prd.md`
- Plan: `.beads/artifacts/her-feat-observability-contract-bq6/plan.md`
- Evidence: `.beads/artifacts/her-feat-observability-contract-bq6/completion-evidence.json`
- Review: `.beads/artifacts/her-feat-observability-contract-bq6/review-report.md`

## Br Bead

- Bead: `her-feat-observability-contract-bq6`
- Status: closed
- Priority: P2
