# Conservative capacity configuration evidence

Run/design evidence: `pac-8a109a5ad1cd`
Scope: local settings, boundary wiring, and Compose validation

## Controls

- `TRANSLATION_PERSISTENCE_EXPANSION_ENABLED=false` is the default and
  rollback profile. It uses one persistence worker and a zero-length queue,
  so enabling the new measured capacity profile is explicit.
- When expansion is enabled, the validated defaults are two persistence
  workers and an eight-item queue. Worker count is bounded to 1..8 and queue
  size to 0..64. Persistence observations are bounded to 32..4096 entries.
- The shutdown drain deadline is validated to 1..300 seconds; the default is
  30 seconds. Runtime telemetry sampling is 0.05..60 seconds (default 0.25),
  with 32..4096 retained observations (default 256). The event-loop stop
  threshold is validated to 1..60,000 ms (default 1,000 ms).
- Provider chunk concurrency is now validated to 1..256; chapter concurrency
  remains bounded to 1..32. Existing provider and DB pool limits remain the
  separate admission budgets.
- Production startup already rejects an impossible direct/session aggregate:
  `DB_POOL_PROCESS_COUNT * (DB_POOL_SIZE + DB_MAX_OVERFLOW) +
  DB_CONNECTION_RESERVE <= DB_CONNECTION_BUDGET`. The current example
  arithmetic is `3 * (5 + 5) + 2 = 32`.

The gate changes only the bounded persistence profile. It does not activate
the worker, resume the existing queues, change provider credentials, mutate
database schema, or change R2 buckets. Rollback is the environment/config
change `TRANSLATION_PERSISTENCE_EXPANSION_ENABLED=false` followed by the
normal worker restart procedure; no row or runtime-file repair is required.

## Verification

- `tools\pytest.ps1 backend/tests/test_settings.py backend/tests/test_job_worker_service.py -q` — exit 0; 29 passed in 6.81s.
- `tools\pytest.ps1 backend/tests/test_translation_async_boundary.py -q` — exit 0; 9 passed in 4.98s, including the gate’s serialized rollback and expanded-profile assertions.
- `tools\pytest.ps1 backend/tests/test_production_config.py -q` — exit 0; 33 passed in 8.10s, including aggregate pool rejection.
- `docker compose -f deploy/compose.yml config --quiet` — exit 0.
- Focused Ruff over changed Python files — exit 0; all checks passed.
- `tools\pyright.ps1` — exit 0; 0 errors, 0 warnings, 0 informations.
- `graphify update . --no-cluster` — exit 0; graph refreshed successfully.

No live capacity, provider, R2, billing, or queue-resume gate was run.
