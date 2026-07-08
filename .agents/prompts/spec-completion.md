# Spec Completion Prompt Template

Use this template when starting a spec completion task. It encodes the three strategies that prevent context budget exhaustion:

1. **Smaller, focused specs** — break work into tasks that fit in one session
2. **Checkpoint progress to files early** — write handoff notes to `tasks.md` or scratch files as you go, not at the end
3. **Skip re-reads** — once a file is read, don't re-read it unless it changed

---

## Template

```
You are completing the spec at: {SPEC_PATH}

## Context Budget Rules (CRITICAL — follow strictly)

### Rule 1: Break work into small, focused tasks
- Before starting, read `tasks.md` and identify natural task boundaries
- Each task should be completable in one tool-call sequence without re-reading
- If a task is too large, split it into subtasks and commit each separately
- Prefer many small commits over one large commit

### Rule 2: Checkpoint progress to files EARLY and OFTEN
- Update `tasks.md` after completing EACH task, not at the end
- Write handoff notes to a scratch file if context is running low
- Commit completed work incrementally — don't wait until everything is done
- Use this format for handoff notes:
  ```
  ## Handoff Summary
  - What is done: [list completed tasks]
  - What remains: [list pending tasks]
  - Next concrete step: [specific command or file to inspect]
  - Key files: [paths to inspect]
  ```

### Rule 3: Skip re-reads
- Once you read a file, remember its contents — don't re-read it
- Only re-read if:
  - The file was modified after your last read
  - You need to verify a specific detail you didn't note
  - The file is large and you only need a section (use offset/limit)
- Use `grep` to find specific patterns instead of reading entire files
- Use `git diff` to see what changed instead of re-reading modified files

## Workflow

1. **Read `tasks.md` ONCE** at the start to understand the full scope
2. **Identify task boundaries** — group related subtasks
3. **For each task:**
   a. Read only the files you need (use grep to find them)
   b. Implement the change
   c. Run verification (tests, ruff, pyright)
   d. Update `tasks.md` to mark the task `[x]`
   e. Commit the change with a clear message
4. **If context budget is running low:**
   - Stop and write a handoff summary to a scratch file
   - Commit all completed work
   - Leave the spec in a resumable state

## Verification Commands

Run from repo root:
- Lint: `python -m ruff check .`
- Typecheck: `python -m pyright`
- Test (focused): `python -m pytest backend/tests/test_<filename>.py`
- Test (full): `python -m pytest` (slow — avoid in one shot)

## Commit Message Format

```
<type>: <short subject>

<body explaining what and why>
```

Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`

## Spec Completion Checklist

Before marking a spec complete:
- [ ] All tasks in `tasks.md` marked `[x]`
- [ ] All Definition of Done items marked `[x]`
- [ ] Tests pass: `python -m pytest backend/tests/test_<spec>.py`
- [ ] Lint passes: `python -m ruff check .`
- [ ] Typecheck passes: `python -m pyright`
- [ ] No regressions in existing tests
- [ ] Changes committed with clear messages

## Spec Path

{Spec path goes here — e.g., `.agents/kiro/specs/jp-en-prompt-quality-policy`}

## Current State

[Describe what's already done, what's pending, and any blockers]
```

---

## Usage

Replace the placeholders:
- `{SPEC_PATH}` — the relative path to the spec directory
- `{Spec path goes here}` — same as above
- `{Current State}` — brief description of where you are

Example invocation:
```
Complete the spec at: .agents/kiro/specs/jp-en-prompt-quality-policy

Current State: Tasks 1-11 complete (implementation + tests). Tasks 12-19 pending (snapshot tests, parser tests, cache-key tests, checklist doc). tasks.md not yet updated.
```

---

## Why This Works

The three strategies work together:

1. **Small tasks** = each fits in one session's budget
2. **Early checkpoints** = progress is preserved even if budget runs out
3. **Skip re-reads** = tokens are spent on new work, not re-reading known content

Together they ensure that even if context budget is exhausted, the spec is in a resumable state with all completed work committed and documented.
