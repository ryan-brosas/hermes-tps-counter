# Plan: Provider-Resilient Usage Data Extraction

## Wave 1 — Implementation (sequential, single file)

### Task 1.1: Add _extract_usage helper
- **File:** `__init__.py`
- **Action:** Add `_extract_usage(usage_dict)` function. Try output_tokens paths: `output_tokens`, `completion_tokens`, `completionTokens`. Try input_tokens paths: `input_tokens`, `prompt_tokens`, `promptTokens`. Return (input_tokens, output_tokens) tuple. Return (0, 0) for missing/invalid input.
- **Verification:** Unit test with OpenAI format, Anthropic format, empty dict, non-dict input
- **Parallel:** No
- **Depends on:** None

### Task 1.2: Wire into hook
- **File:** `__init__.py`
- **Action:** Replace direct `usage.get("output_tokens", 0)` in `_on_post_api_request` with `_extract_usage(usage)`.
- **Verification:** Hook still works with existing format
- **Parallel:** No
- **Depends on:** Task 1.1

### Task 1.3: Update input token tracking
- **File:** `__init__.py`
- **Action:** Use extracted input_tokens in `state.record()` call and `_tps_snapshot`.
- **Verification:** Input tokens tracked correctly
- **Parallel:** No
- **Depends on:** Task 1.2

## Wave 2 — Docs (sequential)

### Task 2.1: Update README
- **File:** `README.md`
- **Action:** Document supported provider formats.
- **Verification:** README lists supported formats
- **Parallel:** No
- **Depends on:** Task 1.3

## Dependencies
```
1.1 → 1.2 → 1.3 → 2.1
```
