---
purpose: Decision log for a bead
updated: 2026-06-16
---

# Decisions: her-her-readme-api-ws-prom-config-6y0

## Decision Log

| # | Decision | Rationale | Confidence |
|---|----------|-----------|------------|
| 1 | Document in README.md, not separate docs/ | Project is small; README is the primary discovery point. Single-file docs reduce maintenance burden. | High |
| 2 | Keep "No Configuration Required" message, add optional config section below | Preserves the zero-config promise while surfacing power-user options. Matches the existing README tone. | High |
| 3 | Document REST API as a reference table (endpoint, method, params, response) | Faster to scan than prose. Matches how developers actually look up API info. | High |
| 4 | Include Prometheus metric names as a table with labels | Prometheus users need exact metric names for PromQL queries. Table format is standard in Prometheus docs. | Med |
| 5 | Show TOML config as the primary config method, env vars as alternative | TOML is more readable for multi-field config. Env vars are for container/CI use. | Med |

## Rejected Alternatives

| # | Alternative | Why Rejected | Risk if Re-introduced |
|---|-------------|--------------|----------------------|
| 1 | Separate docs/ directory with mkdocs | Over-engineered for a plugin this size. Adds build step and hosting concern. | Maintenance drift between README and docs site |
| 2 | Auto-generate API docs from FastAPI OpenAPI | `/docs` already exists but users need to know it exists. Also doesn't cover config or Prometheus. | Incomplete coverage; users still need a guide |
| 3 | Inline docstrings only | Not discoverable without reading source code. Doesn't cover config system. | Users miss features entirely |

## Assumptions

| # | Assumption | Validation | Invalidation Impact |
|---|------------|------------|---------------------|
| 1 | README.md is the correct place for plugin docs | Validated — project has no docs site, README is the only doc | Would need to create docs infrastructure |
| 2 | Users will find the API via the README | Unknown — may need to also surface in Hermes plugin docs | Add cross-references later |
| 3 | The current API surface is stable | Validated — all endpoints exist in api.py and are tested | Docs would need updating on API changes |
