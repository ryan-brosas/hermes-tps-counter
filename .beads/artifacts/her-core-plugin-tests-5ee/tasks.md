---
purpose: Task decomposition with dependency tracking
updated: 2026-06-16
---

# Tasks: her-core-plugin-tests-5ee

## Task Metadata

```yaml
id: "1"
depends_on: []
parallel: true
conflicts_with: []
files: ["tests/test_core.py"]
estimated_minutes: 15
```

## 1. Setup: Fixtures and Imports

### 1.1 Create test file with shared fixtures

```yaml
depends_on: []
parallel: false
files: ["tests/test_core.py"]
estimated_minutes: 15
```

- [ ] Create `tests/test_core.py` with imports and `mock_hermes_cli` autouse fixture
- [ ] Add `clean_state` autouse fixture that clears `_SESSIONS`, `_MODELS`, `_PROVIDERS` under `_STATE_LOCK`
- [ ] Add `temp_db` fixture using `tempfile.mkstemp` for persistence tests
- [ ] Add `mock_cli` fixture returning MagicMock with `.agent._tps_snapshot`

## 2. Core TPS Calculation

### 2.1 TestSessionTPS — record() and properties

```yaml
depends_on: ["1.1"]
parallel: true
files: ["tests/test_core.py"]
estimated_minutes: 15
```

- [ ] `test_record_single_call` — call_count, tokens, duration, TPS computed
- [ ] `test_record_multiple_calls` — accumulates correctly
- [ ] `test_avg_tps_returns_ratio` — total_output / total_duration
- [ ] `test_avg_tps_zero_duration` — returns 0.0
- [ ] `test_peak_tps_tracks_max` — highest TPS across calls
- [ ] `test_total_tokens_property` — input + output
- [ ] `test_turn_tps_after_reset` — reflects tokens since reset_turn()
- [ ] `test_turn_tps_zero_elapsed` — returns 0.0 when no time elapsed

### 2.2 TestSessionTPS — summary_line and _fmt_tokens

```yaml
depends_on: ["1.1"]
parallel: true
files: ["tests/test_core.py"]
estimated_minutes: 10
```

- [ ] `test_fmt_tokens_under_1000` — returns raw string
- [ ] `test_fmt_tokens_thousands` — returns "1.5K" format
- [ ] `test_fmt_tokens_millions` — returns "2.3M" format
- [ ] `test_summary_line_with_data` — contains "tok/s", "avg", "peak", "total"
- [ ] `test_summary_line_empty_session` — returns empty string

## 3. Per-Model and Public APIs

### 3.1 TestModelTPS and get_model_stats()

```yaml
depends_on: ["1.1"]
parallel: true
files: ["tests/test_core.py"]
estimated_minutes: 10
```

- [ ] `test_model_tps_record` — call_count, tokens, duration, avg_tps, peak_tps
- [ ] `test_get_model_stats_empty` — returns {} for unknown session
- [ ] `test_get_model_stats_multiple_models` — returns dict with 2+ model keys
- [ ] `test_get_model_stats_structure` — each model has avg_tps, peak_tps, calls, total_output_tokens, total_duration

### 3.2 TestGetTpsStats

```yaml
depends_on: ["1.1"]
parallel: true
files: ["tests/test_core.py"]
estimated_minutes: 5
```

- [ ] `test_get_tps_stats_unknown_session` — returns dict with zeros
- [ ] `test_get_tps_stats_with_data` — returns correct values
- [ ] `test_get_tps_stats_includes_session_duration` — has session_duration key

## 4. Session Lifecycle

### 4.1 TestGetSession — DB hydration

```yaml
depends_on: ["1.1"]
parallel: true
files: ["tests/test_core.py"]
estimated_minutes: 10
```

- [ ] `test_get_session_creates_new` — returns fresh _SessionTPS for unknown id
- [ ] `test_get_session_returns_cached` — returns same object on second call
- [ ] `test_get_session_hydrates_from_db` — loads from _STORE when not in memory

### 4.2 TestEviction

```yaml
depends_on: ["1.1"]
parallel: true
files: ["tests/test_core.py"]
estimated_minutes: 10
```

- [ ] `test_evict_noop_under_limit` — nothing evicted when count <= MAX_SESSIONS
- [ ] `test_evicts_oldest_session` — removes session with oldest turn_start_time
- [ ] `test_evict_cleans_models_and_providers` — removes associated model/provider state

### 4.3 TestSessionEnd

```yaml
depends_on: ["1.1"]
parallel: true
files: ["tests/test_core.py"]
estimated_minutes: 5
```

- [ ] `test_on_session_end_removes_state` — session gone from _SESSIONS, _MODELS, _PROVIDERS
- [ ] `test_on_session_end_no_session_id` — handles missing session_id gracefully

## 5. Status Bar and Persistence Integration

### 5.1 TestStatusBarSnapshot

```yaml
depends_on: ["1.1"]
parallel: true
files: ["tests/test_core.py"]
estimated_minutes: 10
```

- [ ] `test_snapshot_basic_fields` — last_tps, avg_tps, peak_tps, output_tokens, input_tokens, total_tokens
- [ ] `test_snapshot_includes_models` — models dict present when model data exists
- [ ] `test_snapshot_includes_providers` — providers dict present when provider data exists

### 5.2 TestPersistenceIntegration

```yaml
depends_on: ["1.1"]
parallel: true
files: ["tests/test_core.py"]
estimated_minutes: 10
```

- [ ] `test_persist_state_writes_to_store` — _persist_state calls store.save()
- [ ] `test_hydrate_from_db_loads_state` — _hydrate_from_db returns _SessionTPS with correct fields
- [ ] `test_hydrate_from_db_returns_none_when_absent` — returns None for unknown session

## 6. Final Verification

### 6.1 Full test suite passes

```yaml
depends_on: ["2.1", "2.2", "3.1", "3.2", "4.1", "4.2", "4.3", "5.1", "5.2"]
parallel: false
files: []
estimated_minutes: 5
```

- [ ] `pytest tests/test_core.py -v` — all new tests pass
- [ ] `pytest tests/ -v` — no existing tests regress
