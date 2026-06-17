---
purpose: Decision log for a bead
updated: 2026-06-17
---

# Decisions: her-feat-historical-tps-export-s3i

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Add an additive versioned historical export endpoint rather than changing existing session/event/trend endpoints. | Preserves existing API contracts while giving offline-analysis clients a stable export-oriented surface. | High |
| 2 | Require explicit bounds and enforce default/max limits for export reads. | The bead objective and agent context require avoiding unbounded SQLite reads and large in-memory responses. | High |
| 3 | Make JSON the required primary format. | JSON fits notebooks, scripts, dashboard imports, and FastAPI response modeling without new dependencies. | High |
| 4 | Treat CSV as optional and dependency-free if implemented. | CSV is useful for spreadsheets, but JSON satisfies the core requirement; CSV must not add packages or a build step. | Med |
| 5 | Reuse `PersistentSessionStore` read patterns where practical and add only narrowly scoped bounded helpers if needed. | Existing `load_events` and aggregation methods already encode session/time filtering; any new SQL should remain minimal and indexed. | High |
| 6 | Keep store-unavailable behavior aligned with current API endpoints. | Existing REST handlers return 503 when `store is None`; the export endpoint should be operationally consistent. | High |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Ask users to query the SQLite database directly. | Bypasses API contracts, exposes internal schema details, and is awkward for dashboard import clients. | Schema changes or retention behavior could break users silently. |
| 2 | Extend only `GET /api/v1/events/{session_id}`. | That route is useful but lacks an export envelope, metadata, and session summary context for offline workflows. | Export clients would still scrape multiple endpoints and reconstruct metadata themselves. |
| 3 | Provide an unbounded all-history export. | Violates the bead constraints and could block the local API process or exhaust memory on large databases. | Performance regressions and accidental large data exposure. |
| 4 | Add a background job that writes export files. | Adds state, lifecycle, cleanup, file path, and concurrency concerns beyond the local read-only endpoint goal. | More operational complexity and new failure modes. |
| 5 | Upload exports directly to S3 or another cloud service. | The bead title mentions offline analysis/dashboard import, while current scope and allowed files do not include credentials, cloud clients, or configuration for uploads. | Credential handling and remote side effects would exceed scope and security expectations. |
| 6 | Add pandas or another export dependency. | The project currently keeps API/export behavior lightweight; standard library JSON/CSV is sufficient. | New install burden and packaging failures for optional local API users. |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | Persisted `call_events` and `session_tps` rows are the authoritative source for historical export. | Validated by existing `store.py` schema and API endpoints. | Export would need a different data source or reconciliation layer. |
| 2 | Existing ISO 8601 timestamp strings are comparable enough for bounded SQLite filtering under current storage conventions. | Validated by existing `load_events` tests using ISO timestamp filters. | Implementation would need timestamp normalization or parsed datetime columns. |
| 3 | Local API users prefer bounded HTTP exports over direct database reads for notebooks and dashboards. | Supported by bead title, objective, and existing API-first design. | Feature shape might need a CLI export command instead of or in addition to HTTP. |
| 4 | JSON alone is acceptable for the first implementation if CSV becomes too large for the bead. | Unknown; bead context says JSON first and optionally CSV. | CSV may need to become a MUST in a follow-up bead or implementation clarification. |
| 5 | A single feature bead is sufficient; no epic decomposition is needed. | Validated by 90-minute estimate and limited allowed files. | If cross-session export and CSV both grow complex, split follow-up work may be needed. |
| 6 | The API remains local-only by default. | Validated by README and existing configuration defaults. | Public exposure would require authentication, rate/size hardening, and stronger documentation. |
