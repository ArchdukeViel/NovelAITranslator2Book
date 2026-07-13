# Implementation Prompt - Milestone M2 (Operational Safety)

Copy-paste fenced block into new session. It is pre-filled from
`docs/operations/implementation-prompt-template.md`, M2 in `docs/roadmap.md`,
and matching active specs.

---

```
You are working in the NovelAITranslator2Book repository on branch main.
Latest commit: 10cc94e.

## 1. Read These Files First (in this order)

1. `AGENTS.md` - operating rules, layer boundaries, canonical names, verification commands.
2. `docs/architecture/architecture.md` - canonical architecture, layer rules, ownership.
3. `docs/roadmap.md` - milestone plan M0-M7, acceptance gates.
4. `docs/DEBT.md` - active technical debt register, completion criteria.
5. `docs/SPECS_COMPLETION.md` - active/archived specs inventory.
6. `docs/storage-contract.md` - canonical ownership matrix and restore rules.
7. `docs/operations/deployment.md` - container topology, reverse proxy routing.
8. `docs/operations/runbook.md` - health, worker, cache invalidation procedures.
9. `docs/operations/data-recovery.md` - backup and restore procedures.
10. `.agents/kiro/specs/deep-health-readiness-checks/design.md`, `requirements.md`, `tasks.md` - M2a contract and checklist.
11. `.agents/kiro/specs/pdf-exporter=registration/design.md`, `requirements.md`, `tasks.md` - M2b historical spec. Read after roadmap; it conflicts with current roadmap PDF direction.
12. `.agents/kiro/specs/scheduled-backups-and-restore-drills/design.md`, `requirements.md`, `tasks.md` - backup contract and checklist.
13. `.agents/kiro/specs/maintenance-cron/design.md`, `requirements.md`, `tasks.md` - retention/cleanup contract and checklist.
14. `.agents/kiro/specs/scheduler-runtime-state-persistence/design.md`, `requirements.md`, `tasks.md` - DEBT-036 state persistence contract.
15. `.agents/kiro/specs/atomic-json-storage-recovery/design.md` - atomic storage write contract.

## 2. Your Task

Implement **Milestone M2 - Operational Safety (Phase 2)** from `docs/roadmap.md`.

### Scope (from roadmap.md)

- **M2a (Health Probes):** Replace static `/health` routes with database, storage, and worker probes. Expose diagnostic details without leaking secrets. (DEBT-001)
- **M2b (PDF Exporter):** Remove registered PDF stub exporter from registry. Document formal deprecation. (DEBT-007)
- **M2c (Storage & Backups):** Schedule local backups, configure retention times, clean fetch caches, prune events and activity logs, and lock writes atomically. (DEBT-010, DEBT-025, DEBT-034, DEBT-035, DEBT-036)

### Acceptance Gates (from roadmap.md)

- Focused health tests, backup manager tests, and cleanup execution tests pass.
- Multi-process lock mechanism prevents concurrent write conflicts.

### Authoritative Conflict: PDF Direction

`pdf-exporter=registration` says to register PDF. Current `docs/roadmap.md` and DEBT-007 say the opposite: remove registered `PDFExporter` stub, deprecate PDF, reject new PDF requests, preserve historical manifests. `docs/roadmap.md` is authoritative.

Do not register, implement, or advertise PDF export. Before editing, report this spec conflict. Implement the roadmap direction:

- Remove `PDFExporter` import and `register_exporter("pdf", ...)` from `novelai.runtime.bootstrap.bootstrap_exporters()`.
- Remove or deprecate dead `PDFExporter` code only after finding all callers. Do not add PDF dependency.
- Make `ExportService.export_pdf()` reject with a controlled, safe unsupported/deprecated-format error. Raw `KeyError` and `NotImplementedError` must not reach API callers.
- Remove PDF from supported/exportable format discovery. Do not rewrite historical manifests that already record `format: "pdf"`.
- Replace tests asserting `NotImplementedError` with tests for unregistered/deprecated PDF behavior and preserved non-PDF exporters.
- Document formal PDF deprecation and upgrade path: reintroduce only after approved renderer, font policy, security review, and real export tests.

### Current State (verified before this prompt)

- `backend/src/novelai/api/app.py` owns static `GET /api/health` and `GET /health`; both return `{ "status": "ok" }`. There is no `api/routers/health.py`; do not assume spec path exists.
- `runtime/bootstrap.py` imports `PDFExporter` and registers `pdf`; `pdf_exporter.py` raises `NotImplementedError`; `ExportService.export_pdf()` delegates to `self.export("pdf", ...)`.
- `BackupManager` exists in `backend/src/novelai/services/backup_manager.py`, but DEBT-010 says it has no scheduler/container integration or retention policy.
- Atomic JSON storage recovery already has focused coverage in `backend/tests/test_atomic_json_storage_recovery.py`. Keep this behavior; extend only where M2c requires locking/cleanup.
- Current focused test files include `test_backup_manager.py`, `test_backup_restore_catalog_refresh.py`, `test_pdf_exporter.py`, `test_atomic_json_storage_recovery.py`, `test_translation_scheduler.py`, and `test_translation_scheduler_observability.py`.

### Spec Contract

#### M2a - Health

- Public `GET /health/live`: process-only, unauthenticated, fast, no DB/storage/worker calls; `200` with status, service, timestamp.
- Public `GET /health/ready`: public-safe readiness response; probe required DB, migrations where applicable, configured storage, and worker/queue backend. Required failure or timeout returns `503`. Never expose credentials, hostnames, paths, stack traces, raw exceptions, bucket names, or signed URLs.
- Owner-only `GET /admin/health`: detailed but still redacted probe results. Use `require_role("owner")`, not a new admin role. Include status, latency, safe message, checked timestamp, safe metadata.
- Probe states: `healthy`, `degraded`, `unhealthy`. Bound each probe and total request with configured timeout. A failed probe must not stop unrelated probes.
- Storage probe uses a dedicated health-check path and removes its temporary file. Never mutate user content.
- Health spec backup-freshness probe is optional until M2c backup status exists. Do not block M2a on it.

#### M2c - Backups, cleanup, locking, scheduler state

- Scheduled backups: use existing scheduler/worker pattern; local backup target first; explicit retention; do not back up `.env`, secrets, temporary files, caches, worker scratch, or runtime locks.
- Backup retention: preserve newest successful backup and configured minimum successful backup count. Failed/offsite states must not erase local successful artifact.
- Maintenance cleanup: explicit config and allowlisted cleanup roots only; reject blank/root/project-root paths; prevent symlink escape; support dry-run; preserve active jobs, current exports, audit/security records, raw source chapters, and non-cache durable artifacts.
- Cleanup scope: expired fetch/cache data, old terminal activity records, expired scheduler runtime records, old backup artifacts via backup service. Do not make broad arbitrary file deletion helpers.
- Atomic writes: write temp file in target directory, flush and fsync file, `os.replace`, best-effort parent-directory fsync, cleanup temp on error. Use a multi-process lock for write/cleanup conflicts. Windows lock retries must be bounded and tested.
- Scheduler runtime state: persist cooldown, failure, exhausted, heartbeat and next-eligible state so restart does not erase cooldown. Use canonical `job_id`, `source_key`, `provider_key`, `activity_id`; do not add aliases.

### Implementation Checklist

Use full matching checklist files by path. Apply only items necessary for M2 acceptance gates; do not blindly build optional UI, S3, Redis, alerts, or new dashboards.

- [ ] 1. Preflight all current health, exporter, scheduler, storage, backup, cleanup, migration, and test paths.
- [ ] 2. Resolve PDF conflict in report; follow roadmap deprecation direction.
- [ ] 3. M2a: add health contract, bounded probe service, live/ready routes, owner-only admin diagnostics, redaction tests, and deployment/runbook documentation.
- [ ] 4. M2b: unregister PDF stub, safely reject PDF requests, preserve historical manifests, document deprecation, add regression tests.
- [ ] 5. M2c: add minimal settings, persistence/migrations only where existing durable store lacks needed records, scheduler hooks, backup retention, safe cleanup, atomic multi-process locking, and scheduler state persistence.
- [ ] 6. Add focused tests for health, backup/retention, cleanup execution/dry-run, atomic locking, Windows retries, scheduler restart state, and PDF deprecation.
- [ ] 7. Update DEBT-001, DEBT-007, DEBT-010, DEBT-025, DEBT-034, DEBT-035, and DEBT-036 only after their exact completion criteria and verification pass. Do not close a debt item merely because supporting code exists.
- [ ] 8. Update `docs/roadmap.md` M2 status only when M2 acceptance gates have evidence. Update `docs/operations/deployment.md`, `runbook.md`, and `data-recovery.md` for changed operator procedures.

## 3. Constraints

- Do not modify completed Phase 0 or Phase 1 work unless a regression is proven.
- Do not reintroduce direct storage/DB/source imports in routers. Routers stay thin.
- Use canonical identifiers: `novel_id`, `chapter_id`, `paragraph_id`, `chunk_id`, `bundle_id`, `provider_key`, `provider_model`, `activity_id`, `job_id`, `request_id`, `credential_id`, `requesting_user_id`, `credential_owner_user_id`, `prompt_version`, `glossary_hash`.
- Use owner-only authorization via `require_role("owner")`. Do not invent multi-admin roles.
- Use `ENV`, not `APP_ENV`; existing canonical settings names only. Do not add configuration for values that have no active use.
- API routers remain HTTP adapters. Put health, backup, cleanup, lock, and scheduler policy in services/domain/storage layers.
- Do not add a PDF renderer or dependency. PDF is deprecated in this milestone.
- Never log/return secrets, raw filesystem paths, DB URLs, bucket names, signed URLs, stack traces, API keys, or raw exception text.
- Use SQLAlchemy models and Alembic migrations for new schema. No raw SQL.
- Do not delete raw scraped chapters. Preserve audit data and current manifest-referenced export artifacts.
- Add/update tests for every behavior change. One runnable check is enough for a one-line change.
- Run `python -m ruff check .`, `python -m pyright`, focused tests, router boundary guard, and `git diff --check` before declaring done.
- Update `docs/DEBT.md` when debt resolves: `Status: Resolved` plus concrete evidence.
- Do not commit, push, amend, or force checkout unless explicitly authorized.

## 4. Preflight (do this before coding)

1. Confirm current state against `docs/DEBT.md` and `docs/current_state.md`.
2. Read two neighboring services/tests before adding a third. Locate actual health ownership in `api/app.py`; do not create a route module only because spec assumes one.
3. Map every PDF call site and public format-discovery path before deleting stub registration. Determine exact controlled error shape already used by export service.
4. Inspect existing lock primitives. Reuse one if it satisfies multi-process Windows requirements. Do not add Redis/database locks for single-node filesystem storage without need.
5. Identify smallest deliverable meeting gates. Split M2a/M2b/M2c internally if needed, but do not mark M2 done until gates are proven.
6. List expected files and reasons. State assumptions, especially scheduler availability, database backend, backup target, and existing test fixture behavior.
7. Report PDF spec/roadmap conflict before edits. Record roadmap as authority.

## 5. Implementation Order

1. Add only settings required by active health, backup, retention, cleanup, lock, or scheduler-state behavior.
2. Add SQLAlchemy models and a new Alembic migration only for durable backup, maintenance, or scheduler-runtime records that cannot reuse existing durable state.
3. Implement service/domain behavior: health probes, exporter deprecation error, backup scheduling/retention, safe cleanup, atomic locking, scheduler state persistence.
4. Add factories in `api/routers/dependencies.py`.
5. Add thin routes for health/admin operations. Preserve existing `/health` and `/api/health` compatibility only if callers/tests prove a need; otherwise point them at public-safe readiness/liveness semantics and document it.
6. Add/adjust tests before docs status changes.
7. Update operations docs, DEBT evidence, and roadmap state after verification.

## 6. Verification (run before declaring done)

| Command | Purpose |
|---|---|
| `python -m ruff check .` | Lint |
| `python -m pyright` | Typecheck |
| `python -m pytest backend/tests/test_backup_manager.py --tb=short -q` | Backup manager |
| `python -m pytest backend/tests/test_atomic_json_storage_recovery.py --tb=short -q` | Atomic storage/recovery |
| `python -m pytest backend/tests/test_pdf_exporter.py --tb=short -q` | PDF deprecation regression |
| `python -m pytest backend/tests/test_translation_scheduler.py backend/tests/test_translation_scheduler_observability.py --tb=short -q` | Scheduler persistence/observability |
| `python -m pytest backend/tests/test_<health>.py --tb=short -q` | Focused health tests added by this work |
| `python -m pytest backend/tests/test_<cleanup>.py --tb=short -q` | Focused cleanup/lock tests added by this work |
| `rg -n "^from novelai\.(db\.models|storage\.service|sources\.)" backend/src/novelai/api/routers/ --glob "!dependencies.py"` | Router boundary guard; no output |
| `git diff --check` | Diff integrity |

Run migration validation from `backend/` if schema changed:

| Command | Purpose |
|---|---|
| `alembic -c backend/alembic.ini upgrade head` | Migration validation; requires `DATABASE_URL` |

If Docker/dependency files changed, run relevant Docker image builds. Do not change dependencies for PDF.

## 7. Final Report

Report:
1. What changed by M2a, M2b, M2c; files, services, migrations, endpoints.
2. PDF contract conflict and how roadmap authority was applied.
3. Verification commands and exact results, including lock concurrency evidence.
4. Debt entries resolved, with evidence; remaining blockers and unrun environment checks.
5. Deviations from specs and why; new debt found.

Do not mark a debt item complete until implementation and validation justify it.
```

---

## M2 Notes

- M2 has three sub-milestones. No single matching spec covers all work.
- PDF registration spec conflicts with roadmap and DEBT-007. Roadmap wins.
- Skip optional S3, UI, dashboards, alerts, and restore-drill automation unless current code or acceptance gates require them. Local scheduled backups, retention, safe cleanup, and lock evidence are M2 core.
