# Isolated R2 operation benchmark gate

Run/design evidence: `pac-8a109a5ad1cd`
Scope: isolated non-production R2 test bucket only; no canonical content
mutation

## Result

The isolated-prefix benchmark passed after the test-only R2 settings were
provided. The integration suite exercised exact save/load/overwrite/delete and
prefix-list behavior under a generated namespace. Its cleanup now paginates
the generated prefix, deletes all returned objects, and performs a final
paginated zero-object sweep; cleanup failures are no longer swallowed.

The active local files use the existing `_ID`/`_SECRET_ACCESS_KEY` aliases,
which the test accepts alongside the CI names. The test bucket was distinct
from the application and configured backup buckets. This is isolated operation
evidence only; it is not a production billing, latency, or capacity claim.

## Verification

- `tools\pytest.ps1 backend/tests/integration/test_s3_integration.py -q` - exit
  0; `6 passed` in `11.68s`.
- The run completed the final paginated zero-object cleanup assertion.
- No canonical application object or canonical prefix was mutated.

Provider billing counters and hosted latency attribution remain unavailable;
the local `R2Storage` counters and fixture result remain the authoritative
bounded evidence for this test gate.
