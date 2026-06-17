---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-br5

## Task Metadata

```yaml
id: "her-br5"
title: "Add bounded in-memory session retention controls"
type: "feature"
priority: 2
estimated_minutes: 85
primary_files:
  - "__init__.py"
  - "tests/test_api.py"
  - "tests/test_thread_safety.py"
constraints:
  - "stdlib only"
  - "no background threads, daemons, schedulers, REST, WebSocket, Prometheus, SQLite, package managers, or Hermes core changes"
  - "default behavior remains disabled/backward-compatible"
```

## 1. Setup and Baseline

### 1.1 Confirm current state and public shapes

```yaml
depends_on: []
parallel: false
conflicts_with: []
files: ["__init__.py", "tests/test_api.py", "tests/test_thread_safety.py"]
estimated_minutes: 10
```

- [ ] Inspect `_SESSIONS`, `_STATE_LOCK`, `_SessionTPS`, `_get_session()`, `_on_post_api_request()`, `get_tps_stats()`, `get_observability_contract()`, and current tests.
- [ ] Record the existing zero-value missing-session shape exactly: `{"calls": 0, "avg_tps": 0, "last_tps": 0, "peak_tps": 0, "total_output_tokens": 0}`.
- [ ] Identify a deterministic test seam for monotonic time; prefer patching `time.monotonic` or injecting a private helper over real sleeps.

### 1.2 Add focused failing tests first

```yaml
depends_on: ["1.1"]
parallel: false
conflicts_with: ["2.1", "2.2", "2.3", "3.1"]
files: ["tests/test_api.py", "tests/test_thread_safety.py"]
estimated_minutes: 20
```

- [ ] Add tests proving no env vars keeps default behavior and existing public helper shapes.
- [ ] Add max-session tests using `HERMES_TPS_MAX_SESSIONS` with multiple synthetic session writes; assert oldest inactive sessions prune to the bound.
- [ ] Add TTL tests using patched monotonic values and `HERMES_TPS_SESSION_TTL_SECONDS`; assert stale sessions are removed and recent sessions remain.
- [ ] Add a pruned-session test asserting `get_tps_stats(pruned_id)` returns the existing zero-value missing-session shape and does not recreate the entry.
- [ ] Add invalid env value tests for unset, zero, negative, non-numeric, and blank values; assert disabled behavior/no crash.
- [ ] Add contract/diagnostics tests asserting JSON serialization, env var names, active numeric limits, enabled flags, and no raw session identifiers or secret material.
- [ ] Extend thread-safety coverage to exercise pruning while concurrent readers/writers call `_get_session()`, `record()`, and `get_tps_stats()`.

## 2. Core Implementation

### 2.1 Add retention configuration helpers

```yaml
depends_on: ["1.2"]
parallel: false
conflicts_with: ["2.2", "2.3", "3.1"]
files: ["__init__.py"]
estimated_minutes: 15
```

- [ ] Define `_RETENTION_MAX_SESSIONS_ENV = "HERMES_TPS_MAX_SESSIONS"` and `_RETENTION_SESSION_TTL_SECONDS_ENV = "HERMES_TPS_SESSION_TTL_SECONDS"` near existing env constants.
- [ ] Add private stdlib-only parsing helpers that treat unset, blank, zero, negative, and invalid values as disabled.
- [ ] Return sanitized policy diagnostics containing only enabled state, env var names, active numeric limits, and disabled/invalid status as needed.
- [ ] Avoid caching env reads globally unless tests can safely reset state; existing privacy policy reads env on demand, so mirror that style.

### 2.2 Track last-update metadata per session

```yaml
depends_on: ["2.1"]
parallel: false
conflicts_with: ["2.3"]
files: ["__init__.py"]
estimated_minutes: 10
```

- [ ] Add `last_updated_monotonic` or equivalent private metadata to `_SessionTPS.__slots__` and initialize it with `time.monotonic()`.
- [ ] Update the metadata in `record()` after successful call accounting.
- [ ] Preserve existing `record()`, `avg_tps`, `turn_tps`, `reset_turn()`, `summary_line()`, and `get_tps_stats()` return fields unless explicitly adding internal-only metadata.

### 2.3 Implement pruning under `_STATE_LOCK`

```yaml
depends_on: ["2.2"]
parallel: false
conflicts_with: ["3.1", "4.1"]
files: ["__init__.py"]
estimated_minutes: 20
```

- [ ] Add a private `_prune_sessions(...)` helper that must only mutate `_SESSIONS` while `_STATE_LOCK` is held.
- [ ] Apply TTL pruning first using monotonic age comparison so sessions older than the configured threshold are deleted.
- [ ] Apply max-session pruning by sorting candidates by oldest `last_updated_monotonic`; never prune the currently recorded `session_id` if avoidable.
- [ ] Skip all pruning work quickly when both retention controls are disabled.
- [ ] Integrate pruning opportunistically after successful writes through `_on_post_api_request()`/session record flow without adding background work.
- [ ] If pruning before stats reads is chosen, ensure it remains read-only from the caller perspective and never creates a session; otherwise leave reads as non-creating dictionary lookups.

## 3. Observability and Privacy Contract

### 3.1 Expose retention policy metadata safely

```yaml
depends_on: ["2.1", "2.3"]
parallel: false
conflicts_with: ["2.3"]
files: ["__init__.py", "tests/test_api.py"]
estimated_minutes: 15
```

- [ ] Add retention metadata to `get_observability_contract()` or a related diagnostics helper.
- [ ] Include env var names, whether each policy is enabled, sanitized configured numeric values, and a statement that pruning is opportunistic/in-memory only.
- [ ] Do not include raw session IDs, session lists, model/provider values, salts, hashes of live IDs, or per-session timestamps.
- [ ] Keep contract changes additive and JSON-serializable.

## 4. Regression and Concurrency Hardening

### 4.1 Finalize thread-safety behavior

```yaml
depends_on: ["2.3", "3.1"]
parallel: false
conflicts_with: []
files: ["__init__.py", "tests/test_thread_safety.py"]
estimated_minutes: 15
```

- [ ] Ensure `_STATE_LOCK` protects all `_SESSIONS` create/read/delete operations.
- [ ] Ensure public return shapes remain stable even if a session is pruned between lookup and result construction.
- [ ] Run and fix focused concurrency tests until no crashes or inconsistent public shapes occur.

## 5. Verification

### 5.1 Run focused and full verification

```yaml
depends_on: ["4.1"]
parallel: false
conflicts_with: []
files: [".beads/artifacts/her-br5/completion-evidence.json"]
estimated_minutes: 15
```

- [ ] `python3 -m pytest tests/test_api.py -v`
- [ ] `python3 -m pytest tests/test_thread_safety.py -v`
- [ ] `python3 -m pytest tests/ -v`
- [ ] Inspect `__init__.py` and dependency metadata to confirm no external packages, background threads, schedulers, REST/WebSocket/Prometheus servers, SQLite persistence, package manager commands, or Hermes core changes were introduced.
- [ ] During `/verify`, write `.beads/artifacts/her-br5/completion-evidence.json` with command outputs and requirement coverage.
