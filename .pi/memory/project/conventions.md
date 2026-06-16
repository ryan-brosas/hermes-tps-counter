# Conventions

## Naming
- Plugin name: `tps-counter`
- Module name: `tps_counter` (underscore for imports)
- Class prefix: `_SessionTPS` (private, underscore-prefixed)
- Hook function: `_on_post_api_request`

## Code Style
- Python 3.11+ with `from __future__ import annotations`
- Type hints on all public functions
- `threading.Lock` for thread-safe state
- `logging` module for debug output
- `__slots__` for performance-critical classes

## Git Workflow
- Branch per bead via worktrees
- Commit at phase boundaries (create, ship, close)
- Prefix: `her` (her-001, her-002, ...)

## Testing
- pytest for unit tests
- Mock `post_api_request` hook calls
- Test thread safety with concurrent calls
