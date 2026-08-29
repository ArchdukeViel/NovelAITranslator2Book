# Pipeline async execution and capacity — final validation evidence

Date: 2026-08-24
Spec: `pipeline-async-execution-and-capacity`
Task: T-020

## Validation results

- `tools\pytest.ps1 backend/tests -q` — exit 0; 2,944 passed and 16
  skipped in 762.96 seconds (12:42) on the final source tree.
- `tools\pytest.ps1 backend/tests/test_translation_async_boundary.py backend/tests/test_pipeline_timing_audit.py backend/tests/test_activity_database.py backend/tests/test_job_worker_service.py backend/tests/test_checkpoint_resume.py -q` — exit 0; 50 passed in 18.38 seconds.
- `tools\pytest.ps1 backend/tests/e2e/test_full_pipeline.py -q` — exit 0; 5 passed in 14.81 seconds after the compatibility review fix.
- `tools\ruff.ps1 check .` — exit 0; all checks passed.
- `tools\pyright.ps1` — exit 0; 0 errors, 0 warnings, 0 informations.
- `frontend; npm run typecheck` — exit 0.
- `docker compose -f deploy/compose.yml config --quiet` — exit 0.
- Router dependency-boundary guard — exit 1 with no matches, which is the
  expected pass result.
- Canonical `AGENTS.md` duplicate-heading guard — exit 0 with no output.
- `git diff --check` — exit 0; only the existing LF-to-CRLF working-copy
  warnings for the three environment example files were emitted.
- Repository Markdown link audit using `rg --files` with generated/scratch
  exclusions — exit 0; 87 Markdown files checked, 30 local links checked, 0
  broken local links.
- `tools\pytest.ps1 backend/tests/test_environment_templates.py backend/tests/test_microservice_split.py -q` — exit 0; 26 passed in 10.04 seconds.

## Independent review and resolution

An earlier full-suite run reached 2,939 passed and 16 skipped but exposed five
E2E fixture setup errors. The fixture retained a compatibility patch for
`novelai.services.orchestration.translation.safely_refresh_catalog_projection_after_storage_write`, while the async boundary refactor had removed that module-level alias. The smallest safe correction restored the alias explicitly while keeping the translation path on `TranslationPersistencePort`. The five E2E tests then passed, Ruff and Pyright passed after the explicit alias form, and the corrected full suite passed completely as recorded above.

## Scope and remaining gates

No remote GitHub operation, deploy, queue resume, provider call, canonical
PostgreSQL/R2 write, or live load was performed. The isolated R2 benchmark is
unavailable without `TEST_R2_ENDPOINT`; the live canary and 1k/10k/100k reader
stages remain deferred pending their separately authorized operator inputs,
hosted target, telemetry, thresholds, rollback owner, and traffic model.

- `graphify update . --no-cluster` — exit 0; rebuilt 14,274 nodes and 39,229
  edges. Graphify reported the recurring six zero-node source-file warning;
  the refresh completed and updated `graphify-out/graph.json`.

## Continuation recovery validation — 2026-08-24

- Root isolated R2 integration run: exit 0; 7 passed.
- `deploy/.env` isolated R2 integration run: exit 0; 7 passed sequentially.
- Rebuilt backend image: exit 0; PostgreSQL client tools present.
- Isolated encrypted database backup and restore: succeeded; 37 public
  tables, 0 invalid constraints, matching Alembic metadata.
- Independent R2 snapshot readback: succeeded; 980 objects,
  4,022,175 bytes, checksum verification true.

The provider canary, full translation queues, and hosted reader-scale stages
remain outside this local recovery validation and were not started.
