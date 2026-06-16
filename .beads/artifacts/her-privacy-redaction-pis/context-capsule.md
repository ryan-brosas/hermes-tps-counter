---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-privacy-redaction-pis

## Objective

Add configurable, dependency-free privacy redaction for TPS observability identifiers so raw `session_id`, `model`, `provider`, and configured future identifier-like fields remain in trusted state but are transformed before outbound snapshots, helper responses, contract metadata, logs, docs, and any present optional observability surfaces expose them.

## Key Patterns

- `Trusted raw session state` — `_SESSIONS` is keyed by raw `session_id`, and `_get_session(session_id)` creates/returns the raw-session state. Do not pseudonymize keys or lookup inputs; redaction happens only at outbound boundaries. Reference: `__init__.py:18-20`, `__init__.py:105-109`.
- `Hook snapshot producer` — `_on_post_api_request` reads `session_id`, `usage.output_tokens`, and `api_duration`, records counters, and injects `agent._tps_snapshot` with TPS numeric fields, freshness timestamps, and `session_id`. Preserve numeric semantics and disabled-mode raw `session_id`; apply redaction only before snapshot exposure when enabled. Reference: `__init__.py:112-154`.
- `Debug logging boundary` — the hook currently logs `session_id[:8]` at debug level. This is an outbound diagnostic surface and must use the shared redaction helper in enabled mode; disabled mode may remain compatible. Reference: `__init__.py:147-154`.
- `Public stats helper` — `get_tps_stats(session_id)` accepts a raw session id and currently returns counters without echoing the id. Preserve lookup and response compatibility; if future identifiers appear in returned payloads, treat them through the shared helper. Reference: `__init__.py:308-322`.
- `Observability contract` — `get_observability_contract()` is static, JSON-compatible, dependency-free, and already documents status snapshot/API/WebSocket/Prometheus availability. Add privacy mode and per-field treatment metadata additively; do not inspect sessions or expose secrets. Reference: `__init__.py:163-305`.
- `README freshness guidance` — README documents `updated_at`, `updated_monotonic`, `session_id`, stale thresholds, and session mismatch handling. Keep this guidance but add privacy-mode migration notes for treated `session_id` comparisons. Reference: `README.md:62-98`, `README.md:121-170`.
- `Existing tests` — `tests/test_hook.py` asserts default raw snapshot `session_id` and freshness fields; `tests/test_api.py` asserts `get_tps_stats`, `register`, contract sections, and absent optional surfaces. Add privacy tests without weakening these compatibility checks. References: `tests/test_hook.py`, `tests/test_api.py`.

## Constraints

1. Do not implement during `/plan`; `/ship` may touch implementation files. This repair phase writes only `.beads/artifacts/her-privacy-redaction-pis/`.
2. Never create a new bead, close beads, open PRs, run package/build commands, or commit for this planning repair.
3. Raw identifiers must remain available for internal correctness: `_SESSIONS` keys, `_get_session`, and `get_tps_stats(session_id)` lookup inputs continue to use raw `session_id`.
4. Disabled/default-compatible mode must preserve existing public field names and raw values, especially `_tps_snapshot["session_id"]`, current `get_tps_stats` outputs, `register()` behavior, and top-level contract sections.
5. Enabled mode must not emit raw `session_id`, `model`, `provider`, or configured identifier-like future fields through available outbound surfaces: status snapshot, public helper/API payloads, observability contract diagnostics/metadata, logs, docs examples, and any present REST/WebSocket/dashboard/Prometheus/export modules.
6. Pseudonyms must be deterministic for the same raw value plus configured scope/salt and must not include raw substrings. Prefer standard-library HMAC/keyed hashing with bounded output length.
7. Salt/secret material must never be returned, logged, serialized, exported, documented as a real value, or included in contract diagnostics.
8. Hook-path overhead must remain low and dependency-free: no network calls, no new packages, no background workers, no route servers, no scanning all sessions, and no optional FastAPI/Prometheus imports solely for privacy.
9. Optional surfaces are conditional. If `api.py`, dashboard, WebSocket, `prometheus_metrics.py`, or export/store modules are absent, do not create them for this bead; keep contract metadata truthful and mark unavailable surfaces unavailable.
10. Contract and README changes should be additive and consumer-safe: unknown fields must remain ignorable, absent optional surfaces must not be over-promised, and existing stale/session mismatch semantics must not conflict with privacy guidance.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Policy/helper | `__init__.py` or optional `config.py` — add dependency-free privacy policy, field treatment mapping, single-value/payload redaction, safe diagnostics | Changing `_SESSIONS` keying, requiring external packages, exposing salt/secret, adding background workers |
| Hook surfaces | `__init__.py` — apply helper to `agent._tps_snapshot` identifiers and debug log output | Changing TPS numeric calculations, removing freshness fields, breaking disabled raw `session_id` compatibility |
| Public helper/contract | `__init__.py` — preserve `get_tps_stats` lookup/output and add privacy metadata to `get_observability_contract()` | Returning secrets, inspecting live sessions from contract helper, renaming/removing existing contract top-level sections |
| Optional REST/WebSocket/dashboard/export/metrics | `api.py`, `dashboard.py`, `prometheus_metrics.py`, `store.py`, or existing route/export modules only if present — apply shared helper to outbound payloads/labels/exports | Creating new REST/WebSocket/dashboard/Prometheus/export features absent on branch; adding framework dependencies |
| Tests | `tests/test_hook.py`, `tests/test_api.py`, optional `tests/test_privacy.py` — assert disabled compatibility, deterministic pseudonyms, enabled no-leak behavior, no secret leakage, unchanged counters | Weakening existing hook/API tests, deleting compatibility assertions, relying on external services |
| Documentation | `README.md` — explain modes, field treatment, deterministic grouping, migration, no-secret examples, and cardinality guidance | Removing stale/session mismatch guidance, claiming absent endpoints/metrics exist, showing real/reversible secrets |
| Bead artifacts | `.beads/artifacts/her-privacy-redaction-pis/` — planning outputs only | Writes outside this artifact directory during the plan repair phase |

## Graph Context

- **Blast radius:** `bv --robot-impact her-privacy-redaction-pis` reports low risk, risk score 0, no affected beads, and no linked files. `bv --robot-file-hotspots` reports no hotspots, but `__init__.py` is the practical coordination file for implementation.
- **Related beads:** The impact network contains only `her-privacy-redaction-pis`; `br dep tree` has no dependencies. `bv --robot-plan` shows `her-feat-batch-session-stats-ojy` as another independent track, not a blocker. PRD notes conceptual relationship to `her-feat-observability-contract-bq6`; use the existing observability contract as the privacy metadata location.
- **File history/current branch:** Current inspection found core plugin implementation in `__init__.py`, docs in `README.md`, and active tests in `tests/test_hook.py` and `tests/test_api.py`. Contract currently marks REST/WebSocket/Prometheus unavailable. Optional files such as `api.py`, `dashboard.py`, `prometheus_metrics.py`, and `store.py` may exist in other branches or future beads; `/ship` must re-check before touching or documenting them as available.
- **Forecast/capacity:** Forecast is 85 minutes with 0.35 confidence. Capacity reports two open actionable items, 50% parallelizable, serial and parallel estimates both 85 minutes for this bead, and no blocking cycles.
- **Sequencing:** Implement policy first, then current surfaces, then contract/optional surfaces, then tests/docs, then verification. Do not split simultaneous edits to `__init__.py` without coordination.
