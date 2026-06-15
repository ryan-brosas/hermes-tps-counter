# Plan: her-input-token-tracking-z7h — Input Token Tracking

## Wave 1: Core changes (sequential)
### Task 1.1: Extend _SessionTPS with input token fields
- Modifies: __init__.py — _SessionTPS class
- Changes:
  - Add `total_input_tokens` to __slots__ and __init__
  - Add `last_call_input_tokens` to __slots__ and __init__
  - Add `turn_start_input_tokens` to __slots__ and __init__
  - Update `record()` to accept and accumulate `input_tokens`
  - Add `total_tokens` computed property (input + output)
  - Update `turn_tps` to use total tokens (or keep output-only, document)
  - Update `reset_turn()` to snapshot input token marker
  - Update `summary_line()` to show total tokens
- Verification: `python -c "from __init__ import _SessionTPS; s = _SessionTPS(); s.record(100, 1.0, 50); print(s.total_input_tokens, s.total_tokens)"`

### Task 1.2: Update hook to extract input_tokens
- Modifies: __init__.py — _on_post_api_request
- Changes:
  - Extract `input_tokens` from `usage` dict (same pattern as output_tokens)
  - Pass `input_tokens` to `state.record()`
  - Add `input_tokens` to `_tps_snapshot` dict
  - Add `total_tokens` to `_tps_snapshot` dict
- Verification: Hook signature accepts input_tokens

### Task 1.3: Update get_tps_stats API
- Modifies: __init__.py — get_tps_stats
- Changes:
  - Add `total_input_tokens` to returned dict
  - Add `total_tokens` to returned dict
- Verification: `get_tps_stats` returns all expected keys

## Wave 2: Documentation (sequential)
### Task 2.1: Update README
- Modifies: README.md
- Changes:
  - Update API section with new fields
  - Add note about input token tracking in "What It Does"
- Verification: README reflects new API

## Wave 3: Mirror artifacts (sequential)
### Task 3.1: Mirror to worktree
- Copies: prd.md, prd.json, plan.md, progress.txt, solve-ledger.md
- Creates: worktree.txt
- Verification: artifacts exist in worktree

## File Ownership
| Wave | Files |
|------|-------|
| 1 | __init__.py |
| 2 | README.md |
| 3 | (artifact mirroring) |

## Context Capsule
- Plugin code: /home/ryan/repos/hermes-tps-counter/__init__.py (169 lines)
- _SessionTPS class: lines 23-98
- Hook function: lines 108-146
- get_tps_stats: lines 156-169
- Key pattern: usage.get("output_tokens", 0) — same for input_tokens
- Thread safety: _STATE_LOCK protects _SESSIONS dict
- Backward compat: all existing fields unchanged, new fields additive
