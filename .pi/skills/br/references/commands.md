# br Command Reference

Full CLI surface for br (beads_rust). Load this when you need a specific flag or subcommand.

## Quick Capture

```bash
br q "fix login bug" -t bug -p 1                    # Create + print ID only
br q "add tests" -t task -l "testing" -e 30         # With labels + estimate
br q "epic: auth system" -t epic -p 1               # Create epic
```

## Create (Full)

```bash
br create "<title>" \
  --type <task|bug|feature|epic|chore> \
  --priority <0-4> \
  --slug <human-readable-id> \
  --description "<concise desc>" \
  --labels "<comma-separated>" \
  --estimate <minutes> \
  --parent <epic-id> \
  --deps "<type>:<id>,<type>:<id>" \
  --defer "+1d" \
  --ephemeral \
  --dry-run \
  --json
```

- `--slug`: human-readable ID like `pi-auth-fix-abc`
- `--deps`: inline dependency creation (`blocks:<id>`, `discovered-from:<id>`)
- `--defer`: schedule for later
- `--ephemeral`: not exported to JSONL
- `--dry-run`: preview without creating

## List & Search

```bash
br list --json                                      # All open issues
br list --status in_progress --assignee "agent-1" --json  # Filtered
br list --overdue --json                            # Overdue issues
br list --label "backend" --json                    # By label (AND)
br list --label-any "frontend,backend" --json       # By label (OR)
br list --format toon --stats                       # Token-efficient output
br list --fields "id,title,priority" --format csv   # Custom CSV fields

br search "auth" --json                             # Full-text search
br search "login" --status open --type bug --json   # Filtered search
```

## Show

```bash
br show <id> --json                                 # Full details + relations
br show <id1> <id2> --json                          # Multiple beads at once
```

## Update

```bash
br update <id> --claim --json                       # Atomic claim
br update <id> --status open --json                 # Change status
br update <id> --priority 0 --json                  # Escalate priority
br update <id> --notes "COMPLETED: X\nNEXT: Y" --json  # Update notes
br update <id> --add-label "urgent" --json          # Add label
br update <id> --remove-label "low-priority" --json # Remove label
br update <id> --set-labels "new1,new2" --json      # Replace all labels
br update <id> --agent-context '{"objective":"..."}' --json  # Embed context
br update <id> --agent-context @path/to/context.json --json  # From file
br update <id> --estimate 120 --json                # Update estimate
br update <id> --due "2025-01-15" --json            # Set due date
br update <id> --force --json                       # Force even if blocked
```

## Dependencies

```bash
br dep add <id> <depends-on-id> --json              # id depends on depends-on
br dep remove <id> <depends-on-id> --json           # Remove dependency
br dep list <id> --json                             # List deps for one issue
br dep tree <id> --json                             # Full dependency tree
br dep tree <id> --format mermaid                   # Mermaid diagram
br dep cycles --json                                # Detect circular deps
br dep cycles --blocking-only --json                # Only blocking cycles
```

## Epic Management

```bash
br epic status --json                               # All epics + progress
br epic close-eligible --json                       # Close epics with all children closed
```

## Labels

```bash
br label add <id> -l "label1,label2" --json         # Add labels
br label remove <id> -l "label1" --json             # Remove labels
br label list <id> --json                           # Labels for one issue
br label list-all --json                            # All unique labels + counts
br label rename "old" "new" --json                  # Rename across all issues
```

## Defer / Undefer

```bash
br defer <id> --until "+1h" --json                  # Defer for 1 hour
br defer <id> --until "tomorrow" --json              # Defer until tomorrow
br defer <id> --until "2025-01-15" --json            # Defer until date
br undefer <id> --json                              # Make ready again
```

Deferred issues don't appear in `br ready` or `br scheduler` until their defer date passes.

## Reopen

```bash
br reopen <id> --reason "Found regression" --json   # Reopen with reason
```

## Close

```bash
br close <id> --reason "<what was done + evidence>" --suggest-next --json
br close <id> --force --json                        # Close even if blocked
br close <id> --suggest-next --json                 # Show newly unblocked work
```

## Comments

```bash
br comments add <id> --author "agent" --message "Implemented auth module" --json
br comments list <id> --json                        # List all comments
```

## Coordination (Multi-Agent)

```bash
br coordination status --json                       # Stale claims diagnosis
```

## Audit Trail

```bash
br audit record --kind "llm_call" --issue-id <id> --model "gpt-4" --json
br audit record --kind "tool_call" --issue-id <id> --tool-name "grep" --json
br audit label <ENTRY_ID> --label "verified" --json
br audit log <id> --json                            # View audit log for issue
br audit summary --json                             # View audit summary
```

## Saved Queries

```bash
br query save "my-bugs" --status open --type bug --json
br query run "my-bugs" --json
br query list --json
br query delete "my-bugs" --json
```

## Lint

```bash
br lint --json                                      # Lint all open issues
br lint <id> --json                                 # Lint specific issue
br lint --type bug --json                           # Lint bugs only
```

## Changelog

```bash
br changelog --json                                 # All closed issues
br changelog --since "2025-01-01" --json             # Since date
br changelog --since-tag "v1.0" --json               # Since git tag
```

## Orphans

```bash
br orphans --json                                   # Issues in commits but open
br orphans --details --json                         # With commit info
```

## Graph & Stats

```bash
br graph --all --compact                            # Dependency graph
br dep tree <id> --format mermaid                   # Mermaid diagram (--format on graph is not supported)
br stats --json                                     # Project statistics
br stats --by-type --by-priority --json             # Grouped stats
br count --by status --json                         # Count by status
```

## Diagnostics

```bash
br doctor                                           # Health check
br doctor --repair                                  # Repair DB from JSONL
br info --json                                      # Workspace metadata
br where                                            # Active .beads path
br config list                                      # All config options
br config get <key>                                 # Get config value
br config set <key> <value>                         # Set config value
br capabilities --json                              # Machine-readable contracts
br schema commands --json                           # Per-command output shapes
br schema issue --json                              # Issue object schema
```

## Token Efficiency

```bash
br list --format toon --stats                       # TOON: ~40% fewer tokens than JSON
br list --format csv --fields "id,title,priority"   # CSV: minimal, custom fields
br scheduler --format toon --stats                  # Token-efficient scheduler
```

## Scheduler

```bash
br scheduler --json --limit 5                       # Evidence-ranked ready work
br scheduler --format toon --stats                  # Token-efficient scheduler
```

`br scheduler` uses evidence-ranked scoring: priority weighting, dependency satisfaction, staleness, fairness, domain contention. Prefer over `br ready`.

## Artifact Contract

Every bead gets `.beads/artifacts/<bead-id>/`:

| File | Phase | Purpose |
|------|-------|---------|
| prd.md | /create | Product requirements |
| prd.json | /create | Machine-readable breakdown |
| progress.txt | /create | Append-only progress log |
| plan.md | /plan | Wave-sequenced plan |
| context-capsule.md | /plan | Agent spawn instructions |
| decisions.md | /plan | Decision log |
| solve-ledger.md | /ship | Implementation log |
| completion-evidence.json | /verify | Verification evidence |
