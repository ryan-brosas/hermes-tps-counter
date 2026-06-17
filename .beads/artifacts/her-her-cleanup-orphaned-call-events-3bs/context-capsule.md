---
purpose: Agent spawn context for a bead
updated: 2026-06-16
---

# Context Capsule: her-her-cleanup-orphaned-call-events-3bs

## Objective

Fix orphaned `call_events` rows by ensuring `store.delete()`, `store.delete_expired()`, and `_evict_if_needed()` all remove associated call_events when cleaning up a session.

## Key Patterns

- `store.delete()` pattern — Currently only deletes from `session_tps` via `_DELETE_ONE`. Must add a companion DELETE for `call_events`. Reference: `store.py:288-299`
- `_DELETE_ONE` SQL constant — Follow this pattern for the new `_DELETE_ONE_EVENT`. Reference: `store.py:58`
- `_evict_if_needed()` — Evicts from memory but never calls `_STORE.delete()`. Must add the DB cleanup call. Reference: `__init__.py:625-640`
- Lock scope — All DB operations in `store.py` use `with self._lock:`. New DELETEs must stay within this scope.

## Constraints

1. Do NOT add FOREIGN KEY constraints or change the schema
2. All DB operations must remain thread-safe (use existing `self._lock`)
3. Keep delete operations atomic — both DELETEs in `delete()` should be in the same transaction
4. Do not change any public API signatures

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Fix store.delete() | `store.py` — add SQL constant, modify delete() | `__init__.py`, tests |
| Fix store.delete_expired() | `store.py` — add SQL constant, modify delete_expired() | `__init__.py`, tests |
| Fix _evict_if_needed() | `__init__.py` — add _STORE.delete() call | `store.py`, tests |
| Tests | `tests/test_store_delete.py` — new test methods | `store.py`, `__init__.py` |

## Graph Context

- **Blast radius:** `store.py`, `__init__.py`, `tests/test_store_delete.py`
- **Related beads:** None (standalone bug fix)
- **File history:** `store.py` and `__init__.py` are actively maintained core files
