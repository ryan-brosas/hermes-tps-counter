# Solve Ledger: her-feat-observability-contract-bq6

- Claimed bead as daedalus after graph check showed no blockers and low impact.
- Verified implementation branch has no `api.py`, WebSocket module, or `prometheus_metrics.py`; optional surfaces are represented as unavailable.
- Added dependency-free `get_observability_contract()` helper in `__init__.py` with contract metadata, status snapshot schema, `get_tps_stats` schema, and optional REST/WebSocket/Prometheus availability metadata.
- Added focused contract tests in `tests/test_api.py` for JSON serializability, required sections, plugin metadata, representative fields, absent optional surfaces, and no session-state mutation.
- Updated README with helper usage, helper-only branch availability, contract versioning, unknown-field guidance, freshness/session mismatch guidance, and Prometheus label-cardinality guidance.
