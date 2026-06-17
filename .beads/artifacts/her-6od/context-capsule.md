---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-6od

## Objective

Implement opt-in, deterministic sampling for historical call-event persistence so write amplification can be bounded without changing default behavior or lossless aggregate TPS stats.

## Key Patterns

- `Flat plugin module` — Current branch keeps plugin registration, hook handling, privacy policy, status snapshots, observability contract, and `get_tps_stats()` in `__init__.py`; inspect again before `/ship` because `her-cbe` may decompose this monolith. Reference: `__init__.py`.
- `Lossless aggregate first` — `_on_post_api_request` validates event inputs, retrieves `_SessionTPS`, and calls `state.record(output_tokens, duration)` before outbound snapshot/logging. Sampling must not move or skip aggregate updates. Reference: `__init__.py:281-333`.
- `Dependency-free policy objects` — Privacy uses small stdlib-only helpers, `__slots__`, environment variables, normalization, and secret-safe diagnostics. Sampling should follow this style. Reference: `_PrivacyPolicy`, `_get_privacy_policy()`, `get_privacy_diagnostics()` in `__init__.py`.
- `Additive observability contract` — `get_observability_contract()` is static, JSON-serializable, additive, and explicit about unavailable optional surfaces. Sampling metadata should be added in the same compatibility style. Reference: `__init__.py:342-514`, `tests/test_api.py`.
- `Autouse state reset tests` — Existing tests clear `_SESSIONS` around each test. Any new global sampling counters/policies must be resettable or isolated with monkeypatch fixtures. Reference: `tests/test_hook.py`, `tests/test_api.py`, `tests/test_privacy.py`.
- `Privacy at outbound boundaries` — Raw IDs remain internal for lookup/correctness; outbound snapshots, logs, diagnostics, and contract metadata must avoid exposing secrets and must respect existing privacy treatment. Reference: README Privacy Redaction section and `tests/test_privacy.py`.

## Constraints

1. Default behavior must be lossless/backward-compatible: event sampling is disabled unless explicitly configured, and default metadata must state event history is complete.
2. Sampling applies only to historical per-call event row persistence, not to `_SessionTPS.record()`, `get_tps_stats()`, status snapshots, or aggregate counters.
3. Sampling decision must be O(1), in-memory, deterministic, stdlib-only, and must not perform a SQLite read before deciding whether to write an event row.
4. Do not add external dependencies, queue workers, background daemons, REST frameworks, or new storage systems for this bead.
5. Do not leak raw session/model/provider identifiers, privacy salts, or secrets through sampling metadata or skipped counters.
6. Current artifact-repair inspection found no `store.py`, `config.py`, `api.py`, `prometheus_metrics.py`, or SQLite `call_events` code in this branch. Implementation must re-check layout and adapt to the actual branch rather than assuming those modules exist.
7. Coordinate with in-progress `her-cbe` monolith decomposition and `her-feat-batch-session-stats-ojy` if they change file ownership before `/ship`.
8. During implementation, tests come first; during this artifact-repair phase, do not implement code, run tests/builds, close beads, create PRs, or commit.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Recon | `__init__.py`, `tests/*.py`, `README.md`, any future `tps_counter/` modules — read/inspect only before choosing edit targets | `.beads/artifacts/her-6od/prd.md`, `prd.json`, `decisions.md` — do not rewrite source PRD/decision context unless explicitly asked |
| Sampling policy/config | `__init__.py` or future `config.py`/policy module — add env constants, validation, diagnostics, deterministic helper | Dependency manifests or vendored code — stdlib-only requirement |
| Hook integration | `__init__.py` and any future `store.py` call-event insertion seam — gate only historical row insertion | `_SessionTPS.record()` semantics — do not sample aggregate math |
| Metadata/diagnostics | `get_observability_contract()` and diagnostics helpers in `__init__.py`; future `api.py`/export helpers if present | Raw identifiers or secret values in metadata/logging |
| Tests | `tests/test_event_sampling.py`, `tests/test_hook.py`, `tests/test_api.py`, `tests/test_privacy.py` | Brittle tests requiring wall-clock sleeps, randomness, network, or optional dependencies |
| Docs | `README.md` — add config/completeness semantics | Dashboard UX rewrites or Hermes core patch changes; out of scope |
| Verification evidence | `.beads/artifacts/her-6od/completion-evidence.json` during `/verify` only | Closing bead, PR creation, or commits before verification/review gates |

## Graph Context

- **Blast radius:** `bv --robot-impact her-6od` reported low risk and no affected beads/file overlap. Practical code blast radius is expected around `__init__.py`, tests, and README in the current flat branch.
- **Related beads:** `bv --robot-related her-6od` reported none. Human-visible coordination risks are active `her-cbe` decomposition and `her-feat-batch-session-stats-ojy` batch stats because they may touch module layout or observability/API surfaces.
- **File history:** Project memory says `__init__.py` is a 531-line monolith and all tests previously passed. Current inspection confirms only one Python implementation file plus six test files on this branch.
