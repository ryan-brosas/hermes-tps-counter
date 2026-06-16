# bv Command Reference — Full Robot Mode Surface

All robot commands output JSON by default. No `--json` flag needed.
For agent help: `bv --robot-help` or `bv --robot-docs guide`.

## Triage & State (What's happening?)

```bash
bv --robot-triage                          # Unified triage: health, wins, blockers, recs
bv --robot-next                            # Single top recommendation
bv --robot-alerts                          # Stale issues, blocking cascades, priority mismatches
bv --robot-alerts --severity critical      # Critical alerts only
bv --robot-alerts --alert-type stale_issue # Filter by alert type
```

## Planning (What should I do next?)

```bash
bv --robot-plan                            # Dependency-respecting execution tracks
bv --robot-plan --label "backend"          # Scope to label
bv --robot-priority                        # Priority misalignment detection
bv --robot-recipe actionable --robot-plan  # Pre-filter: ready to work
bv --robot-recipe high-impact --robot-triage  # Pre-filter: top PageRank
bv --robot-recipes                         # List available recipes
```

## Graph Analysis (What's the structure?)

```bash
bv --robot-insights                        # PageRank, betweenness, HITS, eigenvector, k-core, cycles
bv --robot-insights --as-of HEAD~30        # Historical point-in-time
bv --robot-graph --graph-format json       # Dependency graph (JSON)
bv --robot-graph --graph-format mermaid    # Dependency graph (Mermaid)
bv --robot-graph --graph-format dot        # Dependency graph (Graphviz)
```

## Impact & Blast Radius (What's affected?)

```bash
bv --robot-impact <bead-id>                # Files that may be modified by a bead
bv --robot-impact-network                  # Full impact network graph
bv --robot-impact-network <bead-id>        # Subnetwork for a specific bead
bv --robot-impact-network <id> --network-depth 3  # Deeper network (1-3)
bv --robot-causality <bead-id>             # Causal chain analysis
bv --robot-blocker-chain <bead-id>         # Full blocker chain analysis
```

## File Analysis (What files are involved?)

```bash
bv --robot-file-hotspots                   # Files touched by the most beads
bv --robot-file-beads <file-path>          # Beads that touched a specific file
bv --robot-file-relations <file-path>      # Files that frequently co-change
```

## Related Work (What's connected?)

```bash
bv --robot-related <bead-id>               # Beads related to a specific bead
bv --robot-search --search "query"         # Semantic vector search
bv --robot-search --search "query" --search-limit 5  # Limit results
bv --robot-search --search "query" --search-mode hybrid  # Hybrid ranking
```

## History & Drift (What changed?)

```bash
bv --robot-diff --diff-since <ref>         # Changes since commit/branch/tag/date
bv --robot-diff --diff-since HEAD~5        # Changes since last 5 commits
bv --robot-history                         # Bead-to-commit correlations
bv --robot-history --history-since "30 days ago"  # Limit history window
bv --robot-drift --check-drift             # Drift detection from baseline
bv --robot-drift --save-baseline "desc"    # Save current state as baseline
bv --robot-drift --baseline-info           # Show baseline info
bv --robot-history --bead-history <bead-id>  # History for a specific bead
```

## Forecasting & Capacity (When will it be done?)

```bash
bv --robot-forecast <bead-id>              # ETA prediction for a bead
bv --robot-forecast all                    # Forecast all open issues
bv --robot-forecast --forecast-label "backend"  # Filter by label
bv --robot-forecast --forecast-agents 3    # Multi-agent capacity calc
bv --robot-capacity                        # Capacity simulation
bv --robot-capacity --agents 3             # Simulate with 3 agents
bv --robot-capacity --capacity-label "backend"  # Filter by label
```

## Sprint Management

```bash
bv --robot-sprint-list                     # List all sprints
bv --robot-sprint-show <sprint-id>         # Sprint details
bv --robot-burndown <sprint-id>            # Burndown data
bv --robot-burndown current                # Current sprint burndown
```

## Label Analysis

```bash
bv --robot-label-health                    # Per-label health metrics
bv --robot-label-flow                      # Cross-label dependency flow
bv --robot-label-attention                 # Labels needing focus
bv --robot-label-attention --attention-limit 3  # Top 3 labels
```

## Hygiene & Suggestions

```bash
bv --robot-suggest                         # Duplicates, missing deps, label suggestions, cycle warnings
bv --robot-orphans                         # Orphan commit candidates
```

## Git Correlations

```bash
bv --robot-explain-correlation <commit>    # Why a commit is linked to a bead
bv --robot-confirm-correlation <commit>    # Record positive feedback
bv --robot-reject-correlation <commit>     # Record negative feedback
bv --robot-correlation-stats               # Summary counts for feedback
```

## Schema & Documentation

```bash
bv --robot-capabilities                    # Machine-readable command manifest
bv --robot-schema                          # JSON Schema definitions
bv --robot-schema --schema-command robot-triage  # Schema for specific command
bv --robot-docs guide                      # Agent documentation (JSON)
bv --robot-docs commands                   # Command reference (JSON)
bv --robot-docs examples                   # Usage examples (JSON)
bv --robot-docs env                        # Environment variables (JSON)
bv --robot-docs all                        # Everything (JSON)
bv --robot-metrics                         # Performance metrics
```

## Export & Reporting

```bash
bv --export-md report.md                   # Export to Markdown
bv --export-graph                          # Export graph (.html/.png/.svg)
bv --export-graph graph.html               # Interactive HTML
bv --priority-brief brief.md               # Priority brief
bv --agent-brief ./brief-dir               # Agent brief bundle
bv --export-pages ./site                   # Static site export
bv --emit-script                           # Shell script for top-N recommendations
bv --emit-script --script-limit 10         # Top 10
```

## Filters (Apply to any command)

```bash
bv --label "backend"                       # Scope to label's subgraph
bv --robot-by-assignee "agent-1"           # Filter by assignee
bv --robot-by-label "backend"              # Filter robot output by label
bv --robot-min-confidence 0.5              # Min confidence (0.0-1.0)
bv --robot-max-results 10                  # Limit results
bv --no-cache                              # Bypass disk cache
bv --recipe actionable                     # Pre-built filter recipes
bv --format toon                           # Token-optimized output (~40% fewer tokens)
bv --format toon --stats                   # TOON with savings stats
bv --workspace .bv/workspace.yaml          # Workspace config
bv --repo "api"                            # Filter by repo prefix
```

## Agent File Management

```bash
bv --agents-add                            # Add workflow instructions to AGENTS.md
bv --agents-remove                         # Remove workflow instructions
bv --agents-update                         # Update to latest version
bv --agents-check                          # Check AGENTS.md status
```
