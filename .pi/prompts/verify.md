---
description: "Test + evidence. Graph-informed — checks completeness against impact, file history, and downstream effects."
argument-hint: "<bead-id>"
---

## Resolve Bead ID

```bash
BEAD_ID=$(bash .pi/scripts/resolve-bead.sh "$1") || exit 1
```

Use `$BEAD_ID` (not `$BEAD_ID`) in all commands below.

## Prerequisites (CHECK FIRST)

Before doing ANYTHING, verify:
1. Bead $BEAD_ID is claimed or completed (`br show $BEAD_ID --json`)

If bead not started: STOP. Tell the user: "Run /ship first — bead not started."
Do NOT proceed. Do NOT "helpfully" skip ahead.

You are verifying bead $BEAD_ID. Use the graph to check completeness. Load the **verification-before-completion** skill for evidence-before-claims protocol.

## Phase 1: Graph Context

```bash
bv --robot-triage              # Is this bead still relevant?
bv --robot-alerts              # Any alerts on this bead?
bv --robot-impact $BEAD_ID           # Blast radius — were all affected files covered?
bv --robot-impact-network $BEAD_ID   # Full impact network — downstream effects
bv --robot-blocker-chain $BEAD_ID    # Blocker chain — does this unblock anything?
br show $BEAD_ID --json              # Bead details
```

## Phase 2: File Coverage

Check that all files in the blast radius were actually changed:

```bash
bv --robot-impact $BEAD_ID           # Expected files
git diff --name-only           # Actual changed files
```

If blast radius includes files not changed, verify they were intentionally skipped.

## Phase 3: Run Verification

```bash
br lint $BEAD_ID --json                              # Lint the bead
bv --robot-suggest                             # Hygiene check
```

Then verify based on bead type:
- **Feature:** `npm test` / `cargo test` / `pytest` (whatever the project uses)
- **Bug:** reproduce the original symptom — it should now pass
- **Task:** build succeeds, lint clean
- **Chore:** specific verification per chore type

Run the actual commands. Do not claim pass without output.

## Phase 4: Write Completion Evidence

Populate the template below with actual values and write to `.beads/artifacts/$BEAD_ID/completion-evidence.json`:

```json
{
  "bead_id": "$BEAD_ID",
  "status": "verified",
  "timestamp": "<ISO timestamp>",
  "verification_commands": ["<commands run and their output>"],
  "requirements_met": { "<req>": "PASS/FAIL — <evidence>" },
  "blast_radius_covered": true/false,
  "files_changed": ["<list>"],
  "files_expected": ["<list from robot-impact>"]
}
```

## Phase 5: Check Downstream Impact

```bash
bv --robot-impact-network $BEAD_ID   # What's downstream?
bv --robot-capacity            # How does this affect capacity?
```

If this bead unblocks downstream work, note it in the report.

## Phase 6: Report

```
Bead: $BEAD_ID | Status: VERIFIED/FAILED
Evidence: .beads/artifacts/$BEAD_ID/completion-evidence.json
Blast radius: <files covered/total>
Unblocks: <list of downstream beads>
Next: /review $BEAD_ID (if verified) or fix issues (if failed)
```
