# Public reader correctness and isolation evidence

Run/design evidence: `pac-8a109a5ad1cd`
Scope: local public-router fixtures plus the fixture-only capacity harness

## Correctness contract

- The harness matrix covers published catalog/detail/chapter 200 responses,
  unpublished and unavailable 404 isolation, approved takedown 404
  isolation, missing active-artifact 404 isolation, and adult-detail field
  filtering.
- Malformed and stale active references are rejected as non-body-bearing
  samples. A cancelled caller is not accepted and records zero canonical
  writes. The report stores status/shape/reference counters only and records
  zero raw response bodies.
- Warm-hit and cold-miss cache modes are represented separately. Conditional
  HTTP response handling is recorded as unavailable because the public router
  does not expose a 304/ETag contract; the harness does not invent one or mark
  it as passed.
- The real public availability/router tests continue to exercise the
  application contract with isolated fixtures. The harness matrix is an
  additional fail-closed capacity assertion, not a substitute for those
  route tests.

## Verification

- `tools\pytest.ps1 backend/tests/test_public_reader_availability.py backend/tests/test_public_router.py backend/tests/test_capacity_harness.py -q` - exit 0; 158 passed in 37.01s.
- `tools\pytest.ps1 backend/tests/test_capacity_harness.py -q` - exit 0; 10 passed in 3.56s.
- Focused Ruff over the harness files - exit 0; all checks passed.
- `tools\pyright.ps1` - exit 0; 0 errors, 0 warnings, 0 informations.
- `graphify update . --no-cluster` - exit 0; graph refreshed successfully.

No hosted route, production content, raw public body, canonical DB row, R2
object, provider, or queue was touched by this capacity slice.
