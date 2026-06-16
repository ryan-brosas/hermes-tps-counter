---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-feat-observability-contract-bq6

## Task Metadata

```yaml
id: "her-feat-observability-contract-bq6"
depends_on: []
parallel: partially
conflicts_with: ["tasks touching __init__.py", "tasks touching README.md", "tasks changing public observability fields"]
files:
  - "__init__.py"
  - "README.md"
  - "plugin.yaml"
  - "tests/test_api.py"
  - "tests/test_hook.py"
  - "tests/test_session_tps.py"
  - "tests/test_thread_safety.py"
  - "api.py (only if present on implementation branch)"
  - "prometheus_metrics.py (only if present on implementation branch)"
estimated_minutes: 85
```

## 1. Setup and Surface Inventory

### 1.1 Verify branch surfaces before implementation

```yaml
depends_on: []
parallel: true
files: ["__init__.py", "README.md", "plugin.yaml", "tests/"]
estimated_minutes: 10
```

- [ ] Confirm the current implementation branch contents before editing: whether `api.py`, any WebSocket route/module, and `prometheus_metrics.py` exist.
- [ ] Read `__init__.py` and map current producers/consumers: `_on_post_api_request`, `_tps_snapshot`, `get_tps_stats`, `register`, `_SESSIONS`, and `_STATE_LOCK`.
- [ ] Read `plugin.yaml` version and use that value for the contract's plugin metadata; do not hard-code a conflicting version.
- [ ] Read README status snapshot freshness guidance and preserve the documented stale/session mismatch semantics.

### 1.2 Choose contract availability language

```yaml
depends_on: ["1.1"]
parallel: true
files: ["__init__.py", "README.md"]
estimated_minutes: 5
```

- [ ] Decide exact section names before coding: `contract`, `compatibility`, `status_snapshot`, `api`, `websocket`, `prometheus`.
- [ ] If REST/WebSocket/Prometheus code is absent, plan those sections as metadata with `available: false`, `reason`, and `consumer_guidance` rather than omitting them.
- [ ] Set initial contract version to a simple string such as `"1.0.0"`; document that additive fields do not require consumers to fail.

## 2. Core Implementation

### 2.1 Add dependency-free contract helper

```yaml
depends_on: ["1.1", "1.2"]
parallel: false
files: ["__init__.py", "plugin.yaml"]
estimated_minutes: 20
```

- [ ] Add `get_observability_contract()` to `__init__.py` near the public `get_tps_stats()` helper.
- [ ] Keep the helper static/cheap: no session iteration, no SQLite access, no network calls, no optional FastAPI/Prometheus imports.
- [ ] Return only JSON-compatible values: dictionaries, lists, strings, booleans, numbers, and nulls.
- [ ] Include contract metadata: contract name, contract version, plugin name, plugin version from `plugin.yaml` or an internal constant kept consistent with it, generated/static indicator, and stability notes.
- [ ] Describe `status_snapshot.fields` for `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `updated_at`, `updated_monotonic`, and `session_id` with type, unit, source, and freshness/session guidance.
- [ ] Describe `api.surfaces.get_tps_stats` fields for `calls`, `avg_tps`, `last_tps`, `peak_tps`, `total_output_tokens`, and `total_duration`, including units and absent-session zero behavior.
- [ ] Add `websocket` and `prometheus` sections. Include branch-available metadata only for surfaces actually present; otherwise state they are absent on this branch and avoid naming nonexistent metrics as active.
- [ ] Export/import compatibility must remain unchanged: do not require callers to instantiate plugin state to read the contract.

### 2.2 Add optional REST route adapter only when route layer exists

```yaml
depends_on: ["2.1"]
parallel: false
files: ["api.py (if present)", "tests/test_api.py"]
estimated_minutes: 10
```

- [ ] If an API/router module exists on the branch, add a read-only GET route at `/api/v1/observability/contract` or the repository's established equivalent path.
- [ ] The route must return exactly the `get_observability_contract()` output or a shallow JSON response wrapper that preserves the contract body.
- [ ] Do not create a new API framework dependency just to expose the route. If no API layer exists, skip this task and rely on the helper; document the absence in README and contract metadata.
- [ ] Do not alter existing REST route payloads, WebSocket events, metrics output, hook registration, or status snapshot injection behavior.

## 3. Testing

### 3.1 Add contract shape tests

```yaml
depends_on: ["2.1"]
parallel: true
files: ["tests/test_api.py"]
estimated_minutes: 15
```

- [ ] Add tests importing `get_observability_contract` from `__init__.py`.
- [ ] Assert the helper returns a `dict` and `json.dumps(contract)` succeeds.
- [ ] Assert top-level sections include `contract`, `compatibility`, `status_snapshot`, `api`, `websocket`, and `prometheus`.
- [ ] Assert contract metadata includes `contract_version` and plugin metadata matching `plugin.yaml`.
- [ ] Assert `status_snapshot.fields` includes `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `updated_at`, `updated_monotonic`, and `session_id` with representative type/unit/freshness metadata.
- [ ] Assert `api` metadata covers `get_tps_stats` and representative fields without changing the live return value tested by existing tests.
- [ ] Assert absent optional surfaces are represented explicitly when their modules are absent, rather than causing imports or failures.

### 3.2 Add optional route tests only if route layer exists

```yaml
depends_on: ["2.2"]
parallel: true
files: ["tests/test_api.py", "api.py (if present)"]
estimated_minutes: 10
```

- [ ] If a REST route was added, test the route through the existing test client or route function pattern used by this repo.
- [ ] Assert the endpoint status is successful and the JSON body contains the same required sections as `get_observability_contract()`.
- [ ] If no route layer exists, do not invent a test client; instead assert the contract metadata documents `api.routes.observability_contract.available` as false or helper-only.

### 3.3 Run compatibility-focused existing tests

```yaml
depends_on: ["3.1", "3.2"]
parallel: false
files: ["tests/test_api.py", "tests/test_hook.py", "tests/test_session_tps.py", "tests/test_thread_safety.py"]
estimated_minutes: 10
```

- [ ] Run `pytest tests/test_api.py tests/test_hook.py tests/test_session_tps.py tests/test_thread_safety.py`.
- [ ] Existing assertions for `get_tps_stats`, `_on_post_api_request`, snapshot freshness, session stats, and thread safety must pass unchanged.
- [ ] If a failure reveals current test assumptions, fix the additive implementation rather than weakening existing backward-compatibility tests.

## 4. Documentation

### 4.1 Document the observability contract in README

```yaml
depends_on: ["2.1"]
parallel: true
files: ["README.md"]
estimated_minutes: 10
```

- [ ] Add a concise `Observability Contract` section near the API/status-bar documentation.
- [ ] Show Python helper usage: `from tps_counter import get_observability_contract` or the repo's import convention.
- [ ] If a route exists, document `/api/v1/observability/contract`; if no route exists, explicitly document helper-only availability for the current branch.
- [ ] Explain contract versioning: consumers should treat unknown fields as additive, validate required sections by contract version, and avoid failing on extra metadata.
- [ ] Include Prometheus label-cardinality guidance even if metrics are absent: avoid unbounded labels and treat high-cardinality dimensions as opt-in/unsafe unless the contract marks them bounded.

### 4.2 Final compatibility review

```yaml
depends_on: ["3.3", "4.1"]
parallel: false
files: ["__init__.py", "README.md", "tests/test_api.py"]
estimated_minutes: 5
```

- [ ] Review the diff and confirm no existing public response/schema fields were renamed or removed.
- [ ] Confirm no optional dependencies were introduced for contract generation.
- [ ] Confirm no new background work, session scans, SQLite queries, timers, or plugin state mutation occur when reading the contract.

## 5. Verification

### 5.1 Full code verification for `/ship`

```yaml
depends_on: ["4.2"]
parallel: false
estimated_minutes: 5
```

- [ ] `pytest tests/test_api.py tests/test_hook.py tests/test_session_tps.py tests/test_thread_safety.py`
- [ ] `python3 - <<'PY'` smoke check imports `get_observability_contract`, serializes it with `json.dumps`, and asserts required top-level sections.

### 5.2 Bead hygiene verification

```yaml
depends_on: ["5.1"]
parallel: false
estimated_minutes: 5
```

- [ ] `br lint her-feat-observability-contract-bq6 --json`
- [ ] `bv --robot-suggest`
- [ ] `br dep cycles --blocking-only --json`
- [ ] `br sync --flush-only`

## Wave Summary

- **Wave 1:** Tasks 1.1 and 1.2 can run together after PRD review; both are read-only discovery/design.
- **Wave 2:** Task 2.1 is the core helper. Task 2.2 is conditional and must not run unless an API route layer exists.
- **Wave 3:** Tasks 3.1 and 3.2 can run in parallel after Wave 2; Task 3.3 serializes compatibility testing.
- **Wave 4:** README documentation can proceed after helper shape is stable; final review waits on tests and docs.
- **Wave 5:** Verification and bead hygiene are serial final gates.
