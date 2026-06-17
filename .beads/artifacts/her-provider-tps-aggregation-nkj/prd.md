# PRD: Provider-Level TPS Aggregation

## Problem

The TPS counter tracks per-session and per-call metrics, and there's a pending bead for per-model tracking. However, users who use multiple providers (e.g., OpenAI for fast tasks, Anthropic for complex ones, custom/local for privacy) have no way to compare throughput across providers. The answer to "which provider is fastest for my workload?" requires manual calculation.

This matters because provider choice directly affects user experience — a 2x TPS difference means 2x faster responses. Without aggregated provider stats, users can't make data-driven routing decisions.

## Scope

**In scope:**
- Extract provider name from hook kwargs (the `model` field contains provider prefixes like `openai/gpt-4o`, `anthropic/claude-sonnet-4`)
- Maintain per-provider aggregate stats: avg TPS, peak TPS, call count, total tokens, total duration
- Expose via `get_provider_stats()` API function
- Optionally expose per-provider data in the status bar snapshot for future display

**Out of scope:**
- Per-model tracking (covered by `her-her-per-model-tps-tracking-h6f`)
- Provider-resilient parsing (covered by `her-her-provider-usage-parsing-rcz`)
- Cost tracking or pricing
- UI/visualization beyond API exposure

## Requirements

1. **Provider extraction**: Parse provider from model string (e.g., `openai/gpt-4o` → `openai`, `anthropic/claude-sonnet-4` → `anthropic`). Models without `/` prefix get `"default"` as provider.
2. **Per-provider stats**: Track avg_tps, peak_tps, call_count, total_output_tokens, total_duration per provider.
3. **Thread-safe**: Use existing `_STATE_LOCK` pattern.
4. **API function**: `get_provider_stats(session_id)` returns dict of provider → stats.
5. **Session snapshot integration**: Include per-provider breakdown in `_tps_snapshot` dict (key: `"providers"`).
6. **Memory bounded**: Same LRU eviction policy as session cleanup (link to `her-session-lifecycle-cleanup-ot1`).

## Approach

1. Add `_ProviderTPS` dataclass (similar to `_SessionTPS` but aggregated)
2. Add `_PROVIDERS: Dict[str, Dict[str, _ProviderTPS]]` mapping session_id → provider → stats
3. In `_on_post_api_request`, extract provider from `kwargs["model"]`, update provider stats alongside session stats
4. Add `get_provider_stats(session_id)` public API
5. Inject `providers` key into `_tps_snapshot` dict
