# Tech Stack

## Language
- Python 3.11+

## Dependencies
- None (stdlib only: logging, threading, time, typing)

## Plugin System
- Hermes Agent plugin architecture
- Hook: `post_api_request` (fired after each LLM API call)
- Entry point: `register(ctx)` function in `__init__.py`
- Config: `plugin.yaml` declares hooks

## Integration Points
- `hermes_cli._ACTIVE_CLI_INSTANCE` — global reference to CLI instance
- `agent._tps_snapshot` — dict injected on agent for status bar to read
- Status bar fragments in `cli.py` render the TPS label
