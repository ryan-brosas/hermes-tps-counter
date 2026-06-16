---
name: verification-before-completion
description: "Evidence before claims. No completion claims without fresh verification. Use before /verify, /ship, or any completion claim."
---

# Verification Before Completion

**Cognitive tool:** VERIFY — observe behavior, check against expected, report concrete evidence

**Core principle:** Evidence before claims, always. If you haven't run the verification command, you cannot claim it passes.

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

## The Gate Function

```
BEFORE claiming any status:
1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim
```

## Progressive Verification

| Session Activity | Minimum Verification |
|------------------|---------------------|
| 1-2 edits | Run the specific check |
| 3-5 edits | Quick verification |
| 6+ edits | Full verification |
| Before commit/push | Always full |

## Phantom Completion Detection

Scan modified files for stubs:

| Pattern | What It Indicates | Severity |
|---------|-------------------|----------|
| `return null` / `return {}` / `return []` | Empty implementation | HIGH |
| `TODO` / `FIXME` / `HACK` | Acknowledged incomplete | MEDIUM |
| `placeholder` / `stub` / `not implemented` | Self-documenting stubs | HIGH |
| `throw new Error("Not implemented")` | Explicit stub | HIGH |

## Three-Level Artifact Verification

| Level | Check | How |
|-------|-------|-----|
| **1: Exists** | File is present | `ls path/to/file` |
| **2: Substantive** | Not a stub | `grep -v "TODO\|FIXME\|return null" path/to/file` |
| **3: Wired** | Connected and used | `grep -r "import.*Name" src/` |

## Red Flags — STOP and Verify

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Done!")
- About to commit/push without verification
- Trusting agent success reports
- Relying on partial verification

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Agent said success" | Verify independently |

## Anti-Patterns

| Don't | Do Instead |
|-------|-----------|
| Claim "tests pass" without running them | Run the command, read the output, then claim |
| Run only typecheck, skipping tests | Run full verification stack |
| Say "it should work" | Run the command. If you haven't run it, you can't claim it passes |
| Wait for user to ask "did you check X?" | Verify proactively |
