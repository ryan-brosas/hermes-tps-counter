# PRD: Track Input Tokens and Total Token Throughput

## Problem
The tps-counter plugin hooks into `post_api_request` which receives a `usage` dict containing both `input_tokens` and `output_tokens`. However, the plugin only tracks output tokens — input tokens are silently discarded. This means:
- No visibility into prompt size (a major cost driver)
- No total token tracking per call or per session
- The status bar cannot show input/output ratio or total throughput
- `get_tps_stats` API returns incomplete data

## Goal
Add input token tracking to the existing TPS plugin, enabling complete token visibility: input, output, and total tokens per call and per session.

## Scope
- In: Input token capture in `_SessionTPS.record()`, new fields in `_SessionTPS`, updated `summary_line()`, updated `_tps_snapshot` dict, updated `get_tps_stats` API
- Out: Cost calculation, per-model breakdown, persistence, new hooks

## Affected Files
- `__init__.py` (modify) — _SessionTPS class + hook + API
- `README.md` (modify) — update API docs with new fields

## Functional Requirements
1. `_SessionTPS.record()` captures `input_tokens` alongside `output_tokens`
2. New fields: `total_input_tokens`, `last_call_input_tokens`, `turn_start_input_tokens`
3. `total_tokens` computed property: `total_input_tokens + total_output_tokens`
4. `summary_line()` includes total tokens (input+output) formatted with `_fmt_tokens`
5. `_tps_snapshot` dict includes `input_tokens` and `total_tokens`
6. `get_tps_stats` returns `total_input_tokens` and `total_tokens`
7. Hook extracts `input_tokens` from `usage` dict (same pattern as `output_tokens`)
8. Backward compatible: all existing fields remain unchanged

## Success Criteria
- [ ] `_on_post_api_request` extracts `input_tokens` from usage dict
- [ ] `_SessionTPS` tracks cumulative input tokens
- [ ] `get_tps_stats` returns `total_input_tokens` and `total_tokens`
- [ ] `_tps_snapshot` includes `input_tokens` key
- [ ] `summary_line()` shows total tokens when available
- [ ] All existing tests (from her-test-suite-l0o) still pass
- [ ] No new dependencies added (stdlib only)

## Non-Goals
- Cost calculation (model pricing varies, out of scope)
- Per-model tracking
- Persistence to disk
- New hooks or commands

## Risks
- Risk: Changing `_tps_snapshot` structure may affect status bar rendering
  - Mitigation: Additive only — new keys, existing keys unchanged
- Risk: `input_tokens` may be 0 or missing for some providers
  - Mitigation: Same guard as `output_tokens` — check > 0 before recording
