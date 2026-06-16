---
description: "Lean code review. Graph-informed single-pass review for normal workflow."
argument-hint: "<bead-id or defaults to uncommitted>"
---

## Resolve Bead ID

```bash
BEAD_ID=$(bash .pi/scripts/resolve-bead.sh "$1") || exit 1
```

Use `$BEAD_ID` (not `$1`) in all commands below.

## Prerequisites (CHECK FIRST)

Before doing ANYTHING, verify:
1. `git diff HEAD~1` shows changes to review

If no changes: STOP. Tell the user: "No changes to review. Run /ship first."
Do NOT proceed. Do NOT "helpfully" skip ahead.

You are reviewing code in the default lean workflow. Use the graph to understand impact, but keep this pass single-agent and focused. Load the **reconcile** skill for spec↔code drift detection.

If the diff is security-sensitive, architectural, or too large for one focused pass, STOP after context gathering and suggest the explicit deep review prompt instead of doing hidden extra model calls.

## Phase 1: Lean Graph Context

```bash
bv --robot-impact ${1:-}       # Blast radius of this bead
bv --robot-related ${1:-}      # Related beads — context for review
br show ${1:-} --json          # Bead details
```

Use heavier graph commands only when the lightweight context reveals unusual risk:

```bash
bv --robot-impact-network ${1:-}  # Only for broad/multi-file changes
bv --robot-causality ${1:-}       # Only when cause/effect is unclear
bv --robot-insights               # Only when priority/centrality matters
```

## Phase 2: File Context

For changed production files, check history before judging the diff:

```bash
bv --robot-file-beads <file>      # What tasks touched this file?
bv --robot-file-relations <file>  # What files co-change with this?
```

**Token efficiency:** For diffs touching >10 files, check only:
- Files flagged by `bv --robot-file-hotspots`
- Files with the most bead history
- Files central to the stated acceptance criteria

Use `--format toon` for large bv output when supported. Skip per-file graph checks for generated files and obvious test-only changes unless they are the review target.

## Phase 3: Gather Diff

```bash
git diff HEAD~1 --stat
git diff HEAD~1
```

## Phase 4: Single-Pass Review

Review as the main agent. Focus on:

1. **Correctness** — logic errors, edge cases, contract violations
2. **Security** — injection, auth bypass, data exposure
3. **Performance** — algorithmic complexity, memory, blocking I/O
4. **Spec drift** — mismatch with PRD, plan, or acceptance criteria
5. **Workflow fit** — files outside blast radius or missing co-change files

Each finding must include: severity, title, file:line, evidence, confidence.

## Phase 5: Impact Verification

```bash
bv --robot-impact ${1:-}       # Were all blast-radius files addressed?
bv --robot-suggest             # Did this introduce new issues?
```

If the change affects files outside the blast radius, flag it.

## Phase 6: Verdict

```
VERDICT: APPROVE / REQUEST CHANGES / BLOCK

Findings:
- [Critical] ...
- [High] ...

Blast radius: <files covered/total>
File risk: <hotspots checked or skipped with reason>
Impact: <what this unblocks or affects>
Deep review needed: yes/no — <reason>
```
