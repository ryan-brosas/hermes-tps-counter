---
description: "Wave-sequence into implementation plan. Graph-informed — uses bv for tracks, impact, forecasting, and capacity."
argument-hint: "<bead-id>"
---

## Resolve Bead ID

```bash
BEAD_ID=$(bash .pi/scripts/resolve-bead.sh "$1") || exit 1
```

Use `$BEAD_ID` (not `$1`) in all commands below.

## Prerequisites (CHECK FIRST)

Before doing ANYTHING, verify:
1. `.beads/artifacts/$BEAD_ID/prd.md` exists
2. PRD has all sections filled (Problem, Scope, Requirements, Approach, Success Criteria) — no placeholders

If PRD missing: STOP. Tell the user: "Run /create first — no PRD found for $BEAD_ID."
If PRD has placeholders: STOP. Tell the user: "PRD incomplete — run /create to fill all sections."
Do NOT proceed. Do NOT "helpfully" skip ahead.

You are planning implementation for bead $BEAD_ID. Use the graph to inform sequencing.

## Phase 1: Graph Context

```bash
bv --robot-plan                # Execution tracks — parallel-safe waves
bv --robot-insights            # Graph metrics — PageRank, critical path
bv --robot-impact $BEAD_ID           # Blast radius — what files will be affected
bv --robot-impact-network $BEAD_ID   # Full impact network
bv --robot-blocker-chain $BEAD_ID    # Why is this blocked? Full chain.
bv --robot-file-hotspots       # Riskiest files — touch with care
bv --robot-forecast $BEAD_ID         # ETA prediction
bv --robot-capacity            # Capacity simulation — how much can we handle
bv --robot-next                # Single top pick — is this still the right work?
br show $BEAD_ID --json              # Bead details
br dep tree $BEAD_ID --json          # Full dependency tree
```

From the graph:
- What tracks exist — group work into parallel waves
- What's the blast radius — which files will change
- What's the ETA — is this realistic for one session?
- What's the capacity — can we handle more work?

## Phase 2: Decompose

Break the work into tasks. For each task:
- What it does (1-2 sentences)
- Files it touches (check robot-file-hotspots for hot files)
- Dependencies (what must finish first)
- Can it run in parallel? (check robot-plan tracks)

## Phase 3: Wave-Sequence

Organize tasks into waves:

```
Wave 1 (parallel): tasks with no dependencies
Wave 2 (parallel): tasks that depend only on Wave 1
Wave N: tasks that depend on Wave N-1
```

Within a wave, tasks that touch different files can run in parallel.

## Phase 4: Write Plan

Write to `.beads/artifacts/$BEAD_ID/plan.md` (use template from `.pi/templates/plan.md`):

Include:
- Graph context (blast radius, unblocks, forecast)
- Observable truths
- Wave structure with tasks
- Delegation packets for /ship

Also write `.beads/artifacts/$BEAD_ID/tasks.md` (use template from `.pi/templates/tasks.md`) for detailed task decomposition with dependency tracking.

Also write `.beads/artifacts/$BEAD_ID/context-capsule.md` (use template from `.pi/templates/context-capsule.md`) — agent spawn context with key patterns, constraints, and file ownership for /ship.

## Phase 5: Verify

```bash
br lint $BEAD_ID --json
bv --robot-suggest             # Check for new issues
br dep cycles --blocking-only --json
br sync --flush-only
```

## Phase 6: Report

```
Plan: $BEAD_ID
Waves: <N> | Tasks: <N> | Parallel: <N>
Blast radius: <files>
Forecast: <ETA>
Next: /ship $BEAD_ID
```
