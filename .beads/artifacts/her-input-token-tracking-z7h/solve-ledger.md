# Solve Ledger: her-input-token-tracking-z7h

## Decisions
1. **Additive fields only** — New fields added to _SessionTPS without modifying existing ones. `record()` gets a new `input_tokens` parameter with default=0 for backward compat.
2. **TPS stays output-only** — TPS measures generation speed. Input tokens are consumed instantly (prompt processing), so mixing them into TPS would dilute the signal. We track input tokens for volume awareness, not speed.
3. **Same guard pattern** — input_tokens uses the same `if input_tokens <= 0: return` guard as output_tokens. Some providers may not report input tokens.
4. **total_tokens = input + output** — Computed property, not stored. Avoids sync issues.
5. **_tps_snapshot additive** — New keys added alongside existing ones. Status bar can optionally render input/total.

## Open Questions
- Should summary_line() show "in 5.2K" alongside "out 20.3K"? Or just total "25.5K"?
  → Show both input and output separately for clarity.
- Should turn_tps use total tokens or output-only?
  → Keep output-only for consistency with TPS meaning (generation speed).
