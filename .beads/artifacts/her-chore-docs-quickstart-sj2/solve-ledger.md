---
purpose: Implementation ledger
updated: 2026-06-17
---

# Solve Ledger: her-chore-docs-quickstart-sj2

## Wave 1 — Source-of-truth review

- Confirmed `plugin.yaml` metadata: `name: tps-counter`, version `1.0.0`, hook `post_api_request`.
- Reviewed `__init__.py` for hook behavior, snapshot fields, freshness metadata, privacy env vars, `get_tps_stats(session_id)`, `get_observability_contract()`, and `get_privacy_diagnostics()`.
- Reviewed `tests/test_api.py` and `tests/test_privacy.py` for absent optional surfaces, zero stats, snapshot fields, and secret-safe privacy expectations.

## Wave 2 — README update

- Rewrote README into a user-flow order: quickstart, status-bar integration, API helper, observability contract, privacy, troubleshooting.
- Added install/restart/verify checklist without new tooling or package-manager instructions.
- Clarified status-bar patch points, active CLI expectation, snapshot fields, stale handling, session mismatch handling, and positive/zero TPS rendering.
- Documented available in-process observability surfaces and contract-marked unavailable REST/WebSocket/Prometheus surfaces.
- Added troubleshooting table covering installation, stale/cross-session display, zero stats, privacy redaction, missing optional surfaces, plugin registration, and blank labels.

## Wave 3 — Verification

- Pending final diff, source-name cross-check, bead hygiene, completion evidence, commit, close, and PR creation.
