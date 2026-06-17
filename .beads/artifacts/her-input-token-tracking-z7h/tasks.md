# Tasks: her-input-token-tracking-z7h

## Task 1: Extend _SessionTPS with input token fields
**File:** __init__.py
**Action:** Add `total_input_tokens`, `last_call_input_tokens`, `turn_start_input_tokens` to `__slots__` and `__init__`. Update `record()` to accept and accumulate `input_tokens`. Add `total_tokens` computed property (input + output). Update `reset_turn()` to snapshot input token marker. Update `summary_line()` to show total tokens.
**Verification:** `python -c "from __init__ import _SessionTPS; s = _SessionTPS(); s.record(100, 1.0, 50); print(s.total_input_tokens, s.total_tokens)"`
**Parallel:** No
**Depends on:** None

## Task 2: Update hook to extract input_tokens
**File:** __init__.py
**Action:** Extract `input_tokens` from `usage` dict in `_on_post_api_request`. Pass `input_tokens` to `state.record()`. Add `input_tokens` and `total_tokens` to `_tps_snapshot` dict.
**Verification:** Hook signature accepts input_tokens
**Parallel:** No
**Depends on:** Task 1

## Task 3: Update get_tps_stats API
**File:** __init__.py
**Action:** Add `total_input_tokens` and `total_tokens` to returned dict in `get_tps_stats`.
**Verification:** `get_tps_stats` returns all expected keys
**Parallel:** No
**Depends on:** Task 2

## Task 4: Update README
**File:** README.md
**Action:** Update API section with new fields. Add note about input token tracking in "What It Does".
**Verification:** README reflects new API
**Parallel:** No
**Depends on:** Task 3

## Task 5: Mirror to worktree
**File:** (artifact mirroring)
**Action:** Copy prd.md, prd.json, plan.md, progress.txt, solve-ledger.md to worktree. Create worktree.txt.
**Verification:** Artifacts exist in worktree
**Parallel:** No
**Depends on:** Task 4
