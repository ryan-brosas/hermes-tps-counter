---
purpose: Wave-sequenced implementation plan
updated: 2026-06-17
---

# Plan: her-6od

**Goal:** Add opt-in deterministic sampling for persisted historical call-event rows so SQLite write volume can be bounded while default behavior and aggregate TPS counters remain lossless.

## Graph Context

- **Blast radius:** Low from `bv --robot-impact her-6od`; no existing bead/file overlap reported. Current repo inspection shows the active code is still the flat `__init__.py` plugin plus tests, with no `store.py`, `config.py`, `api.py`, or `prometheus_metrics.py` present on this branch.
- **Unblocks:** None reported by bv.
- **Blocked by:** None reported by bv. Coordinate manually with in-progress `her-cbe` monolith decomposition and `her-feat-batch-session-stats-ojy` if their branches move the persistence/API surfaces before `/ship`.
- **Critical path:** No; P2 feature, actionable and unblocked.
- **Forecast:** `bv --robot-forecast her-6od` estimates 85 minutes with low confidence because project velocity data is sparse.

## Observable Truths

What must be TRUE for the goal to be achieved:

1. With default configuration, every valid hook event that was persisted before this bead is still persisted; `get_tps_stats()` and status snapshots remain backward-compatible.
2. When sampling is explicitly enabled/configured, aggregate session counters (`calls`, `avg_tps`, `last_tps`, `peak_tps`, `total_output_tokens`, `total_duration`) still count every valid hook event, while only selected historical call-event rows are written.
3. Sampling decisions are deterministic, O(1), dependency-free, and made before any per-event SQLite write without an extra SQLite read.
4. Diagnostics/contract/export metadata clearly states the configured sampling policy, rate, completeness semantics, and skipped-event counts without exposing raw session/model/provider identifiers.
5. Tests cover default compatibility, invalid configuration, boundary rates, deterministic keep/drop decisions, aggregate-vs-history separation, metadata, and privacy-safe output.

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| Sampling config/policy helper | Typed/default configuration, validation, deterministic keep/drop decision | `__init__.py` in current branch, or future `config.py`/policy module if `her-cbe` lands first | Need |
| Hook-path integration | Applies sampling only around historical event persistence after aggregate update | `__init__.py` and any future persistence module such as `store.py` | Need |
| Skipped-event diagnostics | Secret-safe count of events skipped due to sampling | `__init__.py` diagnostics/contract helpers; optional future Prometheus surface only if present | Need |
| Metadata contract | Consumer-visible completeness policy for event history/export/API | `get_observability_contract()` in `__init__.py`; future `api.py`/export helpers if present | Need |
| Tests | Regression and edge coverage for all requirements | `tests/test_hook.py`, `tests/test_api.py`, new `tests/test_event_sampling.py` if needed | Need |
| Documentation | Operator-facing config and completeness semantics | `README.md` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | 1.1-1.3: Reconfirm current layout, locate call-event persistence/export surfaces, write focused failing tests | Partly | PRD and this plan exist | Focused tests fail for missing sampling behavior, e.g. `python3 -m pytest tests/test_event_sampling.py tests/test_api.py::TestObservabilityContract -v` |
| 2 | 2.1-2.4: Add config parser/policy helper and deterministic sampling counters | No | Wave 1 tests define expected public contract | Policy/config tests pass, no hook integration yet |
| 3 | 3.1-3.3: Integrate sampling after aggregate update and before historical event write | No | Policy helper exists | Hook tests prove aggregates are lossless and event rows are sampled/skipped only when configured |
| 4 | 4.1-4.3: Add metadata/diagnostics/docs | Partly | Hook behavior is correct | Contract/docs tests pass and serialized outputs contain no raw secrets/identifiers beyond existing raw-default compatibility |
| 5 | 5.1-5.2: Full regression and workflow evidence | No | Waves 1-4 complete | `python3 -m pytest tests/ -v` and `br lint her-6od --json` pass during `/verify` |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

Run during `/ship` and `/verify`, not during this artifact-repair phase:

```bash
cd /home/ryan/repos/hermes-tps-counter
python3 -m pytest tests/test_event_sampling.py -v
python3 -m pytest tests/test_hook.py tests/test_api.py tests/test_privacy.py -v
python3 -m pytest tests/ -v
br lint her-6od --json
```
