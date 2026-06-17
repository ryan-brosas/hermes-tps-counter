---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-feat-tps-threshold-alerting-how

## Objective

Add configurable TPS threshold alerting to the tps-counter plugin: evaluate rolling TPS averages in-hook after each API call, maintain alert state machine (idle/firing/resolved), and emit `tps_alert` hook events on transitions.

## Key Patterns

- `sync hook callback` — All work happens in `_on_post_api_request`, which runs after each API call. No background threads. Evaluation is O(1) arithmetic on a small rolling window. Reference: `__init__.py`
- `_STATE_LOCK threading.Lock()` — All session state mutations (including alert state) must be inside `with _STATE_LOCK:` blocks. Reference: `__init__.py`
- `_SESSIONS` dict — Per-session state keyed by `session_id`. Extend `_SessionTPS` dataclass with alert fields. Reference: `__init__.py`
- `ctx.register_hook(name, callback)` — Register new hooks via this pattern. For emission, call `ctx.hooks.tps_alert(payload)` or equivalent. Reference: `__init__.py`
- `agent._tps_snapshot` — Status bar reads this dict. Add `alert_state` and `alert_indicator` keys. Reference: `__init__.py`
- `conftest.py fixtures` — Tests use `mock_ctx` and `mock_agent` fixtures. Follow pattern in `tests/test_hook.py`

## Constraints

1. **No background threads** — Alert evaluation must be synchronous in the hook callback
2. **Thread safety** — All alert state mutations inside `with _STATE_LOCK:` — never outside the lock
3. **No regressions** — Existing status bar integration, hook registration, and session tracking must continue working unchanged
4. **Zero-config default** — Plugin must work out of the box with sensible defaults (auto-calculated threshold from first 10 calls)
5. **Lightweight evaluation** — Rolling window is small (default 5); evaluation is O(1) mean calculation; no sorting or complex data structures

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Core alert engine | `__init__.py` — add fields to `_SessionTPS`, add `_evaluate_alert()`, extend `register()`, extend `_on_post_api_request` | `__init__.py` — do not refactor existing classes or rename existing functions |
| Status bar indicator | `__init__.py` — extend `_tps_snapshot` dict | `__init__.py` — do not change status bar format for non-alert fields |
| Tests | `tests/test_threshold_alerting.py` — create new file | `tests/test_hook.py` — do not modify existing tests |
| Documentation | `README.md` — add "Threshold Alerting" section | `README.md` — do not rewrite existing sections |
| General | `.beads/artifacts/` — workflow files | `.beads/beads.db`, `.env.local`, `credentials` |

## Graph Context

- **Blast radius:** Minimal — isolated node (degree 0), no downstream dependents
- **Related beads:** None (no dependency edges)
- **File hotspots:** `__init__.py` (3 prior beads touched it), `tests/test_hook.py` (test pattern reference)
- **Forecast:** 85 minutes (confidence 0.35)
- **Parallel track:** Can run alongside `her-feat-batch-session-stats-ojy` (different files, no conflicts)
