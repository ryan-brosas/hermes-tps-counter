---
purpose: Post-ship review output from analyst sub-agent
updated: [date]
---

# Review Report: [bead-id]

**Reviewed:** [timestamp]
**Agent:** analyst
**Verdict:** [APPROVE | FIX GAPS | ITERATE | BLOCK | BYPASSED]

## Summary

[One-line summary for bead notes injection]

## Reconcile: Spec↔Code Drift

**Adherence Score:** [N]%

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | [criterion from PRD] | [VERIFIED/PARTIAL/MISSING/UNTESTABLE] | [file:line or "No code evidence"] |

### Drift Findings

| Finding | Severity | Evidence |
|---------|----------|----------|
| [Missing Feature / Partial Implementation / Scope Creep / Diverged Behavior] | [HIGH/MEDIUM/LOW] | [specific evidence] |

## Verification: Completion Checks

### Phantom Stub Detection

| File | Pattern | Line | Severity |
|------|---------|------|----------|
| [path] | [return null / TODO / "not implemented"] | [N] | [HIGH/MEDIUM] |

### Three-Level Artifact Verification

| Artifact | Level 1: Exists | Level 2: Substantive | Level 3: Wired |
|----------|-----------------|---------------------|----------------|
| [name] | [✅/❌] | [✅/❌] | [✅/❌] |

## Gate Decision

- [ ] Adherence score ≥ 70%
- [ ] No HIGH severity drift findings
- [ ] No phantom stubs detected
- [ ] All artifacts pass three-level verification

**Gate:** [PASS | BLOCKED]

If BLOCKED: [What must be fixed before closure]

## Notes Injection

```
REVIEW [APPROVED/BLOCKED/BYPASSED]: Adherence [N]%, [M] drift findings, [P] phantom stubs. [Specific action needed or "Ready to close."]
```
