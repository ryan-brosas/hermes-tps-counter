# hermes-tps-counter

## Goal
Hermes Agent plugin that tracks tokens-per-second (TPS) throughput and displays it in the status bar.

## Success Criteria
- Plugin hooks into `post_api_request` to capture output tokens and API duration after each LLM call
- Maintains per-session stats: last TPS, rolling average, peak TPS, total output tokens
- TPS data is injected into the Hermes status bar via `agent._tps_snapshot`
- Works out of the box with no configuration
- Status bar integration patches are documented and minimal

## Current State
- Plugin code is complete in `__init__.py` (169 lines)
- `plugin.yaml` declares `post_api_request` hook
- README documents install + 4 status bar patches needed in Hermes core
- No tests exist
- No `.pi/` template (just initialized)
- Not yet integrated into Hermes status bar (requires core patches)

## Scope
- In: TPS tracking, per-session stats, status bar integration, tests
- Out: Historical persistence across sessions, per-model breakdown, config options
