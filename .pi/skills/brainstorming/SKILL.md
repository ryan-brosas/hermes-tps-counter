---
name: brainstorming
description: "Cognitive tools for ideation. UNDERSTAND the problem → SYNTHESIZE the strongest ideas. Use before /create when goals are ambiguous."
---

# Brainstorming — Cognitive Tools

**UNDERSTAND** (frame the problem) → **SYNTHESIZE** (converge on strongest ideas)

## When to Use

- Rough idea needs clarification into a design or spec
- Multiple approaches exist with no clear winner
- High-stakes work (many files, public APIs, security)

## When NOT to Use

- Requirements are clear and execution is mechanical
- Already in implementation with a validated plan

## Phase 0: Problem Framing

Before exploring solutions, understand the problem:

1. Check current project state (bv --robot-triage, br list)
2. Answer:
   - Who is affected?
   - What outcome do we want? (specific, observable)
   - Is this root cause or symptom?
   - Why now?
   - What constraints can't we change?
   - What are we explicitly NOT solving?

**Gate:** "Is this the right problem to solve?" If uncertain, research first.

## Phase 1: Assumption Surfacing

For each assumption:
- Why it might be wrong
- How to validate it
- Risk level (1-5)

If any assumption scores 4+, validate before proceeding.

## Phase 2: Ideation Techniques

### Inversion
"What would guarantee failure? How do we avoid that?"

### SCAMPER
- **S**ubstitute — What can we replace?
- **C**ombine — What can we merge?
- **A**dapt — What existing solution can we borrow?
- **M**odify — What can we change (scale, shape, timing)?
- **P**ut to other use — What else could this do?
- **E**liminate — What can we remove?
- **R**everse — What if we did the opposite?

### Analogy
"What would [familiar system] do?" Look at how similar problems are solved in other domains.

### Constraint Relaxation
Temporarily remove one constraint. Ideate freely. Re-introduce and adapt.

## Phase 3: Evaluate Alternatives

For each candidate:

| Field | Content |
|-------|---------|
| Approach | Short name |
| Description | One sentence |
| Pros | 2-3 bullets |
| Cons | 2-3 bullets |
| Effort | Low/Med/High |
| Risk | Low/Med/High |

## Phase 4: Decision Gate

| Criterion | Weight | A | B | C |
|-----------|--------|---|---|---|
| Impact | H | | | |
| Effort | M | | | |
| Risk | H | | | |
| Leverage | M | | | |

**Chosen:** [name] — **Rationale:** [why]
**Rejected:** [names + specific why]

## Phase 5: Handoff

**STOP HERE. Do not proceed to implementation.**

Present the decision to the user and wait. Do not create beads, write code, or make changes.

- Confident? → Suggest `/create "<scoped bead title>"` and **wait for user confirmation**
- Uncertain? → Suggest research to fill gaps
- Wrong problem? → Suggest re-framing

**The user decides when to proceed. Not you.**

## Anti-Patterns

| Don't | Do Instead |
|-------|-----------|
| Ask questions the codebase can answer | Search first, then ask only unresolved questions |
| Generate 10+ alternatives without narrowing | Present 2-3 viable options with decision criteria |
| Continue brainstorming after direction emerges | Confirm, summarize, transition to /create |
| Jump to solution without framing | Frame the problem first |
| Proceed to /create without user confirmation | Present decision, STOP, wait for user |
