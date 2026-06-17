---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-6od

## Task Metadata

```yaml
id: "her-6od"
title: "Add configurable call event sampling to bound SQLite write amplification"
type: "feature"
priority: 2
estimated_minutes: 85
repo: "/home/ryan/repos/hermes-tps-counter"
```

## 1. Setup and Recon

### 1.1 Reconfirm implementation surface before editing

```yaml
depends_on: []
parallel: false
conflicts_with: []
files: ["__init__.py", "tests/*.py", "README.md"]
estimated_minutes: 5
```

- [ ] Inspect the current branch for the real persistence/config/API layout before changing code.
- [ ] If `her-cbe` has landed and code moved into a `tps_counter/` package, map the tasks below from `__init__.py` to the new module names before editing.
- [ ] Confirm whether historical `call_events` persistence exists in the branch being implemented. Current artifact-repair inspection found no `store.py`, `config.py`, `api.py`, or SQLite call-event code; if still absent, add only the sampling policy/metadata seams that make sense for current available surfaces and do not invent unrelated storage.

### 1.2 Define exact sampling contract in tests first

```yaml
depends_on: ["1.1"]
parallel: false
conflicts_with: []
files: ["tests/test_event_sampling.py", "tests/test_hook.py", "tests/test_api.py"]
estimated_minutes: 10
```

- [ ] Add/extend tests for default compatibility: default sampling config reports disabled/lossless semantics and keeps every persistable event.
- [ ] Add tests for validation: allowed rate range, aliases, boundary rates (`1.0` keeps all, `0.0` keeps none only when explicitly enabled), and clear errors for invalid values.
- [ ] Add deterministic-decision tests: identical inputs/counters produce identical keep/drop sequences without calling `random.random()` or querying SQLite.
- [ ] Add aggregate separation tests: after multiple sampled-out calls, `get_tps_stats(session_id)` still reports all valid calls/tokens/durations.

### 1.3 Capture metadata and privacy expectations in tests

```yaml
depends_on: ["1.1"]
parallel: true
conflicts_with: []
files: ["tests/test_api.py", "tests/test_privacy.py"]
estimated_minutes: 8
```

- [ ] Add contract tests asserting a sampling metadata section exists and is JSON-serializable.
- [ ] Assert metadata includes mode/enabled state, rate, deterministic strategy, event-history completeness, and skipped-event count or diagnostics pointer.
- [ ] Assert metadata does not expose privacy salt/secret material or raw identifiers beyond existing backward-compatible raw fields.

## 2. Sampling Policy and Configuration

### 2.1 Add sampling environment/config constants

```yaml
depends_on: ["1.2"]
parallel: false
conflicts_with: ["2.2"]
files: ["__init__.py"]
estimated_minutes: 8
```

- [ ] Add dependency-free constants for explicit opt-in sampling, such as `HERMES_TPS_EVENT_SAMPLING_MODE` and `HERMES_TPS_EVENT_SAMPLING_RATE`.
- [ ] Keep defaults backward-compatible: disabled/lossless, rate `1.0`, history complete.
- [ ] Prefer additive names that are specific to historical event rows, not aggregate TPS stats.

### 2.2 Implement a small validated policy helper

```yaml
depends_on: ["2.1"]
parallel: false
conflicts_with: ["2.1", "2.3"]
files: ["__init__.py"]
estimated_minutes: 12
```

- [ ] Add an internal policy object/helper with `__slots__` if class-based, matching existing style.
- [ ] Normalize disabled aliases (`disabled`, `off`, `false`, `0`) to lossless behavior.
- [ ] Validate configured rates as floats in `[0.0, 1.0]`; fail predictably with a clear `ValueError` or safe diagnostic error path, depending on existing config style in the branch.
- [ ] Expose safe diagnostics for tests and consumers, analogous to `get_privacy_diagnostics()`.

### 2.3 Implement deterministic O(1) keep/drop logic

```yaml
depends_on: ["2.2"]
parallel: false
conflicts_with: ["2.2", "3.1"]
files: ["__init__.py"]
estimated_minutes: 10
```

- [ ] Use a deterministic, in-memory decision strategy; acceptable approaches include a per-policy counter cadence (`keep every Nth event`) or a stable hash threshold over already-available event fields.
- [ ] Do not call `random.random()`.
- [ ] Do not issue a SQLite read before deciding whether to write an event row.
- [ ] Keep the helper independently testable without Hermes runtime objects.

### 2.4 Add skipped-event counters

```yaml
depends_on: ["2.3"]
parallel: false
conflicts_with: ["3.1"]
files: ["__init__.py"]
estimated_minutes: 8
```

- [ ] Track aggregate skipped historical event count in memory.
- [ ] If per-session counters are added, protect the `_SESSIONS` dictionary with `_STATE_LOCK` and avoid leaking raw session IDs in diagnostics.
- [ ] Keep counters dependency-free; only add Prometheus wiring if a Prometheus module already exists on the implementation branch.

## 3. Hook and Persistence Integration

### 3.1 Preserve aggregate update order

```yaml
depends_on: ["2.4"]
parallel: false
conflicts_with: ["3.2"]
files: ["__init__.py"]
estimated_minutes: 8
```

- [ ] In `_on_post_api_request`, keep validation of `session_id`, `output_tokens`, and `api_duration` before any sampling decision.
- [ ] Always call `state.record(output_tokens, duration)` for every valid event before deciding whether to persist a historical event row.
- [ ] Ensure status snapshot injection continues to use lossless aggregate values.

### 3.2 Gate only historical event insertion

```yaml
depends_on: ["3.1"]
parallel: false
conflicts_with: ["3.1", "3.3"]
files: ["__init__.py", "store.py"]
estimated_minutes: 12
```

- [ ] Locate the actual per-call event insertion call on the implementation branch.
- [ ] Apply the sampling policy immediately before that insertion.
- [ ] If the current branch still has no historical `call_events` persistence, do not add unrelated SQLite storage just for this bead; instead leave the helper/metadata ready and document that no event-row insertion surface exists in this branch.
- [ ] On dropped events, increment the skipped counter and skip only the row write.

### 3.3 Preserve failure isolation and logging behavior

```yaml
depends_on: ["3.2"]
parallel: false
conflicts_with: []
files: ["__init__.py"]
estimated_minutes: 6
```

- [ ] Ensure sampling diagnostics/logging never raises from the hook path for normal calls.
- [ ] Keep debug logs privacy-treated using the existing privacy policy.
- [ ] Do not make successful hook handling depend on optional API/Prometheus modules.

## 4. Metadata, Documentation, and Compatibility

### 4.1 Add sampling metadata to observability contract

```yaml
depends_on: ["3.3", "1.3"]
parallel: false
conflicts_with: ["4.2"]
files: ["__init__.py", "tests/test_api.py"]
estimated_minutes: 10
```

- [ ] Add an additive top-level or relevant nested `event_sampling` contract section.
- [ ] Include configured mode/rate, default completeness semantics, deterministic strategy, and guidance that aggregate TPS counters remain lossless.
- [ ] If event export/API routes are absent, mark route-specific history metadata unavailable in the same explicit style used for REST/WebSocket/Prometheus today.

### 4.2 Add diagnostics/API metadata

```yaml
depends_on: ["4.1"]
parallel: false
conflicts_with: ["4.1"]
files: ["__init__.py", "tests/test_api.py", "tests/test_privacy.py"]
estimated_minutes: 8
```

- [ ] Add a public or internal helper for secret-safe sampling diagnostics if needed by tests/contract.
- [ ] Include total skipped due to sampling and whether event history may be incomplete.
- [ ] Avoid raw session/model/provider identifiers in skipped diagnostics.

### 4.3 Document operator behavior

```yaml
depends_on: ["4.2"]
parallel: true
conflicts_with: []
files: ["README.md"]
estimated_minutes: 8
```

- [ ] Add README wording for the sampling environment variables/configuration.
- [ ] Document default lossless behavior, opt-in sampled history, exact aggregate-vs-history distinction, and consumer completeness metadata.
- [ ] Document invalid values and boundary behavior.

## 5. Verification and Workflow Closure Prep

### 5.1 Run focused and full tests

```yaml
depends_on: ["4.1", "4.2", "4.3"]
parallel: false
conflicts_with: []
files: []
estimated_minutes: 8
```

- [ ] `python3 -m pytest tests/test_event_sampling.py -v`
- [ ] `python3 -m pytest tests/test_hook.py tests/test_api.py tests/test_privacy.py -v`
- [ ] `python3 -m pytest tests/ -v`

### 5.2 Record evidence for later verification phase

```yaml
depends_on: ["5.1"]
parallel: false
conflicts_with: []
files: [".beads/artifacts/her-6od/completion-evidence.json"]
estimated_minutes: 5
```

- [ ] During `/verify`, write command outputs and requirement coverage to `completion-evidence.json`.
- [ ] Run `br lint her-6od --json` before review/close.
- [ ] Do not close the bead or create a PR until verification evidence and review artifacts exist.
