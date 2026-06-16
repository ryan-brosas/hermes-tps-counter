---
description: "Formalize work into a br bead + PRD. Graph-informed — uses bv for dedup, classification, and placement."
argument-hint: "[--worktree] <description of work>"
---

## Prerequisites (CHECK FIRST)

Before doing ANYTHING, verify:
1. User provided input ($@) describing what to build

If no input: STOP. Ask the user: "What are we building? Provide a description or run /brainstorm first."
Do NOT proceed. Do NOT "helpfully" skip ahead.

## Flag Parsing

Parse $@ for flags before proceeding:

```bash
# Extract --worktree flag and description
WORKTREE=false
DESCRIPTION="$@"

if echo "$@" | grep -q '\-\-worktree'; then
  WORKTREE=true
  DESCRIPTION=$(echo "$@" | sed 's/--worktree//g' | xargs)
fi
```

If `--worktree` is set, a git worktree will be created at `<repo>/.worktrees/<bead-id>-<slug>/` after the bead is created.

You are formalizing work into a tracked br bead. The bead is the backbone.

## Phase 1: Graph Context

```bash
bv --robot-triage              # Project state
bv --robot-suggest             # Duplicates, missing deps, label suggestions
bv --robot-plan                # Execution tracks — where does new work fit?
bv --robot-search --search "$DESCRIPTION"   # Semantic dedup
br search "$DESCRIPTION" --status open --status in_progress --json  # Exact dedup
```

If a matching bead exists, surface it: work on existing or create new?

## Phase 2: Classify

| Signal | Type | Slug prefix |
|--------|------|-------------|
| add/build/create/new | feature | `feat-` |
| fix/crash/error/broken | bug | `fix-` |
| refactor/migrate/cleanup | task | `task-` |
| multi-phase/complex | epic | `epic-` |
| test/docs/ci/config | chore | `chore-` |

Check `bv --robot-label-health` for existing label patterns. Use consistent labels.

Priority: P0=production down | P1=blocking | P2=default | P3=nice-to-have | P4=backlog

Check `bv --robot-priority` — if this unblocks mispriorized work, adjust priority accordingly.

## Phase 3: Create

### Single Bead

```bash
br create "$DESCRIPTION" --type <type> --priority <0-4> --slug <slug> --labels "domain,component" --estimate <min> --json
```

### Epic + Children

```bash
br create "$DESCRIPTION" --type epic --priority <0-4> --slug <slug> --json
br create "<child>" --type task --parent <epic-id> --json
```

3-7 children max. Each independently claimable.

## Phase 4: Enrich

```bash
br update <id> --agent-context '{"objective":"...","constraints":{"MUST":[],"SHOULD":[]},"files":{"allowed":[],"forbidden":[]}}' --json
br update <id> --add-label "domain,component" --json
```

## Phase 5: Artifacts

Create `.beads/artifacts/<bead-id>/`:

**prd.md** — Use template from `.pi/templates/prd.md`. Problem (WHEN/THEN/BECAUSE), Scope (In/Out), Requirements table, Approach, Risks, Success Criteria.

**prd.json** — Machine-readable mirror: `{bead_id, type, priority, requirements, success_criteria}`.

**decisions.md** — Use template from `.pi/templates/decisions.md`. Decision log, rejected alternatives, assumptions.

**progress.txt** — Append-only: `[<date>] Bead created: <id>`

## Phase 6: Worktree (if --worktree)

If `WORKTREE=true`, create an isolated git worktree:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
BEAD_ID=<id from Phase 3>
SLUG=<slug from Phase 3>
BRANCH="worktree/${BEAD_ID}-${SLUG}"
WORKTREE_PATH="${REPO_ROOT}/.worktrees/${BEAD_ID}-${SLUG}"

# Create worktree directory and branch
mkdir -p "${REPO_ROOT}/.worktrees"
git worktree add "$WORKTREE_PATH" -b "$BRANCH" HEAD

# Mirror artifacts into worktree
mkdir -p "$WORKTREE_PATH/.beads/artifacts/$BEAD_ID"
cp .beads/issues.jsonl "$WORKTREE_PATH/.beads/issues.jsonl"
cp -R ".beads/artifacts/$BEAD_ID/." "$WORKTREE_PATH/.beads/artifacts/$BEAD_ID/"

# Record worktree path
echo "$WORKTREE_PATH" > ".beads/artifacts/$BEAD_ID/worktree.txt"
```

**Safety:**
- Check for collision: `test -e "$WORKTREE_PATH"` — if exists, ask user
- Never copy `.beads/beads.db`, `.env.local`, credentials
- Ask before editing .gitignore

## Phase 7: Verify

```bash
br lint <id> --json
bv --robot-suggest             # Check for new issues this creates
ls .beads/artifacts/<bead-id>/
[ "$WORKTREE" = "true" ] && ls "$WORKTREE_PATH/.beads/artifacts/$BEAD_ID/"
br sync --flush-only
```

## Phase 8: Report

```
Bead: <id> | Type: <type> | Priority: P<n>
Graph fit: <where this sits in execution tracks>
Impact: <what this unblocks per robot-plan>
Artifacts: .beads/artifacts/<id>/
Worktree: <path if --worktree, "none" otherwise>
Next: /plan <id>
```
