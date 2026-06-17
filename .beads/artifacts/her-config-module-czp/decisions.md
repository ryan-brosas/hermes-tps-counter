# Decisions: her-config-module-czp

## Decision Log

### D1: Config file format — TOML
**Decision:** Use TOML for the config file format.
**Alternatives rejected:**
- YAML: Requires `pyyaml` external dependency, heavier
- JSON: No comments support, worse UX for config files
- INI: Limited type support, deprecated in Python
**Rationale:** TOML is stdlib in Python 3.11+ (`tomllib`), supports types natively, human-readable, and is the standard for Python project config (pyproject.toml).

### D2: Merge precedence — defaults < TOML < env vars < ctx
**Decision:** Four-layer merge with ctx.get_config() as highest priority.
**Rationale:** Preserves backward compatibility with existing Hermes plugin config system. Env vars override file config for CI/Docker scenarios. Defaults ensure the plugin works zero-config.

### D3: Singleton pattern for config
**Decision:** Lazy-initialized module-level singleton with threading.Lock.
**Alternatives rejected:**
- Per-call config loading: Wasteful I/O on every hook call
- Global mutable config object: Thread safety concerns
**Rationale:** Config rarely changes after startup. Lazy init avoids import-time side effects. Lock ensures thread safety.

### D4: Env var prefix — TPS_COUNTER_
**Decision:** Use `TPS_COUNTER_` prefix for all environment variables.
**Rationale:** Namespaced to avoid collisions. Consistent with plugin name. Uppercase with underscores is env var convention.

## Assumptions

1. Python 3.11+ is guaranteed (project convention)
2. Plugin config dir is `~/.hermes/plugins/tps-counter/`
3. No hot-reload needed — config is read once at startup
4. No secrets in config (all values are operational settings)
