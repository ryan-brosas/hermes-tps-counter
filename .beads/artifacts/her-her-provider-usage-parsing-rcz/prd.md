# PRD: Provider-Resilient Usage Data Extraction

## Problem
Different LLM providers return usage data in different formats. OpenAI puts tokens under `usage.completion_tokens`, Anthropic uses `usage.output_tokens`, some providers nest it differently. The current hook uses a fixed key path and returns 0 when the format doesn't match, silently losing data.

## Scope
- Add fallback key path extraction for usage data
- Support OpenAI, Anthropic, Google, and generic formats
- Don't break existing working extractions

## Requirements
1. Try multiple key paths for output_tokens: `usage.output_tokens`, `usage.completion_tokens`, `usage.completionTokens`
2. Try multiple key paths for input_tokens: `usage.input_tokens`, `usage.prompt_tokens`, `usage.promptTokens`
3. Log at debug level when fallback path is used
4. Keep backward compatible — existing working paths still used first

## Approach
- Add `_extract_usage(usage_dict)` helper function
- Tries primary path, then fallbacks in order
- Returns (input_tokens, output_tokens) tuple
- Used in `_on_post_api_request` before `state.record()`

## Acceptance Criteria
- OpenAI format (`completion_tokens`) works
- Anthropic format (`output_tokens`) works
- Unknown format returns 0 (not crash)
- Existing behavior unchanged for currently-working providers
