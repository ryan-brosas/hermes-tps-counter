---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-privacy-redaction-pis

## Task Metadata

```yaml
id: "her-privacy-redaction-pis"
depends_on: []
parallel: partially
conflicts_with:
  - "tasks touching __init__.py"
  - "tasks changing _tps_snapshot public keys"
  - "tasks changing observability contract schema"
  - "tasks changing README status snapshot/session mismatch guidance"
files:
  - "__init__.py"
  - "README.md"
  - "tests/test_hook.py"
  - "tests/test_api.py"
  - "tests/test_privacy.py (optional if clearer than extending existing tests)"
  - "config.py (optional lightweight local helper/config module)"
  - "api.py (only if present on implementation branch)"
  - "dashboard.py (only if present on implementation branch)"
  - "prometheus_metrics.py (only if present on implementation branch)"
  - "store.py (only if present and exposing exports on implementation branch)"
estimated_minutes: 85
```

## 1. Setup and Surface Inventory

### 1.1 Re-check branch files and outbound surfaces

```yaml
depends_on: []
parallel: true
files: ["__init__.py", "README.md", "tests/", "api.py (if present)", "dashboard.py (if present)", "prometheus_metrics.py (if present)", "store.py (if present)"]
estimated_minutes: 10
```

- [ ] Confirm actual implementation files before editing. Current plan-phase inspection found `__init__.py`, `README.md`, `tests/test_hook.py`, and `tests/test_api.py` as active surfaces; optional `api.py`, dashboard, WebSocket, Prometheus, and export modules should be re-checked in `/ship` because branch state may change.
- [ ] Map trusted state versus outbound data: `_SESSIONS` and `_get_session(session_id)` require raw `session_id`; `agent._tps_snapshot`, debug log messages, `get_tps_stats` output, observability contract metadata, docs, and any optional payload/label/export surfaces are outbound.
- [ ] Record current compatibility expectations from tests: `tests/test_hook.py` asserts raw `snapshot["session_id"]` in default mode; `tests/test_api.py` asserts contract sections, `get_tps_stats` behavior, and absent optional surfaces.
- [ ] Treat `__init__.py` as the hot coordination file even though `bv --robot-file-hotspots` reports no hotspots, because it owns state, hook path, helper API, contract, and logging.

### 1.2 Define privacy modes and field-treatment matrix

```yaml
depends_on: []
parallel: true
files: ["__init__.py", "README.md", "tests/test_api.py"]
estimated_minutes: 10
```

- [ ] Define disabled/default-compatible mode as the default unless a repo convention or PRD implementation choice explicitly names a configuration source. In this mode, current raw values and field names must be preserved.
- [ ] Define enabled behavior for covered fields: `session_id`, `model`, `provider`, and future configured identifier-like fields. Default enabled treatment should support deterministic pseudonymization where grouping is useful; allow redaction/omission by field where needed.
- [ ] Decide configuration input names and safe defaults. Keep them dependency-free and compatible with plugin loading; likely candidates are environment variables, a lightweight local config helper, or function-level policy construction. Never expose salt/secret values through diagnostics.
- [ ] Define per-field contract metadata values: `raw`, `pseudonymized`, `redacted`, `omitted`, plus a no-secret active mode indicator.
- [ ] Decide pseudonym format, such as a stable prefix plus truncated HMAC digest. The output must not contain raw substrings and must be bounded in length for hook-path safety.

## 2. Core Implementation

### 2.1 Add the shared redaction policy/helper

```yaml
depends_on: ["1.1", "1.2"]
parallel: false
files: ["__init__.py", "config.py (optional)"]
estimated_minutes: 20
```

- [ ] Implement a single helper/policy path used by all outbound surfaces. Keep it small enough to audit and either colocated in `__init__.py` or in a dependency-free local module such as `config.py` if separation improves clarity.
- [ ] Use only Python standard-library primitives, likely `hashlib`/`hmac`, `os`, and `typing`. Do not add packages, background workers, network calls, storage, or imports from optional web/metrics stacks.
- [ ] Preserve raw input semantics: raw `session_id` must continue to key `_SESSIONS`, and callers must still pass raw `session_id` to `get_tps_stats(session_id)` for lookup.
- [ ] Provide helper entry points for redacting one field/value and a mapping/nested outbound payload. Include behavior for unknown identifier-like future fields via configured field set or field-treatment mapping.
- [ ] Ensure disabled mode returns values exactly as before for covered fields. Ensure enabled pseudonym mode is deterministic for the same configured scope/salt and distinct for different raw values.
- [ ] Ensure policy diagnostics expose only safe values: active mode, covered fields, treatment names, digest algorithm/prefix if needed, and never salt/secret/reversible material.

### 2.2 Apply policy to current hook outbound data and logs

```yaml
depends_on: ["2.1"]
parallel: false
files: ["__init__.py", "tests/test_hook.py"]
estimated_minutes: 15
```

- [ ] Keep `_on_post_api_request` reading raw `session_id` from kwargs and using it for `_get_session(session_id)` exactly as today.
- [ ] Apply the shared helper immediately before writing `agent._tps_snapshot`, so enabled mode transforms covered identifiers and disabled mode leaves `session_id` raw.
- [ ] If model/provider values are available in hook kwargs or future snapshot metadata, route those fields through the same helper before snapshot exposure. Do not invent new public raw fields solely for this bead.
- [ ] Replace the debug log's raw `session_id[:8]` exposure with helper-treated output in enabled mode while preserving useful debug diagnostics and disabled-mode compatibility.
- [ ] Keep numeric TPS fields unchanged: `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `updated_at`, and `updated_monotonic` must not be redacted or recalculated differently.

### 2.3 Apply policy to public helper/contract metadata

```yaml
depends_on: ["2.1"]
parallel: false
files: ["__init__.py", "tests/test_api.py"]
estimated_minutes: 15
```

- [ ] Keep `get_tps_stats(session_id)` backward compatible. It currently does not echo `session_id`; if implementation adds any identifier fields or diagnostics, they must be helper-treated.
- [ ] Update `get_observability_contract()` with additive privacy metadata: active/default mode, configuration-safe diagnostics, covered fields, per-field treatments, deterministic grouping guarantees, and no-secret caveats.
- [ ] Update the existing `status_snapshot.fields.session_id` description so disabled mode is raw-compatible and enabled mode is pseudonymized/redacted/omitted according to policy.
- [ ] Keep the contract static/cheap and JSON-compatible. Reading it must not inspect live sessions, mutate `_SESSIONS`, read secret values into output, or import optional dependencies.
- [ ] Preserve current top-level contract sections and optional surface availability flags so existing `tests/test_api.py` expectations remain compatible with additive changes.

### 2.4 Apply policy to optional current/future surfaces only if present

```yaml
depends_on: ["2.1", "1.1"]
parallel: true
files: ["api.py (if present)", "dashboard.py (if present)", "prometheus_metrics.py (if present)", "store.py (if present)", "tests/"]
estimated_minutes: 10
```

- [ ] If `api.py` or a REST route module exists, ensure route payloads use the shared helper for covered identifiers. Do not implement a new REST API for this bead if none exists.
- [ ] If WebSocket/event streaming code exists, ensure event payloads use the shared helper. Do not add a WebSocket stream if absent.
- [ ] If `prometheus_metrics.py` exists, ensure labels do not expose raw covered identifiers in enabled mode and consider omission/coarse treatment for high-cardinality labels. Do not add a metrics exporter if absent.
- [ ] If dashboard JSON or historical export/store code exists, ensure outbound JSON/exports use the shared helper. Do not implement a dashboard/export endpoint if absent.
- [ ] If optional surfaces are absent, leave contract metadata truthful: mark them unavailable and document privacy policy as future-surface guidance only.

## 3. Testing

### 3.1 Test disabled/default-compatible behavior

```yaml
depends_on: ["2.2", "2.3"]
parallel: true
files: ["tests/test_hook.py", "tests/test_api.py", "tests/test_privacy.py (optional)"]
estimated_minutes: 10
```

- [ ] Assert default/disabled mode preserves current `_tps_snapshot["session_id"]` raw value and field names.
- [ ] Assert `get_tps_stats(session_id)` lookup and response remain unchanged for missing and existing sessions.
- [ ] Assert `register(ctx)` still registers only the `post_api_request` hook and does not add privacy setup side effects requiring external services.
- [ ] Assert existing contract tests still pass with additive privacy metadata.

### 3.2 Test deterministic pseudonyms and secret safety

```yaml
depends_on: ["2.1"]
parallel: true
files: ["tests/test_api.py", "tests/test_privacy.py (optional)"]
estimated_minutes: 10
```

- [ ] Assert the same raw field/value with the same configured scope/salt maps to the same pseudonym across calls.
- [ ] Assert different raw values produce different pseudonyms suitable for grouping.
- [ ] Assert pseudonyms do not contain raw source substrings such as the original `session_id`, `model`, or `provider`.
- [ ] Assert changing salt/scope changes pseudonyms if that is part of the selected policy design.
- [ ] Assert diagnostics/contract/payload output never includes the configured salt/secret value.

### 3.3 Test enabled outbound no-leak coverage

```yaml
depends_on: ["2.2", "2.3", "2.4"]
parallel: true
files: ["tests/test_hook.py", "tests/test_api.py", "tests/test_privacy.py (optional)"]
estimated_minutes: 15
```

- [ ] Enable privacy mode in the test-controlled configuration and call `_on_post_api_request` with obvious raw values such as `session_id="raw-session-secret"`, `model="raw-model-name"`, and `provider="raw-provider-name"` when the hook accepts them.
- [ ] Assert status snapshot outbound fields do not contain raw covered values in enabled mode while numeric TPS values remain unchanged.
- [ ] Capture debug logs and assert raw covered values, including the old raw prefix pattern, are not emitted in enabled mode.
- [ ] Assert `get_observability_contract()` privacy metadata describes treatment without raw sample identifiers or secret material.
- [ ] If optional route/dashboard/prometheus/export surfaces exist, add focused assertions for those payloads/labels/exports. If absent, assert their contract availability remains false and no nonexistent surface is promised.

### 3.4 Run compatibility-focused test selection

```yaml
depends_on: ["3.1", "3.2", "3.3"]
parallel: false
files: ["tests/test_api.py", "tests/test_hook.py"]
estimated_minutes: 5
```

- [ ] Run `pytest tests/test_api.py tests/test_hook.py`.
- [ ] If additional existing tests are present and relevant to touched modules, include them in the `/ship` verification run, especially session/thread-safety or optional surface tests.
- [ ] Fix implementation compatibility issues rather than weakening existing tests that assert disabled-mode behavior.

## 4. Documentation

### 4.1 Update README privacy and migration guidance

```yaml
depends_on: ["2.3"]
parallel: true
files: ["README.md"]
estimated_minutes: 10
```

- [ ] Add or update a privacy/redaction section near Status Bar Integration, API, or Observability Contract docs.
- [ ] Document default disabled/raw-compatible mode and enabled privacy mode without showing real secrets or reversible examples.
- [ ] List covered fields: `session_id`, `model`, `provider`, and configured future identifier-like fields.
- [ ] Explain per-field treatment values and deterministic grouping guarantees: same configured scope/salt gives stable pseudonyms; raw values cannot be recovered from output.
- [ ] Explain migration for consumers that compare `snapshot["session_id"]`: disabled mode preserves raw comparisons; enabled mode requires comparing the same treated value or using a policy-aware active-session treatment.
- [ ] Keep existing stale/session-mismatch guidance intact and update it only where privacy mode changes comparison semantics.
- [ ] Reiterate Prometheus cardinality guidance for future labels and explain omission/coarse redaction when labels would be high cardinality.

### 4.2 Final implementation review before verification

```yaml
depends_on: ["3.4", "4.1"]
parallel: false
files: ["__init__.py", "README.md", "tests/"]
estimated_minutes: 5
```

- [ ] Review the diff and confirm all outbound identifier handling flows through the shared helper.
- [ ] Confirm raw identifiers remain available only inside trusted state and lookup inputs.
- [ ] Confirm no salt/secret appears in examples, diagnostics, logs, contract output, or tests snapshots.
- [ ] Confirm no new optional dependencies, background workers, route servers, dashboards, Prometheus exporters, or export endpoints were created outside the PRD scope.
- [ ] Confirm contract changes are additive and do not overstate unavailable surfaces.

## 5. Verification

### 5.1 Full code verification for `/ship`

```yaml
depends_on: ["4.2"]
parallel: false
estimated_minutes: 5
```

- [ ] `pytest tests/test_api.py tests/test_hook.py`
- [ ] If new `tests/test_privacy.py` exists, include it: `pytest tests/test_privacy.py tests/test_api.py tests/test_hook.py`.
- [ ] Run a Python smoke check that serializes `get_observability_contract()` with `json.dumps`, confirms privacy metadata exists, and confirms no test salt/secret appears in the serialized contract.
- [ ] Run a helper-level smoke check for disabled raw compatibility and enabled deterministic non-raw pseudonyms, adapted to the final helper/API names selected during `/ship`.

### 5.2 Bead hygiene verification

```yaml
depends_on: ["5.1"]
parallel: false
estimated_minutes: 5
```

- [ ] `br lint her-privacy-redaction-pis --json`
- [ ] `bv --robot-suggest`
- [ ] `br dep cycles --blocking-only --json`
- [ ] `br sync --flush-only`

## Wave Summary

- **Wave 1:** Tasks 1.1 and 1.2 are read/design tasks and can run in parallel after PRD review.
- **Wave 2:** Task 2.1 is the core shared policy and must happen before any surface integration. Tasks 2.2 and 2.3 both touch `__init__.py`, so they should be coordinated serially even though they cover different concerns. Task 2.4 is conditional and can proceed only for optional modules that actually exist.
- **Wave 3:** Tasks 3.1, 3.2, and 3.3 can be developed in parallel after the core policy and surface hooks stabilize, but final test execution in 3.4 is serial.
- **Wave 4:** README work can proceed after contract/policy semantics are stable; final review waits on tests and docs.
- **Wave 5:** Code verification and bead hygiene are serial final gates.
