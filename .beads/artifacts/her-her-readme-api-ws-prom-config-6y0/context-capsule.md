---
purpose: Agent spawn context for a bead
updated: 2026-06-16
---

# Context Capsule: her-her-readme-api-ws-prom-config-6y0

## Objective

Add comprehensive documentation for REST API, WebSocket streaming, Prometheus metrics, and configuration options to README.md.

## Key Patterns

- `table-based API reference` — Document endpoints as method/path/params/response tables, matching common API doc style. Reference: `README.md` (existing style)
- `config field table` — Each config field gets: name, type, default, env var, TOML key. Reference: `config.py` lines 46-71
- `metric name table` — Each Prometheus metric gets: name, type, labels. Reference: `prometheus_metrics.py` lines 62-122

## Constraints

1. Edit ONLY `README.md` — no other files
2. Do NOT change existing README content, only append new sections
3. Keep "No Configuration Required" message but update it to reference optional config
4. All endpoint paths, metric names, and config fields must match the actual source code exactly
5. Do NOT add code examples beyond basic curl/usage — no full application examples

## File Ownership

| Task | Allowed | Forbidden |
|------|---------|-----------|
| Write REST API docs | `README.md` — append section | Any other file |
| Write WebSocket docs | `README.md` — append section | Any other file |
| Write Prometheus docs | `README.md` — append section | Any other file |
| Write Config docs | `README.md` — append section | Any other file |
| Update "No Configuration" | `README.md` — edit existing section | Any other file |

## Graph Context

- **Blast radius:** README.md only
- **Related beads:** None (standalone docs bead)
- **File history:** README.md last modified for per-model tracking docs
