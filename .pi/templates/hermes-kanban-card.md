# Hermes Kanban Card Template

Use when creating kanban tasks for pi-core work. Copy into the kanban card body.

## Required Fields

- **title:** `[bead-id] — [task title]`
- **assignee:** [profile from hermes profile list]
- **workspace:** `worktree`
- **skill:** `beads-workflow`

## Body Template

### Bead

[bead ID from br]

### Goal

[What to accomplish — from PRD or plan]

### Artifacts

- PRD: `.beads/artifacts/<id>/prd.md`
- Plan: `.beads/artifacts/<id>/plan.md`
- Tasks: `.beads/artifacts/<id>/tasks.md`
- Context: `.beads/artifacts/<id>/context-capsule.md`

### Allowed Files

[From plan.md blast radius or task file ownership]

### Forbidden Files

- `.pi/extensions/*` (unless task explicitly modifies extensions)
- `.pi/agents/*` (unless task explicitly modifies agents)
- `.pi/settings.json` (unless task explicitly modifies settings)
- `~/.hermes/*` (never)
- `.env` (never)

### Verification

[From PRD acceptance criteria — specific commands]

### Completion Metadata

When done, pass this to kanban_complete:

```json
{
  "changed_files": ["<list of files changed>"],
  "tests_run": <number>,
  "tests_passed": <number>,
  "decisions": ["<any decisions made>"]
}
```

### Block Conditions

Block (don't complete) if:
- Tests regress
- Missing required artifacts
- Architecture decision needed
- Files outside allowed list were modified
