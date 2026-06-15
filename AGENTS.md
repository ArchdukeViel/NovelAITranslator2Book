# AGENTS.md

Agent-neutral operating guide for AI coding assistants working in this repository
(Hermes, Codex, Cline, Cursor, Claude Code, ChatGPT, etc.).

This file is an onboarding and guardrail document. It is not a roadmap, not a
phase plan, and not a substitute for the canonical architecture.

## 1. Source of Truth

The highest project-level authority is:

- `docs/architecture/architecture.md`

Before making a non-trivial change, read the relevant parts of that document and
verify the current code. If this file conflicts with the architecture document,
the architecture document wins. Report the conflict instead of guessing.

Use this priority order when deciding what to do:

1. User's latest explicit instruction
2. Current code and tests
3. `docs/architecture/architecture.md`
4. Other current project docs
5. Existing implementation patterns
6. General best practices

Do not rely on stale memory, old prompt packs, archived docs, or previous phase
reports when the repository says something different.

## 2. Project Identity

This repository is a web-based novel translation platform.

Core product direction:

- Crawl and ingest Japanese web-novel sources.
- Queue and run translation jobs.
- Let the owner/admin review, edit, manage, and export translated content.
- Serve a public reader interface.
- Support registered public users so they can save user-specific data.
- Allow controlled public contribution workflows when the architecture and
  security model explicitly support them.

Current technical shape:

- Backend: FastAPI under `/api` (`backend/src/novelai`, import package
  `novelai`)
- Frontend: Next.js / React / TypeScript under `frontend/`
- Runtime storage: private storage under `storage/` unless replaced by the
  architecture
- Background work: crawler / translation / job worker processes
- Database and auth: follow the current architecture and migrations; do not
  invent parallel auth or persistence paths

Product assumption:

- There is one owner/admin account, controlled by the project owner.
- Public users may exist, but they are not admins.
- Any public contribution feature must be authenticated, rate-limited,
  auditable, revocable, and mediated through backend services.

## 3. Non-Negotiable Architecture Boundaries

Respect the dependency direction defined by the architecture. As a working rule:

```text
api -> services -> domain -> storage/providers/sources/export
```

Frontend must call the backend through the approved frontend API client layer.
Do not make React components responsible for backend policy, scheduling policy,
provider selection, storage rules, or authorization decisions.

Before editing, identify the owning layer:

- API routers stay thin: request validation, dependency injection, response
  shaping, and delegation only.
- Use-case logic belongs in `services/` or orchestration modules.
- Domain rules belong in domain/application logic, not in routers or React.
- Source parsing belongs in source adapters.
- HTTP fetching, throttling, SSRF protection, and cache policy belong in
  infrastructure/network layers.
- Prompt construction belongs in prompt modules.
- Provider API details belong in provider modules.
- Persistence belongs behind storage/repository/database abstractions.
- Export logic belongs in export modules.
- Background scheduling and job policy belong in worker/service/job layers.

Forbidden crossings:

- Storage importing API/router objects
- Providers importing storage policy
- Source adapters importing service orchestration
- Translation stages touching FastAPI request/response objects
- React implementing scheduler, QA, provider, or authorization policy
- API responses exposing raw filesystem paths
- Frontend-only flags pretending to be authorization

## 4. Canonical Naming and Contract Discipline

Preserve canonical identifiers unless the architecture changes them:

- `novel_id`
- `chapter_id`
- `paragraph_id`
- `chunk_id`
- `bundle_id`
- `provider_key`
- `provider_model`
- `activity_id`
- `job_id`
- `request_id`

Legacy aliases may exist for compatibility. Do not create new aliases casually.
Naming drift is architecture rot wearing a fake mustache.

When changing public contracts:

- Maintain backward compatibility unless the task explicitly permits a breaking
  change.
- Update backend schemas, frontend types, tests, and docs together when the
  contract changes.
- Do not silently change response shapes.
- Do not let frontend types become wishful thinking disconnected from backend
  serializers.

## 5. Authentication, Authorization, and Public Users

Treat auth as backend-owned security infrastructure.

Hard rules:

- Do not fake users with localStorage IDs, request-provided usernames, unsigned
  cookies, frontend-only flags, or trust-me headers.
- Do not grant admin behavior to public users.
- Do not infer ownership from client-provided fields.
- Enforce object-level authorization in backend services or policy layers.
- Keep session/cookie behavior aligned with the canonical architecture.

Public-user features must be designed as limited user capabilities, not as a
shortcut into admin workflows.

Public contribution workflows are security-sensitive. If they involve provider
API keys, credentials, quotas, translation capacity, or user-funded resources,
then the implementation must include a clear credential model, encryption or
secret handling, audit trail, revocation path, abuse controls, and tests. If the
architecture does not yet define that safely, stop and report the gap.

## 6. Security Rules

Never expose:

- Provider API keys
- Auth headers
- Cookies or session tokens
- Passwords
- OAuth secrets
- Database credentials
- Raw tracebacks in public API responses
- Internal filesystem paths
- Private runtime storage contents

Never serve runtime storage as static public files unless the architecture
explicitly introduces a safe public object-storage layer.

Never accept raw filesystem paths from API clients as authority. Use IDs,
validated references, or storage abstractions.

Never mutate real storage, credentials, migrations, deployment config, or user
data unless the task explicitly requires it and the risk is understood.

## 7. Change Discipline

Make changes in small, reviewable increments.

For every task:

1. Identify the goal.
2. Identify the owning layer.
3. Inspect existing patterns before inventing new ones.
4. Keep unrelated cleanup out of scope.
5. Add or update tests when behavior changes.
6. Run the relevant verification commands.
7. Report exactly what changed and what remains uncertain.

Do not create duplicate systems because the existing one feels inconvenient.
That is how a clean codebase becomes a haunted warehouse.

Avoid:

- Broad rewrites without explicit permission
- Opportunistic refactors mixed into feature work
- Dependency upgrades unless requested
- New architecture documents competing with the canonical one
- New runtime folders without checking storage rules
- New environment variables without documenting them
- Generated files or build artifacts committed to source control

## 8. Context-Wasting Work and Scout Subagents

Some work is necessary but toxic to the main context: wide `rg` searches, grep
sweeps, directory trees, dependency spelunking, repeated file reads, test
inventory, route inventory, and architecture reconnaissance.

For these tasks, prefer a bounded scout/subagent workflow when the tool supports
it. The main agent remains responsible for decisions. The scout only explores
and reports.

Use a scout/subagent for:

- broad repository exploration
- locating definitions, call sites, routes, schemas, migrations, tests, or docs
- comparing docs against implementation
- finding security-sensitive patterns
- identifying files affected by a planned change
- summarizing noisy command output

Do not use a scout/subagent for:

- editing files
- committing changes
- making product or architecture decisions
- changing dependencies
- running migrations
- touching secrets, credentials, or production data
- recursively spawning more subagents

Scout/subagent limits:

- Read-only commands only.
- No source edits.
- No commits or pushes.
- No installs or dependency changes.
- No destructive shell commands.
- Summarize findings; do not paste raw command floods into the main context.
- Preserve raw output only in an ignored temporary artifact when useful.

A scout/subagent report must use this format:

```markdown
# Scout Report

## Objective

## Verdict
FOUND / NOT FOUND / PARTIAL / BLOCKED

## Files Inspected
| File | Why inspected | Relevant finding |
|---|---|---|

## Findings

## Evidence
- `path/to/file.ext:line-line` — why it matters

## Unknowns / Limits

## Recommended Next Action
```

If no real subagent tool is available, emulate the same workflow manually: run
the noisy exploration separately, compress it into the report above, and only
bring the distilled report back into the main reasoning context.

## 9. Build, Test, and Verification

Verify the current commands from the repository before assuming they still match
this file. At the time this guide was written, useful commands included:

Backend, from repository root:

```bash
pip install -e ".[documents,openai,gemini,dev]"
pytest --tb=short -q
pyright
ruff check .
```

Frontend, from `frontend/`:

```bash
npm install
npm run typecheck
npm run build
```

Run targets, when applicable:

```bash
novelaibook web --reload
novelaibook worker
npm run dev
```

Verification rules:

- If you ran checks, report the exact command and result.
- If you could not run checks, say why.
- If a check fails, report the failing command, the relevant error, and whether
  your change likely caused it.
- Do not claim success from inspection alone when tests/builds were available
  but not run.

## 10. Documentation Discipline

Keep documentation useful and current.

- `docs/architecture/architecture.md` remains the canonical architecture.
- Do not create competing roadmap or architecture files.
- Do not reintroduce scratch files such as `project_tree.txt` unless the user
  explicitly asks for a temporary local artifact and it is not committed.
- Archive or label obsolete docs instead of leaving misleading active docs.
- Update docs when behavior, contracts, commands, or operational assumptions
  change.

Documentation should reduce future confusion, not become a museum of old plans.

## 11. Agent Behavior in This Repository

When asked to review:

- Read the relevant files.
- Identify whether the result matches architecture.
- Point out drift, missing tests, unsafe shortcuts, and stale assumptions.
- Recommend the next safest action.

When asked to implement:

- Modify only files needed for the requested change.
- Preserve architecture boundaries.
- Avoid unrelated cleanup.
- Add tests where practical.
- Run relevant checks where available.
- Return a concrete implementation report.

When asked for a prompt:

- Write a scoped, copy-ready prompt.
- Include allowed files, forbidden files, task steps, validation, and required
  final report format.

When asked to explore:

- Use the scout/subagent workflow for broad or noisy reconnaissance.
- Return compact findings with evidence.
- Do not dump raw `rg`, `grep`, `tree`, or full-file output unless explicitly
  requested.

When unsure:

- Prefer inspecting the repository over guessing.
- Ask only when the ambiguity blocks safe progress.
- Otherwise make the smallest safe assumption and state it.

## 12. Required Final Report for Implementation Work

Use this format after modifying files:

```markdown
# Implementation Report

## Verdict
PASS / PARTIAL / FAIL

## Files Modified

## Files Created

## Files Deleted

## What Changed

## Checks Run

## Remaining Risks

## Recommended Next Step
```

The report must distinguish verified facts from assumptions. Pretty lies are
still lies; do not polish uncertainty into certainty.
