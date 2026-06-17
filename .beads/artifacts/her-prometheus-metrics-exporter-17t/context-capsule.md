---
purpose: Agent spawn context for implementation
updated: 2026-06-16
---

# Context Capsule: her-prometheus-metrics-exporter-17t

## Key Patterns

### Plugin architecture
- `__init__.py` is the main plugin module with `_on_post_api_request` hook
- `store.py` is the SQLite persistence layer (PersistentSessionStore)
- `api.py` is the FastAPI REST API (create_app factory)
- All modules use `from __future__ import annotations`
- Thread safety via `_STATE_LOCK = threading.Lock()` for all state mutations

### Hook pattern
```python
def _on_post_api_request(**kwargs):
    session_id = kwargs.get("session_id", "")
    usage = kwargs.get("usage", {})
    model = kwargs.get("model", "")
    # ... extract tokens, duration ...
    with _STATE_LOCK:
        state.record(output_tokens, duration, input_tokens)
        _persist_state(session_id, state)  # write-through to SQLite
        # per-model tracking
        # per-provider tracking
```

### FastAPI endpoint pattern
```python
@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # ... logic ...
    return HealthResponse(...)
```

### Test pattern
```python
@pytest.fixture(autouse=True)
def mock_hermes_cli():
    mod = types.ModuleType("hermes_cli")
    mod._ACTIVE_CLI_INSTANCE = None
    with patch.dict(sys.modules, {"hermes_cli": mod}):
        yield

@pytest.fixture
def store():
    from store import PersistentSessionStore
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = PersistentSessionStore(path)
    yield s
    s.close()
    try:
        os.unlink(path)
    except OSError:
        pass
```

## Key Constraints

- `prometheus_client` is OPTIONAL — import with try/except, graceful degradation
- Use custom `CollectorRegistry` to avoid global state conflicts
- Metric updates must be sub-millisecond (gauge.set is sub-microsecond in prometheus_client)
- Label cardinality bounded by MAX_SESSIONS (50) — acceptable
- Don't touch `.pi/`, `README.md`, `HERMES.md` (forbidden files)

## File Ownership

| File | Action | Owner |
|------|--------|-------|
| `prometheus_metrics.py` | CREATE | This bead |
| `__init__.py` | MODIFY | This bead (hook integration + config) |
| `api.py` | MODIFY | This bead (/metrics endpoint) |
| `tests/test_prometheus.py` | CREATE | This bead |
| `store.py` | READ ONLY | Reference for data patterns |
| `conftest.py` | READ ONLY | Reference for test fixtures |

## Decision Reference

- D1: Use `prometheus_client` library (not custom text format)
- D2: Custom `CollectorRegistry` (not global REGISTRY)
- D3: Mount on existing FastAPI app (not standalone server)
- D4: Optional dependency with try/except
- D5: Inline updates in hook (not background thread)
- D6: `tps_` prefix for all metric names

## Existing Code References

- `_extract_provider(model)` at __init__.py:~155 — extracts provider from "openai/gpt-4o"
- `_MODELS` dict at __init__.py:~75 — session_id → model_name → _ModelTPS
- `_PROVIDERS` dict at __init__.py:~76 — session_id → provider → _ProviderTPS
- `_evict_if_needed()` at __init__.py:~280 — LRU eviction for stale sessions
- `create_app(store)` at api.py:~60 — FastAPI app factory
