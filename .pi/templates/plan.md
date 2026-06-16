---
purpose: Wave-sequenced implementation plan
updated: [date]
---

# Plan: [bead-id]

**Goal:** [One sentence describing the outcome]

## Graph Context

- **Blast radius:** [files from bv --robot-impact]
- **Unblocks:** [downstream beads]
- **Blocked by:** [upstream beads]
- **Critical path:** [yes/no]
- **Forecast:** [ETA from bv --robot-forecast]

## Observable Truths

What must be TRUE for the goal to be achieved:

1. [Observable truth 1 — user/system can do X]
2. [Observable truth 2 — artifact/behavior Y exists]
3. [Observable truth 3 — verification Z proves completion]

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| [name] | [what it enables] | `[path]` | Need/Done/Verify |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | [tasks] | [yes/no] | [what must be true] | `[command]` |
| 2 | [tasks] | [yes/no] | [Wave 1 complete] | `[command]` |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd [repo]
[focused check 1]
[focused check 2]
[build/test command]
```
