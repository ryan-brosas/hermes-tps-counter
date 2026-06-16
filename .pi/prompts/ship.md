---
description: "Implement. Graph-informed — checks file history, impact, and related work before coding."
argument-hint: "<bead-id>"
---

## Resolve Bead ID

```bash
BEAD_ID=$(bash .pi/scripts/resolve-bead.sh "$1") || exit 1
```

Use `$BEAD_ID` (not `$BEAD_ID`) in all commands below.

## Prerequisites (CHECK FIRST)

Before doing ANYTHING, verify:
1. `.beads/artifacts/$BEAD_ID/plan.md` exists
2. `.beads/artifacts/$BEAD_ID/tasks.md` exists

If plan missing: STOP. Tell the user: "Run /plan first — no plan found for $BEAD_ID."
Do NOT proceed. Do NOT "helpfully" skip ahead.

You are implementing bead $BEAD_ID. Check the graph before coding. Load the **executing-plans** skill for wave execution protocol.

## Phase 1: Graph Check

```bash
bv --robot-triage              # Have priorities shifted?
bv --robot-alerts              # Any new blockers or stale issues?
bv --robot-related $BEAD_ID          # Related beads — don't duplicate work
bv --robot-impact $BEAD_ID           # Blast radius — what files will change
br show $BEAD_ID --json              # Bead details
br dep tree $BEAD_ID --json          # Dependencies
```

If priorities shifted or new blockers appeared, report before proceeding.

## Phase 2: File Context

Before editing any file, check its history:

```bash
bv --robot-file-beads <file>   # What tasks touched this file?
bv --robot-file-relations <file>  # What files co-change with this?
```

**Token efficiency:** For tasks touching >5 files, check only the 3 most critical files (by blast radius from `bv --robot-impact`) plus any hotspots (`bv --robot-file-hotspots`). Use `--format toon` for large bv result sets to reduce token usage ~40%.

This prevents:
- Reverting someone else's work
- Missing files that should co-change
- Breaking changes that depend on patterns in the file

## Phase 3: Claim

```bash
br update $BEAD_ID --claim --json
```

## Phase 4: Implement

Follow the plan in `.beads/artifacts/$BEAD_ID/plan.md`.

For each task:
1. Read context capsule (`.beads/artifacts/$BEAD_ID/context-capsule.md`)
2. Check file history (robot-file-beads, robot-file-relations)
3. Implement the change
4. Log to `.beads/artifacts/$BEAD_ID/solve-ledger.md`
5. Update progress.txt

## Phase 5: Verify

```bash
bv --robot-impact $BEAD_ID           # Compare actual changes against Phase 1 blast radius
Only re-query if changes seem unexpected. Reference Phase 1 result first.
br lint $BEAD_ID --json              # Lint changed files
```

Run project-specific verification (tests, build) before claiming complete. Load the **verification-before-completion** skill for the Iron Law.

## Phase 6: Complete

```bash
br update $BEAD_ID --notes "COMPLETED: <what was done>" --json
br close $BEAD_ID --reason "<specific proof>" --suggest-next --json
br sync --flush-only
```

`--suggest-next` returns newly unblocked work — chain it.

```
Bead: $BEAD_ID | Status: COMPLETED
Next: /verify $BEAD_ID
```

## Guardrails

- Always check file history before editing (robot-file-beads)
- Always check co-changing files (robot-file-relations)
- Always check blast radius (robot-impact)
- If graph check reveals priority shift, ask before proceeding
- Keep edits scoped to the bead
- For discovered work >2 min, ask before creating a bead
