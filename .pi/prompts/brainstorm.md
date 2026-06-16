---
description: "Ideation. Graph-informed — uses bv triage, suggest, priority, and label analysis to find high-impact work."
argument-hint: "<topic or problem to brainstorm>"
---

## Prerequisites

None. This is the entry point.

You are brainstorming work. Use the project graph to inform ideation — don't brainstorm in a vacuum. Load the **brainstorming** skill for cognitive tools (UNDERSTAND → SYNTHESIZE).

## Phase 1: Graph Context

```bash
bv --robot-triage              # Project state: open, blocked, in progress
bv --robot-suggest             # Hygiene: duplicates, missing deps, cycle warnings
bv --robot-priority            # Priority misalignment: graph importance vs assigned
bv --robot-label-attention     # Labels needing focus (stale, high-impact)
bv --robot-plan                # Execution tracks — where work fits
```

From triage, extract:
- What's blocked and why — unblocking work is high-impact
- What's on the critical path — delays here delay everything
- What's mispriorized — graph says P1 but assigned P3
- What's stale — neglected work that needs attention
- What's missing — suggest finds gaps (missing deps, duplicates)

## Phase 2: Dedup

```bash
bv --robot-search --search "$@"   # Semantic search across beads
br search "$@" --status open --status in_progress --json
```

If matching work exists, surface it. Don't brainstorm duplicates.

## Phase 3: Research (Automatic)

Research happens every brainstorm — not optional.

### Web Search (Firecrawl)
Search for patterns, alternatives, and best practices:
```bash
web_search "$@ patterns best practices"
web_search "$@ alternatives open source"
```
Extract:
- What approaches exist in the wild
- What tools/libraries solve similar problems
- What patterns are considered best practice
- What anti-patterns to avoid

### Past Context (Honcho)
```bash
honcho_search "$@"
```
Extract:
- What has been discussed about this topic before
- Past decisions that constrain this work
- Known gotchas or warnings

### Codebase Patterns (Scout)
```bash
delegate(agent="scout", task="Find patterns adjacent to '$@' in this codebase. Look for: similar implementations, related files, co-changing patterns, existing abstractions that could be reused. Return file paths and brief descriptions.")
```
Extract:
- Existing patterns to follow
- Files that will likely co-change
- Abstractions that can be reused
- Gaps in the current implementation

## Phase 4: Ideation

Generate 3-5 alternatives. For each:
- What it solves (link to graph data + research)
- What it unblocks (check robot-plan tracks)
- What pattern it follows (from research)
- Effort estimate
- Risk

Use brainstorming skill techniques: SCAMPER, inversion, analogy, constraint relaxation.

## Phase 5: Decision Gate

Pick one. Criteria:
- **Impact** — does it unblock downstream work? (robot-plan)
- **Alignment** — is priority misaligned? (robot-priority)
- **Effort** — is it achievable in one session?
- **Hygiene** — does it fix a suggest warning? (robot-suggest)
- **Pattern** — does it follow a proven pattern? (research)

## Phase 6: Output

```
Decision: <chosen alternative>
Rationale: <why, citing graph data + research>
Pattern: <what inspo/pattern informed this>
Impact: <what it unblocks>
Open questions: <what we don't know yet>
Suggested scope: <in/out boundaries>
Next: /create --worktree "<scoped description>"
```
