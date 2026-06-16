---
purpose: Decision log for a bead
updated: 2026-06-17
---

# Decisions: her-privacy-redaction-pis

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Keep raw identifiers inside trusted in-process state, but redact immediately before outbound exposure. | Internal lookup by raw `session_id` is required for existing correctness, while the privacy requirement is about observability outputs that may be shared. | High |
| 2 | Use one shared policy/helper for redacting identifier-like fields. | A central implementation reduces drift across status snapshots, API/helper responses, logs, contract metadata, dashboard data, future REST/WebSocket surfaces, Prometheus labels, and exports. | High |
| 3 | Preserve disabled/default-compatible behavior. | Current tests, README guidance, and existing consumers rely on raw `session_id` in `_tps_snapshot`; privacy mode must be opt-in or otherwise compatibility-preserving. | High |
| 4 | Prefer deterministic keyed pseudonyms for grouping-capable redaction. | Operators need stable grouping by session/model/provider without exposing raw values; keyed hashing/HMAC from the standard library avoids external dependencies and reduces reversibility risk. | High |
| 5 | Represent field treatment in the observability contract or diagnostics without exposing secrets. | Consumers need to know whether values are raw, redacted, pseudonymized, or omitted; secret material such as salts must never be returned. | Med |
| 6 | Mark absent optional surfaces as unavailable rather than designing as if they exist. | The current branch exposes core plugin helpers and status snapshot behavior; REST/WebSocket/Prometheus/dashboard/export implementations may be absent and should not be over-promised. | High |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | README-only privacy instructions. | Prose guidance does not stop raw identifiers from being emitted by code and is likely to drift from implementation. | Raw values continue to leak through snapshots, logs, metrics, or exports despite documentation. |
| 2 | Per-surface ad hoc redaction logic. | Multiple implementations would diverge as observability surfaces grow. | One surface may hash while another logs raw values, producing inconsistent privacy guarantees. |
| 3 | Random opaque IDs per event. | Non-deterministic values prevent grouping and make dashboards/metrics less useful. | Operators lose the ability to correlate events for the same session/model/provider. |
| 4 | Remove all identifiers from all outputs. | Some consumers need source identity for stale/session-mismatch checks and aggregate grouping. | Status-bar safety and observability correlation regress; users may disable privacy protections to regain utility. |
| 5 | Add an external redaction dependency or service. | The plugin is currently lightweight and dependency-free; hook-path work should remain local and bounded. | Install complexity, network failure modes, and latency are introduced into TPS capture. |
| 6 | Expose redaction salt/secret for debugging. | Secret disclosure undermines pseudonymization. | Pseudonyms become dictionary-attackable or reversible. |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | The bead should repair create-phase artifacts only, not implement code. | Validated by user instruction. | If implementation were requested, plan/tasks and code changes would be needed in a later phase. |
| 2 | `session_id` is the primary currently exposed identifier; `model` and `provider` may appear in future or adjacent observability surfaces. | Validated by current `__init__.py` and bead context. | If model/provider already exist on another branch, implementers must include those concrete files in coverage. |
| 3 | Current branch may not contain REST, WebSocket, Prometheus, dashboard, or export modules. | Validated by README/contract and file inspection of current branch. | If those modules are added before implementation, the redaction coverage and tests must include them. |
| 4 | Disabled/default-compatible privacy mode is required to avoid breaking existing consumers. | Validated by existing tests and README examples that use raw `session_id`. | If product policy changes to privacy-on by default, migration requirements and test expectations must be updated. |
| 5 | Deterministic pseudonymization can use standard-library keyed hashing/HMAC with a configured secret or stable salt. | Unknown until implementation config source is chosen. | If no secret/config source exists, implementation must define safe fallback semantics and document their limits. |
