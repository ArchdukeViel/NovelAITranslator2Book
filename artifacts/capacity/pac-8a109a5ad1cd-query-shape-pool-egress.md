# PAC query-shape, pool, and egress evidence

- Audit run: `pac-8a109a5ad1cd`
- Captured UTC: `2026-08-23T20:20:40.0003543Z`
- Scope: local SQLite fixtures and sanitized configuration only
- Provider or hosted database mutation: none

## Verification

- `tools\pytest.ps1 backend/tests/test_catalog_service.py backend/tests/test_activity_database.py backend/tests/test_pipeline_timing_audit.py -q`
  - exit code `0`
  - result: `48 passed in 25.40s`
- `tools\ruff.ps1 check .`
  - exit code `0`
  - result: `All checks passed`

## Query and projection evidence

- `backend/tests/test_catalog_service.py::TestSaveTranslatedChapter::test_existing_chapter_lookup_defers_large_json_columns`
  verifies that routine chapter lookup leaves `media_state_json`,
  `translation_versions_json`, and `translation_edit_history_json` unloaded.
- `backend/src/novelai/activity/database.py` uses a fixed narrow `RETURNING`
  projection for activity claims and timestamp-only updates for heartbeats.
- The async translation path uses scalar/bundle operation classes and does not
  claim that a local fixture is a hosted query-plan or billed-byte measurement.

## Connection arithmetic

The current sanitized settings read was:

```text
DB_CONNECTION_MODE=session
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5
DB_POOL_PROCESS_COUNT=3
DB_CONNECTION_RESERVE=2
DB_CONNECTION_BUDGET=32
DB_POOL_TIMEOUT_SECONDS=30
DB_STATEMENT_TIMEOUT_MS=120000
```

The documented upper-bound arithmetic is exact for this configuration:

```text
3 * (5 + 5) + 2 = 32 <= DB_CONNECTION_BUDGET 32
```

The persistence executor is bounded independently; this arithmetic is a
deployment-wide pool budget, not a claim that every connection is active.

## Egress and hosted attribution

Query-level billed bytes, Supabase plan output, and per-operation R2/provider
egress were unavailable in this local run. No billed-byte, provider-cost, or
hosted egress claim is made. A fresh hosted measurement requires the separate
operator-approved read-only telemetry window and must retain only sanitized
query shape, rows, duration, pool checkout/wait, and provider-reported byte
fields.
