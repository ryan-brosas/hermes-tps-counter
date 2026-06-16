---
name: br
description: "Task tracking backbone. br manages beads — create, claim, close, sync. For graph triage, load bv."
---

# br — Beads Task Tracker

Every piece of work flows through br beads. SQLite primary, JSONL for git sync. br never runs git.

For full command reference: `br --help`, `br capabilities --json`, or load `references/commands.md`.
For graph-aware triage: load the **bv** skill.

## Session Protocol

### Start

```bash
bv --robot-triage              # If bv installed — full triage in one call
br scheduler --json --limit 5  # Fallback — evidence-ranked ready work
br stale --json --days 3       # Neglected work
```

Inspect before claiming:

```bash
br show <id> --json            # Full context
br dep tree <id> --json        # What it depends on
```

### Claim

```bash
br update <id> --claim --actor "$AGENT_NAME" --json
```

`--claim` is atomic: assignee + status=in_progress. Never do separate updates.

### Work

- Keep edits scoped to the bead
- Log decisions with `--notes`
- Embed spawn-ready context with `--agent-context`
- Use `br comments add` for audit trail

### Complete

```bash
br close <id> --reason "<specific proof>" --suggest-next --json
br sync --flush-only
```

Always `--suggest-next` — it returns newly unblocked work.

## Decision Tree

```
Find next work            → br scheduler --json --limit 5
Quick-capture             → br q "title" -t task -p 2
Create with metadata      → br create "title" --type ... --priority ...
Inspect a bead            → br show <id> --json
Claim work                → br update <id> --claim --json
Check blocked             → br blocked --json --detailed
Defer work                → br defer <id> --until "+1h"
Reopen                    → br reopen <id> --reason "..."
Close + chain             → br close <id> --reason "..." --suggest-next --json
Check epic progress       → br epic status --json
Manage labels             → br label add <id> -l "label1,label2"
Lint workspace            → br lint --json
Graph analysis / triage   → load the bv skill
```

## Key Patterns

### Create

```bash
br create "title" --type task --priority 2 --slug my-slug --labels "domain,component" --json
```

Flags: `--type`, `--priority`, `--slug`, `--labels`, `--estimate`, `--parent`, `--deps "blocks:<id>"`, `--defer`, `--ephemeral`, `--dry-run`.

### Update

```bash
br update <id> --claim --json                    # Atomic claim
br update <id> --priority 0 --json               # Escalate
br update <id> --notes "COMPLETED: X" --json     # Notes survive compaction
br update <id> --add-label "urgent" --json       # Label
br update <id> --agent-context '{"obj":"..."}' --json  # Embed context
```

### Dependencies

```bash
br dep add <id> <depends-on-id> --json           # Add dependency
br dep tree <id> --format mermaid                 # Visualize
br dep cycles --blocking-only --json              # Find cycles
```

### Artifacts

Every bead gets `.beads/artifacts/<bead-id>/`: prd.md, prd.json, progress.txt, plan.md, solve-ledger.md, completion-evidence.json.

## Notes Format (Survives Compaction)

```
COMPLETED: [specific deliverables]
IN PROGRESS: [current state + what's working]
NEXT: [concrete next step]
BLOCKERS: [what's preventing progress]
KEY DECISIONS: [important context with rationale]
```

## Anti-Patterns

| Don't | Do Instead |
|-------|-----------|
| `br update <id> --status in_progress` | `br update <id> --claim --json` |
| Create without `br search` first | Always dedup |
| Close without completion-evidence.json | Write evidence first |
| Work on blocked beads | Use `br scheduler` — excludes blocked |
| `br sync` without `--flush-only` | Always `--flush-only` |
| Separate status + assignee | Use `--claim` (atomic) |
| Skip `br show` before mutate | Inspect first, always |

## Error Recovery

```bash
br doctor --repair              # Corrupted DB
br --allow-stale <command>      # Stale DB warning
br close <id> --bypass-policy --bypass-reason "reason" --json  # Bypass close policy
br reopen <id> --reason "..." --json  # Mistaken close
```
