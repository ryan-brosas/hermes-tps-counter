---
purpose: Product Requirements Document for a bead
updated: 2026-06-16
---

# PRD: Document REST API, WebSocket, Prometheus, and config options in README

**Bead:** her-her-readme-api-ws-prom-config-6y0 | **Type:** docs | **Priority:** P3
**Created:** 2026-06-16 | **Estimate:** 45

## Problem

WHEN a user or developer reads the README THEN they see only the Python API, basic install, and status bar integration BECAUSE the REST API (`api.py`), WebSocket streaming, Prometheus metrics (`prometheus_metrics.py`), and configuration system (`config.py`) are fully implemented but undocumented.

**Who is affected?** Anyone integrating with or deploying the plugin — operators who want HTTP metrics, dashboard builders who need WebSocket data, DevOps teams scraping Prometheus, and users who want to configure the plugin via TOML or env vars.

**Why now?** The features exist and work. Without docs, users don't know they exist. Discovery requires reading source code, which defeats the purpose of a plugin.

## Scope

### In Scope
- Document all REST API endpoints (`/api/v1/health`, `/api/v1/sessions`, `/api/v1/sessions/{id}/tps`, `/api/v1/summary`, `/api/v1/events/{id}`, `/api/v1/trends/{id}`, `/metrics`)
- Document WebSocket endpoint (`/ws/tps`) with message format
- Document Prometheus metrics (metric names, labels, types)
- Document configuration system (TOML file, env vars, ctx overrides, merge precedence)
- Document all config fields with defaults and types
- Update the existing README "No Configuration Required" section to cover optional config

### Out of Scope
- Adding new features or endpoints
- Creating separate docs site or wiki
- Documenting internal implementation details
- Adding code examples beyond curl/basic usage

## Requirements

| # | Requirement | Priority | Acceptance Criteria |
|---|------------|----------|-------------------|
| 1 | REST API section with all endpoints, methods, params, and response schemas | MUST | Each endpoint has method, path, params, and example response |
| 2 | WebSocket section with connection URL, message format, and reconnection notes | MUST | Message envelope format documented with JSON example |
| 3 | Prometheus section with metric names, types, labels, and scraping config | MUST | All 9 metrics listed with name, type, and label dimensions |
| 4 | Configuration section with TOML, env vars, and ctx override docs | MUST | All 7 config fields documented with type, default, env var, and TOML key |
| 5 | Merge precedence documented | SHOULD | Clear ordering: defaults < TOML < env < ctx |
| 6 | Quick-start examples for enabling API, Prometheus, and config | SHOULD | Copy-paste TOML snippet and env var examples |

## Technical Context

Key source files:
- `api.py` — FastAPI app with REST endpoints and WebSocket manager
- `config.py` — `TPSConfig` dataclass with TOML/env/ctx loading
- `prometheus_metrics.py` — Prometheus gauges, counters, and registry
- `__init__.py` — `register()` entry point that wires config → API → Prometheus

## Approach

Extend the existing README.md with new sections after the current content. Keep the "No Configuration Required" message but add an "Optional Configuration" section. Follow the existing README's style (headers, code blocks, tables).

**Alternatives considered:**
- Separate `docs/` directory — rejected because README is the primary discovery point and the project is small enough for a single file
- Auto-generated API docs (FastAPI's `/docs`) — good supplementary but not discoverable without docs pointing to it

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Docs drift from code as endpoints change | Med | Med | Keep docs close to code; PR review checklist |
| Over-documenting internal details | Low | Low | Focus on user-facing API surface only |

## Success Criteria

- [ ] README documents all 7 REST endpoints with methods, paths, and response schemas
    - Verify: `grep -c '/api/v1/' README.md` returns >= 6
- [ ] README documents WebSocket `/ws/tps` endpoint with message format
    - Verify: `grep 'ws/tps' README.md` finds the section
- [ ] README documents all 9 Prometheus metrics
    - Verify: `grep -c 'tps_' README.md` in Prometheus section returns >= 9
- [ ] README documents all 7 config fields with env var names
    - Verify: `grep -c 'TPS_COUNTER_' README.md` returns >= 7
- [ ] README documents merge precedence
    - Verify: `grep 'precedence\|merge' README.md` finds the ordering
