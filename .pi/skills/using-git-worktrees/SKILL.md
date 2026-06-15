---
name: using-git-worktrees
description: "Optional. Isolated git worktree per bead. Use with /create --worktree for parallel workstreams."
---

# Git Worktrees — Isolated Workspace Per Bead

**Optional skill.** Load only when `/create --worktree` is used or parallel workstreams are needed.

## When to Use

- Parallel work on multiple beads that touch overlapping files
- Long-running feature that shouldn't block the main branch
- /create --worktree flag is used

## When NOT to Use

- Simple changes in the current working tree
- Not inside a git repo (report `not-a-git-worktree`, skip)
- Single-bead work with no parallel needs

## Safety First

### 1. Check Git Context

```bash
git rev-parse --is-inside-work-tree || echo "not-a-git-worktree"
```

If not in git, skip worktree setup. Bead artifacts are still valid.

### 2. Collision Checks

```bash
git worktree list --porcelain
git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"
test -e "$WORKTREE_PATH"
```

If collision: ask to reuse, choose new suffix, use current branch, or stop. Never force.

### 3. Approval-Gated

Ask before: creating worktree/branch, editing .gitignore, installing dependencies, committing/pushing.

## Directory Selection

Priority order:
1. `.worktrees/` in repo root (if gitignored)
2. `~/.pi/worktrees/<project>/<path-slug>` (global fallback)

Never create worktrees in non-ignored directories without asking.

## Creation

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
PROJECT=$(basename "$REPO_ROOT")
BRANCH="worktree/<bead-id>-<slug>"
WORKTREE_PATH="$HOME/.pi/worktrees/$PROJECT/<bead-id>-<slug>"

mkdir -p "$(dirname "$WORKTREE_PATH")"
git worktree add "$WORKTREE_PATH" -b "$BRANCH" HEAD
```

## Beads Artifact Mirroring

Mirror only public state — never copy private/runtime files:

```bash
br sync --flush-only
mkdir -p "$WORKTREE_PATH/.beads/artifacts/$BEAD_ID"
cp .beads/issues.jsonl "$WORKTREE_PATH/.beads/issues.jsonl"
cp -R ".beads/artifacts/$BEAD_ID/." "$WORKTREE_PATH/.beads/artifacts/$BEAD_ID/"
echo "$WORKTREE_PATH" > ".beads/artifacts/$BEAD_ID/worktree.txt"
```

**Never copy:** `.beads/beads.db`, `.env.local`, credentials, sessions, lock files.

## Cleanup

```bash
git worktree remove "$WORKTREE_PATH"
git branch -d "$BRANCH"
```

## Anti-Patterns

| Don't | Do Instead |
|-------|-----------|
| Create worktrees for every bead | Use only for parallel/long-running work |
| Copy .beads/beads.db to worktree | Mirror issues.jsonl + artifacts only |
| Edit .gitignore without asking | Ask first, or use global fallback |
| Delete worktree dirs manually | Use `git worktree remove` |
| Force past collision checks | Ask user how to resolve |
