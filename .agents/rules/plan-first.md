---
trigger: always_on
description: Default to planning and specification before making non-trivial code modifications.
---

# Plan-First Rule

## Core Directive

When requested a task, feature, change, or fix, default to **planning/spec mode only** — create a plan or specification that describes WHAT will be done and HOW — and STOP. Do **NOT** proceed to write implementation code, modify source files, or execute build/test commands unless given an explicit implementation directive.

## When to Plan (Default)

Create a plan/spec when:
- Requesting a new feature or capability
- Asking for a refactor, redesign, or architectural change
- Describing a bug or issue that requires more than a trivial fix
- Asking "how would you...", "can we...", "what would it take to..."
- Requesting changes spanning multiple files or modules
- Providing a vague or open-ended request that needs scoping

## When to Implement Immediately (No Plan Needed)

Implement immediately, without a plan, only when **ALL** of these conditions are true:
1. Request is **trivial** — single-line fix, typo, config value change, command execution, or file read/search
2. Change affects **one location** in one file
3. There is **no ambiguity** about what to do
4. Change carries **no architectural risk**

## Explicit Implementation Keywords

User must use at least **one** of the following before writing implementation code:
- "implement it" / "implement this"
- "execute the plan" / "execute it"
- "code it" / "code this up"
- "make the changes" / "apply the changes"
- "start implementing" / "start coding"
- "build it" / "build this"
- "go ahead" / "go ahead and implement"
- "proceed with implementation"
- "do it"
