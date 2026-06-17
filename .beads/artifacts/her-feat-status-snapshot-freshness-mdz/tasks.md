---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-feat-status-snapshot-freshness-mdz

## Task Metadata

```yaml
id: "1.1"
depends_on: []
parallel: false
conflicts_with: []
files: ["__init__.py"]
estimated_minutes: 20
```

## 1. Core Implementation

### 1.1 Add freshness metadata to snapshot construction in `_on_post_api_request`

```yaml
depends_on: []
parallel: false
files: ["__init__.py"]
estimated_minutes: 20
```

- [ ] In `_on_post_api_request` inside `__init__.py`, after building the existing snapshot dict, add three new keys: `updated_at` = `time.time()`, `updated_monotonic` = `time.monotonic()`, `session_id` = the `session_id` parameter passed to the hook.
- [ ] Import `time` at the top of `__init__.py` if not already present.
- [ ] Ensure all existing snapshot keys (`last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `input_tokens`, `total_tokens`, plus alert fields) remain unchanged.
- [ ] Keep additions inside the existing `_on_post_api_request` call path — no new functions, no new threads, no timers.
- [ ] Build the three new fields within the same lock section (or immediately after, before assignment) to avoid inconsistent snapshot state.

## 2. Testing

### 2.1 Add freshness and session_id assertions to existing test

```yaml
depends_on: ["1.1"]
parallel: false
files: ["tests/test_hook.py"]
estimated_minutes: 15
```

- [ ] In `tests/test_hook.py`, extend the snapshot injection test (e.g. `test_injects_tps_snapshot_on_agent` or the closest equivalent) to assert:
  - `snapshot["updated_at"]` is a `float` and is close to `time.time()` (within 1 second).
  - `snapshot["updated_monotonic"]` is a `float` and is close to `time.monotonic()` (within 1 second).
  - `snapshot["session_id"]` equals the `session_id` passed to the hook.
- [ ] Add a separate test that calls the hook twice with different `session_id` values and asserts the snapshot reflects the most recent one.
- [ ] Verify all existing assertions in `test_hook.py` still pass (no renames, no removals).

## 3. Documentation

### 3.1 Update README with freshness contract and consumer guidance

```yaml
depends_on: ["1.1"]
parallel: true
files: ["README.md"]
estimated_minutes: 10
```

- [ ] Add a section or subsection to the README's status-bar integration guidance documenting the three new fields (`updated_at`, `updated_monotonic`, `session_id`).
- [ ] Describe recommended stale-threshold behavior: consumers compare `time.monotonic() - snapshot["updated_monotonic"]` against a configurable threshold; if exceeded, suppress or gray-out the TPS display.
- [ ] Describe recommended session-mismatch behavior: if `snapshot["session_id"]` does not match the active session, consumers should ignore or reset the display.
- [ ] Note that all fields are additive and backward compatible — no existing consumers break.

## 4. Verification

### 4.1 Full test suite passes

```yaml
depends_on: ["2.1"]
parallel: false
```

- [ ] `pytest tests/test_hook.py tests/test_api.py tests/test_session_tps.py` — all pass.
- [ ] Code review of `__init__.py` confirms no new threads, timers, polling loops, or unbounded storage.
