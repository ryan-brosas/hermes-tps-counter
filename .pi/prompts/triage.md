---
description: "Triage open br beads — classify, prioritize, unblock. Graph-native — uses full bv analysis."
argument-hint: "[bead-id or leave empty for project-wide triage]"
---

You are triaging open br beads. Use bv for graph intelligence, br for inspection.

## Phase 1: Full Graph Triage

```bash
bv --robot-triage --no-cache   # Unified triage: health, wins, blockers, recs
bv --robot-plan                # Execution tracks — parallel-safe work
bv --robot-insights            # Graph metrics — PageRank, critical path, HITS
bv --robot-suggest             # Hygiene: duplicates, missing deps, cycles
bv --robot-priority            # Priority misalignment detection
bv --robot-label-health        # Per-label health metrics
bv --robot-label-attention     # Labels needing focus
bv --robot-capacity            # Capacity simulation
bv --robot-alerts              # Stale issues, blocking cascades
```

Extract:
- `quick_wins` — high-confidence ready work
- `blockers_to_clear` — what to unblock first
- `misaligned` — items with wrong priority
- `duplicates` — suggested duplicates
- `missing_deps` — suggested dependencies
- `cycles` — circular dependencies to break
- `stale_labels` — labels needing attention
- `capacity` — can we handle more work?

## Phase 2: Br Health

```bash
br doctor
br stats --by-type --by-priority --json
```

## Phase 3: List Open Beads

```bash
br list --status open --json
br list --status in_progress --json
```

## Phase 4: Classify

| State | Meaning | Action |
|-------|---------|--------|
| needs-triage | New, unclassified | Classify now |
| needs-info | Missing AC or scope | Ask user |
| ready-for-agent | Clear, scoped, unblocked | /ship |
| ready-for-human | Needs user decision | Present to user |
| wontfix | No longer relevant | Close |
| mispriorized | Wrong priority per graph | Adjust |
| duplicate | Duplicate of existing | Close with reference |

## Phase 5: Check Readiness

For each bead:
- Title clear and actionable?
- Acceptance criteria exist?
- Not blocked? (check `br blocked --json --detailed`)
- Scope bounded?
- Priority correct? (check `bv --robot-priority`)

## Phase 6: Check Staleness

```bash
br stale --json --days 7
br coordination status --json
```

## Phase 7: Report

Triage summary table with:
- Bead ID, title, state, priority, graph-priority
- Graph insights (PageRank, critical path, blocks)
- Suggested actions (from robot-suggest)
- Quick wins highlighted
- Blockers to clear highlighted
- Priority misalignments flagged
- Capacity assessment
