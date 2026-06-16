---
purpose: Product Requirements Document for a bead
updated: 2026-06-16
---

# PRD: Add machine-readable observability contract endpoint for TPS snapshots, API responses, and Prometheus metrics metadata

**Bead:** her-feat-observability-contract-bq6 | **Type:** feature | **Priority:** P2
**Created:** 2026-06-16 | **Estimate:** 60 minutes

## Problem

WHEN external dashboards, Hermes status-bar consumers, or local automation need to integrate with hermes-tps-counter observability surfaces THEN they must infer field names, freshness semantics, metric units, and label behavior from README prose or endpoint samples BECAUSE the plugin does not expose a stable machine-readable contract for its TPS snapshot, REST, WebSocket, and Prometheus surfaces.

**Who is affected?** Plugin consumers building dashboards, status-bar integrations, Prometheus/Grafana configuration, and automated compatibility checks.
**Why now?** The graph shows the project has matured across API, dashboard, Prometheus, health, alerting, freshness, and export work, with only one active item in progress. Label attention highlights metrics/feature/api/observability as high-attention areas. A contract endpoint consolidates those surfaces without continuing or duplicating closed implementation beads.

## Scope

### In Scope
- Add an additive, read-only machine-readable observability contract, likely under an API path such as `/api/v1/observability/contract` or an in-process helper exposed from the plugin.
- Include contract version, plugin version, and compatibility/stability notes.
- Describe TPS status snapshot fields, including `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `updated_at`, `updated_monotonic`, and `session_id` semantics.
- Describe current REST/WebSocket payload field names and units at a schema/metadata level without changing existing response contracts.
- Describe Prometheus metric names, metric types, units, and label cardinality expectations.
- Add focused tests for contract shape, required fields, and backward-compatible additive behavior.
- Document where consumers should read the contract and how to treat contract versions.

### Out of Scope
- Implementing new telemetry signals, dashboards, alerting behavior, exports, batching, or status-bar rendering.
- Reworking existing REST, WebSocket, Prometheus, config, persistence, or dashboard features.
- Any breaking change to existing endpoint payloads, metric names, labels, or plugin hook behavior.
- Generating OpenAPI for every internal function or replacing existing README documentation.

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | Expose a stable machine-readable observability contract | MUST | A JSON-compatible contract is available via a documented API route and/or helper and includes contract version plus plugin version. |
| 2 | Define TPS status snapshot schema | MUST | Contract lists snapshot fields, scalar types, units, freshness semantics, and session mismatch guidance. |
| 3 | Define API/WebSocket payload metadata | MUST | Contract identifies existing TPS REST/WebSocket surfaces and describes their response/event payload fields without altering those responses. |
| 4 | Define Prometheus metric metadata | MUST | Contract lists metric names, types, units, and label cardinality expectations; it calls out bounded/high-cardinality dimensions explicitly. |
| 5 | Preserve backward compatibility | MUST | Existing plugin registration, hook path, status snapshot injection, REST routes, WebSocket behavior, and metrics output remain additive-only. |
| 6 | Keep runtime overhead low | SHOULD | Contract generation is static or cheap enough to serve without inspecting all sessions or querying large SQLite tables. |
| 7 | Document consumer guidance | SHOULD | README explains endpoint/helper location, contract versioning, and how consumers should validate or ignore unknown fields. |
| 8 | Add focused coverage | SHOULD | Tests assert required top-level sections and representative fields/metrics, plus no dependency on optional Prometheus availability. |

## Technical Context

Relevant current files and patterns:
- `__init__.py` owns `_on_post_api_request`, `_tps_snapshot` injection, `get_tps_stats`, and core TPS field names.
- `plugin.yaml` contains plugin name/version metadata that the contract should not contradict.
- README already documents status snapshot freshness fields and recommended stale/session mismatch handling.
- Existing bead history includes REST API, WebSocket streaming, Prometheus exporter/histograms/cardinality guardrails, health diagnostics, historical export, threshold alerting, dashboard, and batch session stats. This bead must not reopen those features; it should summarize their contracts for consumers.
- Current working tree snapshot only shows core plugin files in the root; implementers should verify which generated/feature files are present on their branch before selecting exact insertion points.

Research signals:
- Prometheus naming guidance recommends application prefixes, base units in metric names, and warns that every unique label set is a time series; high-cardinality labels such as user IDs or unbounded sets should be avoided.
- Prometheus instrumentation guidance recommends tracking useful internal errors/latency and generally keeping metric cardinality low, investigating alternatives when cardinality can grow large.
- OpenTelemetry metric semantic-convention guidance recommends nesting related metrics in a hierarchy and considering prior art from existing frameworks/libraries.

## Approach

Create an additive observability contract that centralizes the plugin's externally-consumed telemetry metadata. Prefer a small static schema builder (for example `get_observability_contract()` or equivalent) reused by an API endpoint if the API module is present. The contract should be descriptive, not operational: it documents fields, units, freshness semantics, metric labels, and compatibility expectations, but does not query live sessions or mutate plugin state.

**Alternatives considered:**
- README-only contract: rejected because automation cannot reliably consume prose and drift is likely.
- Extend health diagnostics endpoint: rejected because diagnostics report current runtime state, while this contract describes stable integration schemas.
- Full OpenAPI/spec generator: rejected as too broad for one session and not a fit for WebSocket/status snapshot/Prometheus metadata.
- Prometheus-only metadata comments: rejected because the status snapshot and API/WebSocket payloads need the same contract treatment.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Contract drifts from implementation | Med | High | Build schema constants close to producers and add tests for representative fields/metrics. |
| Scope expands into rewriting all endpoints | Med | Med | Keep this bead additive and metadata-only; no response contract changes. |
| Optional modules are absent in minimal installs | Med | Med | Serve static contract without importing optional Prometheus/FastAPI dependencies unless already required by the API layer. |
| Contract over-promises closed-bead features not present on current branch | Med | High | Implementer must inspect the actual branch and include only surfaces available in code, or mark unavailable/optional explicitly. |
| High-cardinality details are underspecified | Low | Med | Include explicit cardinality notes and consumer guidance per Prometheus best practices. |

## Tasks (for epics)

Not an epic.

## Success Criteria

- [ ] A machine-readable observability contract is exposed at a stable documented location.
    - Verify: inspect the endpoint/helper output and confirm top-level sections for snapshot, API/WebSocket payloads, Prometheus metrics, and compatibility metadata.
- [ ] The contract includes field names, types, units, freshness semantics, metric types, and label/cardinality notes for current surfaces.
    - Verify: compare against `__init__.py`, API/WebSocket/Prometheus modules present on the implementation branch, and README documentation.
- [ ] Existing behavior is additive-only and unchanged.
    - Verify: focused tests cover existing public APIs plus new contract shape.
- [ ] README documents how consumers should use contract versioning and tolerate unknown fields.
    - Verify: documentation includes endpoint/helper location and compatibility guidance.
