# PAC R2 exact-key and hot-path LIST audit

- Audit run: `pac-8a109a5ad1cd`
- Scope: local tests and static source review only
- Canonical R2 buckets or objects changed/enumerated: none

## Verification

- `tools\pytest.ps1 backend/tests/test_storage_backends.py backend/tests/test_r2_content_addressing.py backend/tests/integration/test_s3_integration.py -q`
  - exit code `0`
  - result: `21 passed, 6 skipped in 23.34s`
- The six integration skips are all `TEST_R2_ENDPOINT not set`; no real R2
  PUT/GET/HEAD/DELETE or cleanup sweep was attempted.
- Required search:
  `rg -n "list_objects_v2|\.list\(" backend/src/novelai/api backend/src/novelai/translation backend/src/novelai/services/orchestration`
  - exit code `0`
  - only match: `backend/src/novelai/api/routers/notifications.py:85`, a
    notification-service list call, not an R2 object-list operation.

## Static classification

The R2 backend still exposes paginated list methods for inventory, namespace
migration, backup/cutover, health-size accounting, and cleanup. Their callers
are outside reader/translation hot paths. Exact-key content operations remain
the `HEAD`/`GET`/immutable `PUT`/delete methods used by content services.

No claim is made about live operation counters, compression/reuse ratios,
conditional-read latency, or final isolated-prefix cleanup because the real
R2 endpoint was unavailable and no canonical-prefix enumeration was allowed.
