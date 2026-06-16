---
name: orchestrator
description: "Strict workflow recipe. Run each prompt in sequence. No skipping. The workflow-gate extension enforces this."
---

# Workflow

Follow this sequence. Run each prompt in FULL. Do not skip phases.

## The Sequence

1. `/brainstorm [topic]` — ideation, pick what to build
2. `/create [description]` — formalize into bead + PRD + decisions
3. `/plan [bead-id]` — decompose into test-first tasks
4. `/ship [bead-id]` — implement (make tests pass)
5. `/verify [bead-id]` — run tests, write evidence
6. `/review [bead-id]` — check spec↔code drift
7. `git add -A && git commit && git push` — PR

## Rules

- Run each prompt in FULL. Every section, every step.
- Do not skip phases.
- Do not "helpfully" proceed if the prompt says STOP.
- The workflow-gate extension enforces this. Don't fight it.
- If blocked, run the prerequisite prompt.

## Artifacts Per Phase

| Phase | Prompt | Produces | Gate |
|-------|--------|----------|------|
| Ideation | /brainstorm | Decision + rationale | User confirms direction |
| Create | /create | prd.md, prd.json, decisions.md, progress.txt | User confirms scope |
| Plan | /plan | plan.md, tasks.md, context-capsule.md | User approves plan |
| Ship | /ship | Working code + tests | Tests pass |
| Verify | /verify | completion-evidence.json | All tests pass |
| Review | /review | Reconciliation report | Adherence ≥70% |
| PR | commit + push | PR link | — |
