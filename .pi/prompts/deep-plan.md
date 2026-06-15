---
description: "TOKEN-BURN: scout + analyst enriched planning before writing a plan"
argument-hint: "<bead-id>"
---

# Deep Plan

**TOKEN-BURN WARNING:** This prompt intentionally uses extra sub-agent calls before planning. Use normal `/plan` for the lean default path. Use this for high-stakes, ambiguous, cross-cutting, or architecture-heavy work.

You are producing a normal implementation plan artifact, but with deeper reconnaissance and risk analysis first.

## Resolve Bead ID

```bash
BEAD_ID=$(bash .pi/scripts/resolve-bead.sh "$1") || exit 1
```

Use `$BEAD_ID` (not `$BEAD_ID`) in all commands below.

## Prerequisites (CHECK FIRST)

Before doing ANYTHING, verify:
1. `.beads/artifacts/$BEAD_ID/prd.md` exists
2. PRD has Problem, Scope, Requirements, Approach, and Success Criteria filled

If PRD missing: STOP. Tell the user: "Run /create first — no PRD found for $BEAD_ID."
If PRD incomplete: STOP. Tell the user: "PRD incomplete — run /create to fill all sections."
Do NOT proceed.

## Phase 1: Baseline Graph Context

```bash
bv --robot-plan
bv --robot-impact $BEAD_ID
bv --robot-impact-network $BEAD_ID
bv --robot-file-hotspots
bv --robot-forecast $BEAD_ID
br show $BEAD_ID --json
br dep tree $BEAD_ID --json
```

Summarize:
- Planned blast radius
- Blockers and downstream work
- Hot files
- Forecast and whether the task fits one session

## Phase 2: Parallel Deep Reconnaissance

Use `delegate(tasks=[...])` to burn tokens explicitly and gather independent perspectives.

```
delegate(tasks=[
  {
    agent: "scout",
    task: "Reconnoiter bead $BEAD_ID. Read the PRD and graph context. Identify relevant files, existing patterns, likely co-changing files, and unknowns. Return concise bullets with file paths and confidence. Do not edit files."
  },
  {
    agent: "analyst",
    task: "Analyze implementation risks for bead $BEAD_ID. Read the PRD and graph context. Identify top risks, sequencing constraints, acceptance criteria traps, and verification strategy. Do not edit files."
  }
])
```

Treat sub-agent output as advisory. Verify important claims with direct file reads or commands before including them in the final plan.

## Phase 3: Synthesize Plan

Use `.pi/templates/plan.md` as the output shape. Write:

- `.beads/artifacts/$BEAD_ID/plan.md`
- `.beads/artifacts/$BEAD_ID/tasks.md`
- `.beads/artifacts/$BEAD_ID/context-capsule.md`

The plan must include:
- Graph context
- Observable truths
- Wave structure
- File ownership
- Verification gates
- Delegation packets for `/ship`
- Explicit notes where scout/analyst disagreed or had low confidence

## Phase 4: Verify Artifacts

```bash
br lint $BEAD_ID --json
bv --robot-suggest
br dep cycles --blocking-only --json
ls .beads/artifacts/$BEAD_ID/plan.md .beads/artifacts/$BEAD_ID/tasks.md .beads/artifacts/$BEAD_ID/context-capsule.md
br sync --flush-only
```

## Phase 5: Report

```
Deep Plan: $BEAD_ID
Scout claims verified: <N verified / N total>
Analyst risks accepted: <N>
Waves: <N> | Tasks: <N> | Parallel: <N>
Forecast: <ETA>
Next: /ship $BEAD_ID
```
