# Solve Ledger: Session Lifecycle Cleanup

## Entry 1 — Problem Analysis
- **Observation:** `_SESSIONS` dict in `__init__.py` grows unboundedly. No hooks, no eviction, no TTL.
- **Impact:** Memory leak in long-running Hermes gateway processes.
- **Solution:** `on_session_end` hook + LRU eviction + session duration exposure.

## Entry 2 — Design Decision
- **Decision:** Belt-and-suspenders: hook for event-driven cleanup, LRU for safety net.
- **Tradeoff:** Slight complexity increase vs. guaranteed bounded memory.
- **Risk:** `on_session_end` may not have `session_id` in kwargs → LRU catches this.
