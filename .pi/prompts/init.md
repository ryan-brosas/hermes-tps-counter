---
description: "Initialize project memory and br workspace. Generates .pi/memory/project/ files and root AGENTS.md."
argument-hint: "[project-name]"
---

You are initializing a new project from the pi-core template.

## Phase 1: Gather Info

Ask the user (one question at a time, multiple choice preferred):

1. **Project name:** What is this project called?
2. **Goal:** One sentence — what does this project do?
3. **Tech stack:** Language, runtime, framework, package manager
4. **Prefix:** br issue prefix (default: first 3 letters of project name)
5. **Gotchas:** Any known pitfalls or footguns? (can skip, add later)

## Phase 2: Initialize br

```bash
br init --prefix <prefix>
```

If `.beads/` already exists, skip.

## Phase 3: Generate Memory Files

For each file in `.pi/memory/project/`, fill in the template with user's answers:

### project.md

```markdown
---
purpose: Project vision, goals, and success criteria
updated: <today>
---

# Project: <name>

## The Goal

<user's one-sentence goal>

## Success Criteria

1. [To be defined]
2. [To be defined]
3. [To be defined]

## Current Phase

- **Status:** active
- **Milestone:** Initial setup
- **Next:** First feature work
```

### conventions.md

```markdown
---
purpose: How we build — naming, code style, workflow
updated: <today>
---

# Conventions: <name>

## Naming

- Files: kebab-case
- Functions: <language convention>
- Classes: PascalCase

## Code Style

- <from tech stack>

## Git

- Branch: <type>/<bead-id>-<slug>
- Commit: conventional commits

## Workflow

1. Triage — bv --robot-triage
2. Claim — br update <id> --claim
3. Implement — follow plan
4. Verify — run commands, no claims without evidence
5. Close — br close <id> --suggest-next
6. Sync — br sync --flush-only

## Agent Conventions

- Evidence before claims
- Read before edit
- Ask before destructive
- One task per session
```

### tech-stack.md

```markdown
---
purpose: Tech stack and verification commands
updated: <today>
---

# Tech Stack: <name>

## Runtime

| Layer | Tool | Version |
|-------|------|---------|
| Language | <lang> | <version> |
| Runtime | <runtime> | <version> |
| Package manager | <pm> | <version> |

## Verification Commands

```bash
# Lint
<command>

# Test
<command>

# Build
<command>
```

## Constraints

- [To be defined]
```

### gotchas.md

```markdown
---
purpose: Known pitfalls and warnings
updated: <today>
---

# Gotchas: <name>

## Active Warnings

| Date | Area | Gotcha | Impact | Mitigation |
|------|------|--------|--------|------------|
| <today> | setup | <any user-reported gotchas> | <impact> | <mitigation> |
```

### decisions.md

```markdown
---
purpose: Architecture decision records
updated: <today>
---

# Decisions: <name>

## Decision Log

| # | Date | Decision | Rationale | Confidence |
|---|------|----------|-----------|------------|
| 1 | <today> | Use br/bv for task tracking | pi-core template | High |
```

## Phase 4: Generate Root AGENTS.md

Write root `AGENTS.md` (delegates to `.pi/AGENTS.md`):

```markdown
# <name>

See [.pi/AGENTS.md](.pi/AGENTS.md) for conventions, memory protocol, and workflow.
```

## Phase 5: Verify

```bash
# Memory files exist
ls .pi/memory/project/

# br initialized
br doctor

# Root AGENTS.md delegates
cat AGENTS.md

# Context budget (Tier 1 under 500 tokens)
wc -w .pi/memory/project/project.md .pi/memory/project/conventions.md
```

## Phase 6: Report

```
Project: <name>
Prefix: <prefix>
Memory: .pi/memory/project/ (5 files)
br: initialized at .beads/
AGENTS.md: delegates to .pi/AGENTS.md

Next steps:
1. Fill in success criteria in project.md
2. Add verification commands to tech-stack.md
3. Run /brainstorm to plan first feature
```

## Guardrails

- Ask before overwriting existing files
- No credentials in memory files
- Keep generated files portable — use placeholders until user provides real values
- If .beads/ exists, don't reinitialize br
