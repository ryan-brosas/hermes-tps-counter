---
purpose: Task decomposition with dependency tracking
updated: 2026-06-17
---

# Tasks: her-chore-docs-quickstart-sj2

## Task Metadata

```yaml
bead_id: "her-chore-docs-quickstart-sj2"
repo: "/home/ryan/repos/hermes-tps-counter"
implementation_scope: "documentation-only"
primary_file: "README.md"
estimated_minutes: 52
parallel_tracks_from_graph:
  - track-A: ["her-chore-docs-quickstart-sj2"]
  - track-B: ["her-feat-batch-session-stats-ojy"]
file_hotspots: []
```

## 1. Setup and Source-of-Truth Review

### 1.1 Confirm implementation contract and README gaps

```yaml
id: "1.1"
depends_on: []
parallel: false
conflicts_with: []
files: ["README.md", "plugin.yaml", "__init__.py", "tests/test_api.py", "tests/test_privacy.py"]
estimated_minutes: 8
wave: 1
```

- [ ] Read the current `README.md` and identify where to place or reorganize quickstart, status-bar, observability/privacy, and troubleshooting content.
- [ ] Cross-check source-of-truth metadata: `plugin.yaml` has `name: tps-counter`, version `1.0.0`, and hook `post_api_request`.
- [ ] Cross-check `_on_post_api_request` and `get_observability_contract()` for exact snapshot fields, helper names, optional surface availability, and freshness guidance.
- [ ] Cross-check tests for documented expectations: absent optional surfaces, snapshot field names, zero stats for missing sessions, and secret-safe privacy diagnostics.
- [ ] Do not edit code or run package manager/build/test commands.

## 2. README Documentation Update

### 2.1 Add concise install/restart/verify quickstart

```yaml
id: "2.1"
depends_on: ["1.1"]
parallel: false
conflicts_with: ["2.2", "2.3", "2.4"]
files: ["README.md"]
estimated_minutes: 10
wave: 2
requirements: [1, 6, 7]
```

- [ ] Replace or reorganize the existing install snippet into a short quickstart.
- [ ] Include a copy/install flow for placing the plugin into a Hermes plugins directory without implying a new installer or unsupported tooling.
- [ ] Include restart guidance and a basic verification step: after a Hermes LLM call, TPS should be observable via status integration or `get_tps_stats(session_id)` once the plugin is registered.
- [ ] Keep examples consistent with the repository layout and `plugin.yaml` metadata.

### 2.2 Clarify status-bar integration, snapshot fields, freshness, and session mismatch

```yaml
id: "2.2"
depends_on: ["1.1"]
parallel: false
conflicts_with: ["2.1", "2.3", "2.4"]
files: ["README.md"]
estimated_minutes: 12
wave: 2
requirements: [2, 3, 6, 7]
```

- [ ] Explain that the plugin injects latest TPS into `agent._tps_snapshot` on the active Hermes CLI agent after successful `post_api_request` hooks.
- [ ] Preserve/clarify required status-bar patch context: active CLI instance global, CLI startup registration, snapshot injection into status bar snapshot, and fragment rendering.
- [ ] Document snapshot fields accurately: `last_tps`, `avg_tps`, `peak_tps`, `output_tokens`, `updated_at`, `updated_monotonic`, `session_id`, plus optional `model` and `provider` when present.
- [ ] Include consumer behavior for positive and zero TPS values; zero/missing values should not render a misleading TPS label.
- [ ] State stale handling explicitly: compute age with `time.monotonic() - snapshot["updated_monotonic"]`; suppress or gray-out values beyond a consumer-defined threshold such as 30-120 seconds.
- [ ] State session-mismatch handling explicitly: ignore/reset display when `snapshot["session_id"]` does not match the active session, applying the same privacy treatment when privacy mode pseudonymizes session IDs.

### 2.3 Summarize observability surfaces and privacy behavior

```yaml
id: "2.3"
depends_on: ["1.1"]
parallel: false
conflicts_with: ["2.1", "2.2", "2.4"]
files: ["README.md"]
estimated_minutes: 10
wave: 2
requirements: [4, 6, 7]
```

- [ ] Make available surfaces obvious: `agent._tps_snapshot`, `get_tps_stats(session_id)`, `get_observability_contract()`, and `get_privacy_diagnostics()`/secret-safe diagnostics.
- [ ] Document `get_tps_stats(session_id)` response behavior using current field names: `calls`, `avg_tps`, `last_tps`, `peak_tps`, `total_output_tokens`, and `total_duration` for observed sessions; missing sessions return zero values without `total_duration`.
- [ ] Document that `get_observability_contract()` is the machine-readable in-process contract, static/dependency-free, and does not create session state.
- [ ] Explicitly state that REST observability route, WebSocket stream, and Prometheus exporter are unavailable on this branch when the contract marks them `available: false`.
- [ ] Summarize privacy env vars exactly: `HERMES_TPS_PRIVACY_MODE`, `HERMES_TPS_PRIVACY_SALT`, `HERMES_TPS_PRIVACY_SCOPE`, `HERMES_TPS_PRIVACY_FIELDS`, `HERMES_TPS_PRIVACY_TREATMENTS`.
- [ ] Note that salts/secrets and raw identifiers are not emitted by snapshots/logs/contracts/diagnostics when privacy mode is enabled.

### 2.4 Add practical troubleshooting section

```yaml
id: "2.4"
depends_on: ["1.1"]
parallel: false
conflicts_with: ["2.1", "2.2", "2.3"]
files: ["README.md"]
estimated_minutes: 10
wave: 2
requirements: [5, 6, 7]
```

- [ ] Add a concise symptom/cause/check/remediation table.
- [ ] Cover no TPS display: plugin not copied/enabled, Hermes not restarted, status-bar patch missing, no successful LLM call with output tokens/duration, active CLI instance missing.
- [ ] Cover stale TPS display: consumer not checking `updated_monotonic`, stale threshold too long, display not cleared when stale.
- [ ] Cover cross-session mismatch: `session_id` comparison missing or comparing raw active ID to a privacy-treated snapshot ID.
- [ ] Cover zero stats: unknown session, no successful calls recorded, `output_tokens <= 0`, or `api_duration <= 0`.
- [ ] Cover privacy-redacted identifiers: expected pseudonymized/redacted/omitted fields based on env vars; compare using same treatment policy.
- [ ] Cover absent optional REST/WebSocket/Prometheus surfaces: contract marks unavailable on this branch; use in-process helpers instead.
- [ ] Cover plugin registration failures: verify `plugin.yaml`, hook `post_api_request`, plugin location, restart, and logs.

## 3. Documentation Review and Verification

### 3.1 Check README against source files and acceptance criteria

```yaml
id: "3.1"
depends_on: ["2.1", "2.2", "2.3", "2.4"]
parallel: false
conflicts_with: []
files: ["README.md", "plugin.yaml", "__init__.py", "tests/test_api.py", "tests/test_privacy.py"]
estimated_minutes: 8
wave: 3
requirements: [1, 2, 3, 4, 5, 6]
```

- [ ] Inspect `README.md` for the five PRD success criteria: quickstart, status-bar/freshness/session mismatch, observability surfaces, troubleshooting guide, and docs-only change.
- [ ] Verify field names and env vars match `__init__.py` exactly.
- [ ] Verify plugin name/version/hook references match `plugin.yaml` exactly.
- [ ] Verify optional REST/WebSocket/Prometheus language matches tests and contract availability flags.
- [ ] Verify privacy guidance does not expose or encourage real secrets.

### 3.2 Confirm documentation-only blast radius and bead hygiene

```yaml
id: "3.2"
depends_on: ["3.1"]
parallel: false
conflicts_with: []
files: ["README.md", ".beads/artifacts/her-chore-docs-quickstart-sj2/plan.md", ".beads/artifacts/her-chore-docs-quickstart-sj2/tasks.md", ".beads/artifacts/her-chore-docs-quickstart-sj2/context-capsule.md"]
estimated_minutes: 4
wave: 3
requirements: [7]
```

- [ ] Inspect `git diff -- README.md` during `/ship` to ensure only README documentation changed for implementation.
- [ ] Inspect `git diff --name-only` during `/ship`; no plugin code, tests, package files, generated lockfiles, commits, PRs, or bead closure should appear.
- [ ] Run bead hygiene commands only: `br lint her-chore-docs-quickstart-sj2 --json`, `bv --robot-suggest`, `br dep cycles --blocking-only --json`, `br sync --flush-only`.
- [ ] Do not run `npm`, `pip`, `cargo`, package-manager installs, builds, or test suites unless a later plan revision explicitly authorizes them.

## Dependency Summary

| Task | Depends On | Can Run in Parallel? | Reason |
|------|------------|----------------------|--------|
| 1.1 | None | No | Establishes source of truth for all README edits. |
| 2.1 | 1.1 | No | Touches `README.md`; conflicts with other README edit tasks. |
| 2.2 | 1.1 | No | Touches `README.md`; needs source-of-truth review. |
| 2.3 | 1.1 | No | Touches `README.md`; must align with current code/tests. |
| 2.4 | 1.1 | No | Touches `README.md`; depends on all concepts but can be drafted after source review. |
| 3.1 | 2.1, 2.2, 2.3, 2.4 | No | Reviews completed README holistically. |
| 3.2 | 3.1 | No | Final hygiene and documentation-only blast-radius check. |

## Wave Summary

- **Wave 1:** Task 1.1, serial source-of-truth review.
- **Wave 2:** Tasks 2.1-2.4, conceptually sectioned but serialized in practice because all edit `README.md`.
- **Wave 3:** Tasks 3.1-3.2, serial documentation review and bead hygiene.

## Explicit Non-Tasks

- [ ] Do not implement plugin code, status-bar code, REST routes, WebSocket streams, Prometheus exporters, dashboards, alerts, or new tests.
- [ ] Do not change public API behavior, privacy policy, metric names, hook names, or status-bar rendering logic outside README examples.
- [ ] Do not run package managers, builds, commits, PR creation, or bead closure.
- [ ] Do not create a new bead.
