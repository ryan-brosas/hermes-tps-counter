---
purpose: Wave-sequenced implementation plan
updated: 2026-06-16
---

# Plan: her-her-readme-api-ws-prom-config-6y0

**Goal:** Add comprehensive documentation for REST API, WebSocket, Prometheus metrics, and configuration options to README.md.

## Graph Context

- **Blast radius:** `README.md` only
- **Unblocks:** None (docs bead, low downstream impact)
- **Blocked by:** None
- **Critical path:** No
- **Forecast:** ~30 min (single file, documentation only)

## Observable Truths

1. A developer reading README.md can discover and use every REST API endpoint without reading source code
2. A developer reading README.md can connect to the WebSocket endpoint and understand the message format
3. A developer reading README.md can configure Prometheus scraping and understand all exported metrics
4. A developer reading README.md can configure the plugin via TOML file or environment variables

## Required Artifacts

| Artifact | Provides | Path | Status |
|----------|----------|------|--------|
| README.md | All documentation | `README.md` | Need |

## Wave Structure

| Wave | Tasks | Parallel? | Preconditions | Verification Gate |
|------|-------|-----------|---------------|-------------------|
| 1 | Write REST API docs section | yes | PRD complete | All 7 endpoints documented |
| 1 | Write WebSocket docs section | yes | PRD complete | Message format documented |
| 1 | Write Prometheus docs section | yes | PRD complete | All 9 metrics listed |
| 1 | Write Configuration docs section | yes | PRD complete | All 7 fields documented |
| 2 | Integrate sections into README.md | no | Wave 1 complete | `grep` checks pass |

## Tasks

Detailed task decomposition: see `tasks.md` in the same artifact directory.

## Full Verification

```bash
cd /home/ryan/repos/hermes-tps-counter/
# Check all endpoints documented
grep -c '/api/v1/' README.md
# Check WebSocket documented
grep 'ws/tps' README.md
# Check Prometheus metrics
grep -c 'tps_' README.md
# Check config fields
grep -c 'TPS_COUNTER_' README.md
# Check merge precedence
grep -i 'precedence\|merge' README.md
```
