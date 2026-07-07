---
trigger: always_on
---
# Plan-First Rule

## Core Directive

When the user requests a task, feature, change, or fix, you MUST default to **planning/spec mode only** — create a specification (plan) that describes WHAT will be done and HOW — and STOP. Do **NOT** proceed to write implementation code, modify source files, or execute build/test commands unless the user gives an explicit implementation directive.

## When to Plan (Default)

Create a plan/spec when the user:

- Requests a new feature or capability
- Asks for a refactor, redesign, or architectural change
- Describes a bug or issue that requires more than a trivial fix
- Asks "how would you...", "can we...", "what would it take to..."
- Requests changes spanning multiple files or modules
- Provides a vague or open-ended request that needs scoping

## When to Implement Immediately (No Plan Needed)

You MAY implement immediately, without a plan, only when **ALL** of these conditions are true:

1. The user's request is **trivial** — a single-line fix, a typo, a config value change, a command execution, or a file read/search
2. The change affects **one location** in one file
3. There is **no ambiguity** about what to do
4. The change carries **no architectural risk**

Examples of trivial requests:
- "Fix the typo in file X"
- "Run `pytest`"
- "What does this function do?"
- "Search for all uses of `foo`"
- "Add this one import statement"

## Explicit Implementation Keywords

The user MUST use at least **one** of the following (or a close equivalent) before you write any implementation code:

- "implement it" / "implement this"
- "execute the plan" / "execute it"
- "code it" / "code this up"
- "make the changes" / "apply the changes"
- "start implementing" / "start coding"
- "build it" / "build this"
- "go ahead" / "go ahead and implement"
- "proceed with implementation"
- "do it" (when referring to a plan you just presented)

**Without one of these explicit keywords, you MUST NOT write implementation code.** The following do **NOT** authorize implementation:

- "looks good" / "approved" / "sounds right"
- "ok" / "okay" / "sure" / "fine"
- "thanks" / "good" / "nice"
- Thumbs-up emoji or similar reactions
- Any feedback on the plan itself without implementation keywords

When in doubt: **plan, don't code.**

## What a Plan/Spec Must Include

Follow the existing spec format in `.agents/kiro/archive/` where applicable. A plan should contain:

1. **Overview** — 1-2 sentences describing the change at a high level
2. **Requirements** — numbered requirements (REQ-1, REQ-2, ...) with sub-requirements
3. **Design** — architecture decisions, affected files table, component-level design with code sketches where helpful, files not touched, backward compatibility notes
4. **Task breakdown** — ordered, verifiable checklist with file paths
5. **Acceptance criteria** — how to verify success
6. **Non-goals** — what is explicitly out of scope

## Communication Flow

1. User gives a task → You assess: "Is this trivial (one-liner, no ambiguity)?"
2. If trivial → execute immediately
3. If NOT trivial → switch to Plan mode, create a plan/spec, present it to the user
4. Wait for explicit implementation keywords
5. Only then switch to implementation and write code

## Spec Location

Place new specs under `.agents/kiro/specs/<spec-name>/` with:
- `.config.kiro` — `{"specId": "<uuid>", "workflowType": "requirements-first", "specType": "feature"}`
- `requirements.md`
- `design.md`
- `tasks.md`

## Override

If the user explicitly instructs you to both plan AND implement in a single request (e.g., "plan and implement X", "design and build Y"), you may skip the intermediate stop and proceed directly to implementation after creating the plan.
