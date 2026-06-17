---
purpose: Agent spawn context for a bead
updated: 2026-06-17
---

# Context Capsule: her-feat-status-snapshot-freshness-mdz

## Objective

Add `updated_at`, `updated_monotonic`, and `session_id` fields to the TPS status snapshot dict in `_on_post_api_request` so consumers can detect stale or cross-session data without plugin-side background work.

## Key Patterns

- `snapshot dict construction` — The existing snapshot is built as a plain dict inside `_on_post_api_request`. New fields must be added to this same dict, not as a separate object. Reference: `__init__.py` (`_on_post_api_request` function).
- `alert fields under _STATE_LOCK` — Alert fields (`alert_state`, `alert_threshold`, `alert_indicator`) are added under `_STATE_LOCK`. Freshness fields (`updated_at`, `updated_monotonic`, `session_id`) do not require the lock and can be set before or after the alert section, but must be present in the final assigned snapshot. Reference: `__init__.py`.
- `test_injects_tps_snapshot_on_agent` — Primary test that asserts snapshot keys after a hook call. New assertions should be added here or adjacent. Reference: `tests/test_hook.py`.

## Constraints

1. NEVER remove, rename, or change semantics of existing `_tps_snapshot` keys (`last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `input_tokens`, `total_tokens`, `alert_state`, `alert_threshold`, `alert_indicator`).
2. No new threads, timers, polling loops, `time.sleep()`, or background workers — changes must stay entirely within the existing `_on_post_api_request` call path.
3. No unbounded memory growth — the three new fields are constant-size scalars added to each snapshot dict.
4. Use `time.time()` for wall-clock and `time.monotonic()` for robust age calculation — do not use only wall-clock (system clock changes can break freshness checks).
5. Public API (`get_session_tps`, `get_all_session_tps`) is unchanged; freshness fields are internal to the snapshot contract.

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Add freshness fields | `__init__.py` — add `updated_at`, `updated_monotonic`, `session_id` to snapshot dict in `_on_post_api_request` | `__init__.py` — do not rename/remove existing fields; do not add imports beyond `time` |
| Add test assertions | `tests/test_hook.py` — add freshness/compat assertions | `tests/test_hook.py` — do not delete or weaken existing assertions |
| Update docs | `README.md` — add freshness contract section | `README.md` — do not remove existing integration examples |
| Verification | `tests/test_api.py`, `tests/test_session_tps.py` — read-only verification | — |

## Graph Context

- **Blast radius:** None — no files linked to other beads in the graph.
- **Related beads:** None direct. `her-input-token-tracking-z7h` is the only upstream keystone in the graph but does not share files with this bead.
- **File history:** No prior beads touch `__init__.py` snapshot construction path.
