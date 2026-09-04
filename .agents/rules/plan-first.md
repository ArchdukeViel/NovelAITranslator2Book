---
trigger: always_on
description: Default to planning and specification before making non-trivial code modifications.
---

# Plan-First Rule

## Core Directive

When requested a task, feature, change, or fix, default to **planning/spec mode only** — create a plan or specification that describes WHAT will be done and HOW — and STOP. Do **NOT** proceed to write implementation code, modify source files, or execute build/test commands unless given an explicit implementation directive.

## Artifact Protocol

1. **Implementation Plan (`docs/plans/<PLAN_NAME>.md`)**:
   - Write to `docs/plans/<PLAN_NAME>.md` or present for chat review.
   - Plans written to `docs/plans/` MUST include YAML frontmatter with `canonical_truth: false` and `title`.
   - Include: Background, User Review Required, Open Questions, Proposed Changes (grouped by component with `[MODIFY]`, `[NEW]`, `[DELETE]`), and Verification Plan.
   - Do NOT edit canonical documents (`docs/*.md`) during the planning phase.
2. **Approval Gate**:
   - STOP and wait for the user's explicit directive before modifying any codebase files.
3. **Walkthrough / Completion Summary**:
   - Upon completion, summarize all changes, verification commands, and test results in chat or follow-up evidence.

## When to Plan (Default)

Create a plan (`docs/plans/<PLAN_NAME>.md` or chat review) when:
- Requesting a new feature, endpoint, component, or capability.
- Asking for a refactor, redesign, schema migration, or architectural change.
- Fixing a bug or issue spanning multiple files or modules.
- Asking "how would you...", "can we...", "what would it take to...".
- Providing a vague or open-ended request that requires design choices.

## Exceptions (No Plan Needed)

Proceed directly without an implementation plan only when:
1. **Read-Only / Investigatory Tasks**: Searching, auditing, reading code, explaining architecture, running read-only diagnostics, or checking git status.
2. **Trivial Immediate Changes**: ALL of the following must be true:
   - Single-line fix, typo correction, or obvious configuration tweak.
   - Change affects strictly **one location** in one file.
   - Zero ambiguity on user intent.
   - Zero architectural or regression risk.

## Explicit Implementation Keywords

User must use at least **one** of the following before writing implementation code:
- "proceed" / "proceed with plan" / "proceed with implementation"
- "approved" / "approve"
- "looks good" / "lgtm"
- "implement it" / "implement this"
- "execute the plan" / "execute it"
- "code it" / "code this up"
- "make the changes" / "apply the changes"
- "start implementing" / "start coding"
- "build it" / "build this"
- "go ahead" / "go ahead and implement"
- "do it"
