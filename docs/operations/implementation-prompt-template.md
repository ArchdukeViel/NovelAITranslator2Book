# Implementation Prompt Template

Copy this template into a new session. Replace `[MILESTONE]` and `[SPEC]` with the target milestone and spec name. The prompt references the canonical docs and the spec's own `design.md`/`tasks.md` so the agent does not need to re-derive the plan.

---

```
You are working in the NovelAITranslator2Book repository on branch main.
Latest commit: c855d8ab.

## 1. Read These Files First (in this order)

1. `AGENTS.md` — operating rules, layer boundaries, canonical names, verification commands.
2. `docs/architecture/architecture.md` — canonical architecture, layer rules, ownership.
3. `docs/roadmap.md` — milestone plan M0-M7, acceptance gates.
4. `docs/DEBT.md` — active technical debt register, completion criteria.
5. `docs/SPECS_COMPLETION.md` — active/archived specs inventory.
6. `docs/storage-contract.md` — canonical ownership matrix and restore rules.
7. `docs/operations/deployment.md` — container topology, reverse proxy routing.
8. `docs/operations/runbook.md` — health, worker, cache invalidation procedures.
9. `docs/operations/data-recovery.md` — backup and restore procedures.
10. `.agents/kiro/specs/[SPEC]/design.md` — contract, data model, API shape, non-goals.
11. `.agents/kiro/specs/[SPEC]/requirements.md` — numbered requirements (REQ-N).
12. `.agents/kiro/specs/[SPEC]/tasks.md` — implementation checklist with REQ-N tags.

## 2. Your Task

Implement **[MILESTONE]** from `docs/roadmap.md`.

### Scope (from roadmap.md)

[paste the milestone Scope block here]

### Acceptance Gates (from roadmap.md)

[paste the milestone Acceptance gates block here]

### Spec Contract (from .agents/kiro/specs/[SPEC]/design.md)

[paste the relevant design sections: data model, API endpoints, public response shape, non-goals]

### Implementation Checklist (from .agents/kiro/specs/[SPEC]/tasks.md)

[paste the full tasks.md content here, or reference it by path]

## 3. Constraints

- Do not modify completed Phase 0 or Phase 1 work unless a regression is proven.
- Do not reintroduce direct storage/DB/source imports in routers. Routers stay thin.
- Use canonical identifiers: `novel_id`, `chapter_id`, `request_id`, `audit_id`, `requesting_user_id`, `credential_owner_user_id`, `provider_key`, `provider_model`, `activity_id`, `job_id`, `request_id`, `credential_id`, `glossary_hash`, `prompt_version`.
- Use owner-only authorization via `require_role("owner")`. Do not invent multi-admin roles.
- Use `ENV`, not `APP_ENV`. Use canonical setting names: `PUBLIC_FRONTEND_URL`, `SESSION_SECRET_KEY`, `WEB_CORS_ORIGINS`, `S3_BUCKET`.
- Follow the existing service extraction pattern: create service in `services/`, add factory to `api/routers/dependencies.py`, thin router to pure HTTP adapter.
- For takedown: use HTTP 451 for legally blocked content. Do not make it configurable.
- For audit: use `audit_id` (not `event_id` or `id`). Use `novel_id`/`chapter_id` in target maps. Use display name + email hash, not raw email.
- Add or update tests for every behavior change. One runnable check is enough for a one-liner.
- Run `python -m ruff check .`, `python -m pyright`, and targeted tests before declaring done.
- Run the router boundary guard: `grep -rn "^from novelai\.(db\.models|storage\.service|sources\.)" backend/src/novelai/api/routers/ --exclude="dependencies.py"` must return no matches.
- Update `docs/DEBT.md` when debt items are resolved (mark Status: Resolved, add evidence).
- Do not commit unless explicitly authorized. Do not push. Do not amend. Do not force checkout.

## 4. Preflight (do this before coding)

1. Inspect the relevant code paths referenced in the spec's `tasks.md`.
2. Confirm the current state matches what `docs/DEBT.md` and `docs/current_state.md` claim.
3. Identify the smallest diff that satisfies the acceptance gates.
4. List the files you expect to change and why.
5. State any assumptions you are making.

## 5. Implementation Order

1. Add or update settings in `backend/src/novelai/config/settings.py` if the spec requires new config.
2. Add or update SQLAlchemy models and Alembic migrations if the spec requires new tables.
3. Add or update the service layer in `backend/src/novelai/services/` or `backend/src/novelai/services/orchestration/`.
4. Add the factory to `backend/src/novelai/api/routers/dependencies.py`.
5. Add or update the router in `backend/src/novelai/api/routers/`.
6. Add or update frontend API client in `frontend/lib/api.ts` or `frontend/lib/public-api.ts`.
7. Add or update frontend route in `frontend/app/(admin)/` or `frontend/app/(public)/`.
8. Add or update tests in `backend/tests/` and `frontend/`.
9. Update `docs/DEBT.md` to mark resolved items.
10. Update `docs/operations/*.md` if procedures changed.

## 6. Verification (run before declaring done)

| Command | Purpose |
|---|---|
| `python -m ruff check .` | Lint |
| `python -m pyright` | Typecheck |
| `python -m pytest backend/tests/test_<relevant>.py` | Targeted tests |
| `grep -rn "^from novelai\.(db\.models\|storage\.service\|sources\.)" backend/src/novelai/api/routers/ --exclude="dependencies.py"` | Router boundary guard |
| `git diff --check` | Diff integrity |

If frontend files changed:

| Command | Purpose |
|---|---|
| `cd frontend && npm run typecheck` | Frontend typecheck |
| `cd frontend && npm run lint` | Frontend lint |
| `cd frontend && npm run build` | Frontend build |

If Dockerfiles or dependencies changed:

| Command | Purpose |
|---|---|
| `docker build -f deploy/admin.Dockerfile -t novelai-admin-test .` | Admin image |
| `docker build -f deploy/reader.Dockerfile -t novelai-reader-test .` | Reader image |
| `docker build -f deploy/frontend.Dockerfile -t novelai-frontend-test .` | Frontend image |

## 7. Final Report

Report:
1. What you implemented (files changed, services added, endpoints added).
2. What you verified (commands run, results).
3. What remains (follow-up debt, unrun checks, known limitations).
4. Any deviations from the spec and why.
5. Any new debt items discovered during implementation.

Do not mark a debt item complete until implementation and validation justify it.
```

---

## How To Use

1. Pick a milestone from `docs/roadmap.md`.
2. Pick the matching spec from `.agents/kiro/specs/`.
3. Copy the template into a new session.
4. Replace `[MILESTONE]` with the milestone name (e.g., `Milestone 2a — Real Health Probes`).
5. Replace `[SPEC]` with the spec directory name (e.g., `deep-health-readiness-checks`).
6. Paste the milestone Scope and Acceptance gates from `docs/roadmap.md`.
7. Paste the relevant sections from the spec's `design.md` (data model, API endpoints, public response shape, non-goals).
8. Paste the full `tasks.md` content, or reference it by path.
9. Start the session.

The agent will read the canonical docs first, then the spec's design and tasks, then implement against the acceptance gates. No re-planning needed.
