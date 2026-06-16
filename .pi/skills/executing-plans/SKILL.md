---
name: executing-plans
description: "Wave-based plan execution. Parallel within waves, sequential between waves. File ownership, verification at boundaries. Use with /ship."
---

# Executing Plans — Wave Execution Protocol

**Core principle:** Parallel within waves, sequential between waves, with explicit file ownership and verification at each boundary.

## When to Use

- A complete plan exists with task dependencies or wave assignments
- Work has 3+ tasks that can be file-disjoint

## When NOT to Use

- No plan exists
- All tasks are tightly sequential
- File ownership cannot be made explicit

## Step 1: Load Plan

1. Read `.beads/artifacts/<id>/plan.md` end-to-end
2. Extract each task's needs, creates, allowed files, verification
3. Check `bv --robot-impact <id>` for blast radius
4. Flag tasks that need unapproved changes

## Step 2: Build Dependency Waves

For each task:
- `needs`: prerequisite tasks
- `creates`: files, docs, tests, evidence
- `touches`: exact files the task may modify

**Rules:**
- Tasks in the same wave must NOT touch the same files
- If two tasks may edit the same file, serialize them
- Read-only work can run in parallel with other read-only work

## Step 3: Execute a Wave

### Single-task wave
Execute directly.

### Multi-task wave
Delegate with explicit file ownership. Every worker packet includes:

```
Task: [one concrete outcome]
Allowed files: [exact paths]
Forbidden files: [exact paths]
Verification: [command]
Return: result, verification, summary, blockers
```

## Step 4: Lead Verifies the Wave

After every wave:
1. Read changed files directly
2. Check worker responses against return contract
3. Confirm only planned files changed
4. Run verification for touched areas
5. Report blockers before next wave

**The lead verifies; worker self-report is not evidence.**

## Step 5: Chain to Next Wave

After verification passes, execute the next wave. After all waves complete, run full verification and proceed to Step 6. After review passes, chain to /verify.

## Step 6: Post-Ship Review

After all waves complete and verification passes, spawn an independent review before closing the bead.

### 6.1 Spawn Analyst Review

```
delegate(agent="analyst", task="""
You are reviewing bead <bead-id> before closure. Run a full quality review.

## Context

- PRD: .beads/artifacts/<bead-id>/prd.md
- Plan: .beads/artifacts/<bead-id>/plan.md
- Changed files: Run `git diff --name-only HEAD~1` to list

## Tasks

### 1. Reconcile (Spec↔Code Drift)

Read the PRD and extract verifiable claims (success criteria, functional requirements, affected files, scope boundaries).

For each claim, verify against the actual code:
- VERIFIED: Code confirms criterion met
- PARTIAL: Some evidence but incomplete
- MISSING: No code evidence found
- UNTESTABLE: Cannot verify via code

Detect drift patterns:
- Missing Feature: Success criterion with no code (HIGH)
- Partial Implementation: Criterion partially met (HIGH)
- Scope Creep: Files modified not in PRD (MEDIUM)
- Diverged Behavior: Code does different from spec (HIGH)

Calculate: Adherence = (VERIFIED×1.0 + PARTIAL×0.5) / (Total - UNTESTABLE) × 100

### 2. Verification Checks

Scan modified files for:
- Phantom stubs: return null, return {}, return [], TODO, FIXME, placeholder, "not implemented"
- Three-level verification: exists (file present), substantive (not a stub), wired (imported/used)

### 3. Output

Return your findings in this EXACT format:

REVIEW_VERDICT: [APPROVE|FIX GAPS|ITERATE|BLOCK]
ADHERENCE_SCORE: [N]%
DRIFT_FINDINGS: [count] findings
- [severity] [finding type]: [evidence]
PHANTOM_STUBS: [count] found
- [file]:[line] [pattern]
SUMMARY: [one-line summary for bead notes]
""")
```

### 6.2 Process Review Results

Parse the analyst's response using regex:
- `REVIEW_VERDICT: (\w+\s?\w*)` → verdict
- `ADHERENCE_SCORE: (\d+)%` → score
- `DRIFT_FINDINGS: (\d+)` → count
- Lines starting with `- [HIGH|MEDIUM|LOW]` → findings
- `PHANTOM_STUBS: (\d+)` → stub count
- `SUMMARY: (.+)` → summary line

Then:
1. Write `.beads/artifacts/<id>/review-report.md` from template (`.pi/templates/review-report.md`)
2. Write summary to bead notes: `br update <id> --notes "<summary>" --json`

### 6.3 Gate Decision

**Gate blocks if ANY of:**
- Adherence score < 70%
- Any HIGH severity drift findings (MISSING, PARTIAL, DIVERGED)
- Any phantom stubs detected
- Any Level 1 (exists) verification failure — file referenced in PRD but not present

**When gate blocks:**
1. Write findings to bead notes as BLOCKERS
2. Report findings to user
3. Agent must address findings before re-running review
4. After fixes, re-run Step 6

**When gate passes:**
1. Write approval to bead notes
2. Proceed to close

### 6.4 Bypass (--skip-review)

For emergencies only. Requires a reason:

```
--skip-review "reason: <explanation>"
```

**Bypass behavior:**
- Reason is logged to bead notes: `REVIEW SKIPPED: <reason>`
- Bypass is logged in review-report.md as `Verdict: BYPASSED — <reason>`
- No anonymous bypasses — reason is mandatory

## Approval-Gated Actions

Ask before: commits, pushes, merges, dependency changes, schema changes, destructive actions.

## Anti-Patterns

| Don't | Do Instead |
|-------|-----------|
| Parallel workers touching same file | Move one task to a later wave |
| Full-plan prompt to every worker | Give only the task packet |
| Worker commits independently | Worker reports; lead asks before state changes |
| Skip verification between waves | Verify before dependent work starts |
| Trust worker self-report | Lead reads files and runs checks |
