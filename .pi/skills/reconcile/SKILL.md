---
name: reconcile
description: "Spec↔code drift detection. Compares PRD against implementation. Use after /ship or before closing a bead."
---

# Reconcile — Spec↔Code Drift Detection

**Cognitive tool:** VERIFY — confirm implementation matches specification, find drift

## When to Use

- After /ship completes all tasks, before closing the bead
- Before creating a PR to verify completeness
- When you suspect implementation has drifted from spec

## When NOT to Use

- During active implementation (wait until tasks are done)
- For code quality issues (use /review instead)

## Process

### Step 1: Load Artifacts

```bash
cat .beads/artifacts/<id>/prd.md
cat .beads/artifacts/<id>/plan.md 2>/dev/null
git diff <base> --name-only
bv --robot-impact <id>
```

### Step 2: Extract Spec Claims

From the PRD, extract verifiable claims:

| Claim Type | Source | Example |
|------------|--------|---------|
| Success Criteria | `## Success Criteria` | "User can see messages" |
| Functional Req | `## Requirements` | "WHEN X THEN Y" |
| Affected Files | `## Technical Context` | `src/api/users.ts` |
| Scope Boundaries | `## Scope` | "In: X, Out: Y" |
| Task Deliverables | `## Tasks` | Each task's end-state |

### Step 3: Verify Each Claim

| Status | Meaning | Evidence |
|--------|---------|----------|
| **VERIFIED** | Code confirms criterion met | Working code, tests pass |
| **PARTIAL** | Some evidence but incomplete | Stub, TODO, partial impl |
| **MISSING** | No code evidence found | No relevant files/functions |
| **UNTESTABLE** | Cannot verify via code | Needs manual check |

### Step 4: Detect Drift Patterns

| Drift Type | Detection | Severity |
|------------|-----------|----------|
| Missing Feature | Success criterion with no code | HIGH |
| Partial Implementation | Criterion partially met (stub) | HIGH |
| Scope Creep | Files modified not in PRD | MEDIUM |
| Over-Engineering | Code not traceable to PRD | LOW |
| Diverged Behavior | Code does different from WHEN/THEN | HIGH |

### Step 5: Calculate Drift Score

```
Adherence = (VERIFIED×1.0 + PARTIAL×0.5) / (Total - UNTESTABLE) × 100
```

| Score | Meaning | Action |
|-------|---------|--------|
| 90-100% | Excellent | Ready to close |
| 70-89% | Good with gaps | Fix or document deviations |
| 50-69% | Significant drift | Iterate to reconcile |
| <50% | Major drift | BLOCK — spec and code misaligned |

## Report Format

```
Reconciliation: <bead-id>
Adherence: [N]%
Scope Creep: [N]%

Success Criteria:
| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | ... | VERIFIED | src/file.ts:42 |
| 2 | ... | MISSING | No code evidence |

Verdict: [APPROVE / FIX GAPS / ITERATE / BLOCK]
```

## Anti-Patterns

| Don't | Do Instead |
|-------|-----------|
| Assume spec and code agree | Verify each claim against code |
| Fix mismatches without understanding cause | Investigate root cause first |
| Ignore partial matches | Handle partial overlaps explicitly |
