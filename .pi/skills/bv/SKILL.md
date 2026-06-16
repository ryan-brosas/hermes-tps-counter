---
name: bv
description: "Graph intelligence for br beads. 41 robot commands for triage, impact, file analysis, forecasting, and more. Read-only — use br for mutations."
---

# bv — Beads Viewer (Graph Intelligence)

bv reads br's `.beads/` database and provides graph analysis. Read-only — bv never mutates beads.

For full command reference: `bv --help` or load `references/commands.md`.
For bead mutations: load the **br** skill.

## Cognitive Tool: What's the State?

```bash
bv --robot-triage              # THE entry point — health, wins, blockers, recs
bv --robot-next                # Single top pick + claim command
bv --robot-alerts              # Stale issues, blocking cascades
```

Returns: quick_ref, quick_wins, blockers_to_clear, project_health, recommendations.

## Cognitive Tool: What Should I Work On?

```bash
bv --robot-priority            # Priority misalignment detection
bv --robot-suggest             # Duplicates, missing deps, cycle warnings
bv --robot-label-attention     # Labels needing focus
bv --robot-label-health        # Per-label health metrics
```

## Cognitive Tool: How Do I Plan?

```bash
bv --robot-plan                # Dependency-respecting execution tracks
bv --robot-insights            # PageRank, critical path, HITS, betweenness
bv --robot-forecast <id>       # ETA prediction for a bead
bv --robot-capacity            # Capacity simulation — how much can we handle
bv --robot-burndown <sprint>   # Sprint burndown data
```

## Cognitive Tool: What's the Blast Radius?

```bash
bv --robot-impact <id>         # Files that may be modified by a bead
bv --robot-impact-network <id> # Full impact network graph
bv --robot-causality <id>      # Causal chain analysis
bv --robot-blocker-chain <id>  # Full blocker chain
```

## Cognitive Tool: What Files Are Involved?

```bash
bv --robot-file-hotspots       # Files touched by the most beads
bv --robot-file-beads <file>   # What tasks touched a specific file
bv --robot-file-relations <file>  # Files that co-change with a given file
```

Use before editing: check what tasks touched the file, what files co-change.

## Cognitive Tool: What's Related?

```bash
bv --robot-related <id>        # Beads related to a specific bead
bv --robot-search --search "query"  # Semantic search across beads
```

## Cognitive Tool: What Changed?

```bash
bv --robot-diff --diff-since <ref>  # Changes since a historical point
bv --robot-history             # Bead-to-commit correlations
bv --robot-drift               # Drift detection from baseline
```

## Decision Tree

```
Full project triage       → bv --robot-triage
Single best pick          → bv --robot-next
Plan parallel execution   → bv --robot-plan
Priority recommendations  → bv --robot-priority
Graph insights            → bv --robot-insights
Blast radius              → bv --robot-impact <id>
File history              → bv --robot-file-beads <file>
Co-changing files         → bv --robot-file-relations <file>
Related work              → bv --robot-related <id>
Semantic search           → bv --robot-search --search "query"
Hygiene check             → bv --robot-suggest
ETA prediction            → bv --robot-forecast <id>
Capacity planning         → bv --robot-capacity
```

All robot commands output JSON by default — no `--json` flag needed.

## Integration Pattern

**bv for intelligence, br for mutations:**

```
bv --robot-triage → find quick_wins → br show <id> → br update <id> --claim → br close <id>
bv --robot-plan   → get tracks → assign per track → agents claim independently
bv --robot-impact → check blast radius → edit files → verify coverage
bv --robot-file-beads → check file history → avoid reverting others' work
```

## Filters

```bash
bv --label "backend"                       # Scope to label's subgraph
bv --robot-by-assignee "agent-1"           # Filter by assignee
bv --robot-min-confidence 0.5              # High-confidence only
bv --robot-max-results 5                   # Limit results
bv --no-cache                              # Bypass disk cache
bv --recipe actionable --robot-plan        # Pre-filter: ready to work
bv --recipe high-impact --robot-triage     # Pre-filter: top PageRank
```

Note: `--severity` only applies to `--robot-alerts`, not all commands.

## Anti-Patterns

| Don't | Do Instead |
|-------|-----------|
| Skip session triage | Run `bv --robot-triage` first |
| Edit files without checking history | `bv --robot-file-beads <file>` first |
| Ignore blast radius | `bv --robot-impact <id>` before coding |
| Dispatch without graph analysis | `bv --robot-plan` for tracks |
| Use bv to mutate beads | Use br for all mutations |
| Use `--json` flag | Robot commands output JSON by default |
